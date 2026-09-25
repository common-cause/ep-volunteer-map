"""
sync_opportunities.py — pull EP volunteer opportunities from a Google Sheet,
write them to data/opportunities.json, and (optionally) publish that file to
GitHub via the contents API.

Usage:
    python scripts/sync_opportunities.py              # write the JSON; no push
    python scripts/sync_opportunities.py --push       # publish if content changed (Civis mode)
    python scripts/sync_opportunities.py --dry-run    # print the JSON; write nothing

Env vars (loaded from .env at the project root):
    GOOGLE_SHEETS_CREDENTIALS_PASSWORD      Service account JSON. Read by ccef_connections.
    GOOGLE_SHEET_ID                         The long ID from the Sheet URL. Keep it out of
                                            the repo (it is public).
    GOOGLE_SHEET_TAB                        Default: "Opportunities". Opened BY NAME: the
                                            Sheet's first tab is "Read me".
    EP_VOLUNTEER_MAP_GITHUB_PAT_PASSWORD    Fine-grained PAT, this repo only, Contents
                                            read & write (only for --push).
    GITHUB_REPO                             Default: common-cause/ep-volunteer-map.

Sheet schema (row 1, headers case-insensitive; see docs/SPEC.md):
    state        required. Full name or USPS code; the 50 states plus DC.
    title        required. Short heading.
    description  required. Blank-line runs collapse to one paragraph break.
    link         required. http(s) only.
    enabled      optional. Blank/TRUE shows the row; FALSE hides it.
    ends         optional date. Shown through the end of that day, Eastern.
Any other column (e.g. "last updated", "updated by") is ignored: the output is
an allowlist, so a column added to the Sheet later never reaches the page.

Everything in the Sheet is published on a public page. There is deliberately no
content filter (Rob, 2026-09-25); the Sheet's "Read me" tab says so. Text is
stored as plain text, and the front end must render it as text, never as HTML.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = REPO_ROOT / "data" / "opportunities.json"
OUTPUT_REPO_PATH = "data/opportunities.json"  # Path inside the GitHub repo
GITHUB_CREDENTIAL_NAME = "EP_VOLUNTEER_MAP_GITHUB_PAT"
DEFAULT_REPO = "common-cause/ep-volunteer-map"
DEFAULT_TAB = "Opportunities"
EASTERN = ZoneInfo("America/New_York")
SCHEMA_VERSION = 1

REQUIRED_COLUMNS = ("state", "title", "description", "link")

STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
}
_STATE_LOOKUP = {k.lower(): k for k in STATES}
_STATE_LOOKUP.update({v.lower(): k for k, v in STATES.items()})
_STATE_LOOKUP.update({alias: "DC" for alias in (
    "washington dc", "washington d.c.", "washington, dc", "washington, d.c.", "d.c.")})

# Formats an organizer is likely to type, or that Sheets displays for a date cell.
DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%B %d, %Y", "%b %d, %Y",
                "%B %d %Y", "%b %d %Y", "%d %B %Y", "%d %b %Y")
SHEETS_EPOCH = date(1899, 12, 30)  # serial-number dates, if a cell comes back unformatted


def warn(row_num: int, msg: str) -> None:
    print(f"  WARN: row {row_num}: {msg} — skipping.", file=sys.stderr)


def normalize_row(row: dict) -> dict:
    out = {}
    for key, value in row.items():
        norm_key = str(key).strip().lower()
        if isinstance(value, str):
            value = value.strip()
        out[norm_key] = value
    return out


def as_text(value) -> str:
    """Cell value as text. gspread numericises cells, so a title "2026" arrives as an int."""
    if value is None:
        return ""
    return str(value).strip()


def is_truthy(value) -> bool:
    if value is None or value == "":
        return True
    return str(value).strip().lower() not in ("false", "0", "no", "off", "disabled")


def normalize_description(s: str) -> str:
    """
    Collapse paragraph separators so Sheet edits don't leak whitespace artifacts.

    Staff produce different paragraph-break patterns in multi-line cells (a
    space on the "blank" line, trailing whitespace). Normalize to bare ``\\n\\n``
    so identical content hashes identically.
    """
    if not s:
        return s
    lines = [line.strip() for line in s.replace("\r\n", "\n").split("\n")]
    out: list[str] = []
    blank = False
    for line in lines:
        if not line:
            if not blank:
                out.append("")
                blank = True
        else:
            out.append(line)
            blank = False
    return "\n".join(out).strip()


def parse_state(value: str) -> str | None:
    return _STATE_LOOKUP.get(re.sub(r"\s+", " ", value).strip().lower())


def is_http_url(value: str) -> bool:
    """http(s) with a host and no whitespace. Refuses javascript:, data:, bare text."""
    if not value or re.search(r"\s", value):
        return False
    if not re.match(r"^https?://", value, re.IGNORECASE):
        return False
    try:
        return bool(urlsplit(value).hostname)
    except ValueError:
        return False


def parse_ends(value) -> date | None:
    """A date from an ``ends`` cell. Raises ValueError if it can't be read."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return SHEETS_EPOCH + timedelta(days=int(value))
    text = as_text(value)
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(text)


def validate_row(row: dict, row_num: int, today: date) -> tuple[str, dict] | None:
    """``(USPS, opportunity)`` for a publishable row, else None (with a WARN if it looks like a mistake)."""
    state_raw = as_text(row.get("state"))
    title = as_text(row.get("title"))
    description = normalize_description(as_text(row.get("description")))
    link = as_text(row.get("link"))
    ends_raw = row.get("ends")

    # A fully blank row is spacing, not a mistake.
    if not any((state_raw, title, description, link)):
        return None
    if not is_truthy(row.get("enabled")):
        return None

    state = parse_state(state_raw)
    if not state:
        warn(row_num, f"unknown state {state_raw[:40]!r}")
        return None
    missing = [c for c, v in (("title", title), ("description", description), ("link", link)) if not v]
    if missing:
        warn(row_num, f"{state} is missing {', '.join(missing)}")
        return None
    if not is_http_url(link):
        warn(row_num, f"{state} link is not an http(s) URL ({link[:60]!r})")
        return None

    opp = {"title": title, "description": description, "link": link}
    if as_text(ends_raw):
        try:
            ends = parse_ends(ends_raw)
        except ValueError:
            # Fail visible, not open: an unreadable date must not mean "never expires".
            warn(row_num, f"{state} ends date {as_text(ends_raw)[:30]!r} isn't a date (use YYYY-MM-DD or M/D/YYYY)")
            return None
        if ends < today:
            return None  # expired: shown through the end of its day, Eastern
        opp["ends"] = ends.isoformat()
    return state, opp


def check_headers(headers: list[str]) -> list[str]:
    """Required columns missing from the header row (normalized)."""
    have = {str(h).strip().lower() for h in headers}
    return [c for c in REQUIRED_COLUMNS if c not in have]


def build_states(rows: list[dict], today: date) -> dict[str, list[dict]]:
    """``{USPS: [opportunity, ...]}``, states sorted, each list in Sheet order."""
    states: dict[str, list[dict]] = {}
    for i, raw in enumerate(rows):
        result = validate_row(normalize_row(raw), row_num=i + 2, today=today)
        if result:
            state, opp = result
            states.setdefault(state, []).append(opp)
    return dict(sorted(states.items()))


def content_hash(states: dict) -> str:
    canonical = json.dumps(states, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_payload(states: dict, generated_at: str) -> dict:
    return {
        "_meta": {
            "schema_version": SCHEMA_VERSION,
            "generated_at": generated_at,
            "content_hash": content_hash(states),
            "counts": {"states": len(states), "opportunities": sum(len(v) for v in states.values())},
        },
        "states": states,
    }


def serialize(data: dict) -> bytes:
    return (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def previous_hash() -> str | None:
    if not OUTPUT_JSON.exists():
        return None
    try:
        return json.loads(OUTPUT_JSON.read_text(encoding="utf-8")).get("_meta", {}).get("content_hash")
    except (json.JSONDecodeError, AttributeError):
        return None


def write_atomic(data: bytes) -> None:
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT_JSON.with_suffix(".json.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, OUTPUT_JSON)


def read_sheet(sheet_id: str, tab: str) -> tuple[list[str], list[dict]]:
    from ccef_connections import SheetsConnector

    with SheetsConnector() as conn:
        ws = conn.get_spreadsheet(sheet_id).worksheet(tab)
        headers = ws.row_values(1)
        rows = ws.get_all_records() if headers else []
    return headers, rows


def publish_to_github(data: bytes, repo: str) -> str | None:
    """Commit the file via the contents API. Returns the commit SHA, or None if identical."""
    from ccef_connections import GitHubConnector

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    with GitHubConnector(credential_name=GITHUB_CREDENTIAL_NAME) as gh:
        return gh.put_file_if_changed(
            repo=repo,
            path=OUTPUT_REPO_PATH,
            content_bytes=data,
            message=f"Sync opportunities.json from Google Sheet ({stamp})",
            branch="main",
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync EP volunteer opportunities from the Sheet to data/opportunities.json")
    parser.add_argument("--push", action="store_true", help="publish to GitHub if content changed (Civis mode)")
    parser.add_argument("--dry-run", action="store_true", help="print the JSON; write nothing")
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv
        load_dotenv(REPO_ROOT / ".env")
    except ImportError:
        pass
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    tab = os.environ.get("GOOGLE_SHEET_TAB", DEFAULT_TAB)
    if not sheet_id:
        print("ERROR: GOOGLE_SHEET_ID not set", file=sys.stderr)
        return 2

    print(f"Reading tab '{tab}' ...")
    headers, rows = read_sheet(sheet_id, tab)
    missing = check_headers(headers)
    if missing:
        # A renamed header would otherwise publish an empty map. Keep the last good one.
        print(f"ERROR: tab '{tab}' is missing required column(s): {', '.join(missing)}. Nothing published.", file=sys.stderr)
        return 3
    print(f"  {len(rows)} rows")

    today = datetime.now(EASTERN).date()
    states = build_states(rows, today)
    data = build_payload(states, datetime.now(timezone.utc).isoformat(timespec="seconds"))
    counts = data["_meta"]["counts"]
    print(f"  {counts['opportunities']} opportunities in {counts['states']} states (as of {today}, Eastern)")

    if args.dry_run:
        print("Dry run — not writing.")
        print(serialize(data).decode("utf-8"))
        return 0

    # The gate is the content hash, not the bytes: generated_at changes every run.
    # On Civis the repo is freshly cloned, so the local file is what's on main.
    if data["_meta"]["content_hash"] == previous_hash():
        print("No content change — nothing written or published.")
        return 0

    payload = serialize(data)
    write_atomic(payload)
    print(f"Wrote {OUTPUT_JSON.relative_to(REPO_ROOT)}.")

    if args.push:
        repo = os.environ.get("GITHUB_REPO", DEFAULT_REPO)
        sha = publish_to_github(payload, repo)
        print(f"Pushed {sha[:7]} to {repo}." if sha else f"No push needed — {repo} already has identical content.")
    else:
        print("Skipped publish (no --push flag).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
