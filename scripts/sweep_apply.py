"""
sweep_apply.py — apply the training-map sweep's proposal to the Sheet, safely.

The agent writes tmp/sweep/proposal.json: the COMPLETE desired set of sweep
rows. This script is the only thing that writes them, and it enforces the
contract mechanically so a plausible-but-wrong proposal can't slip through:

  ownership   touches only rows with source = sweep. A key a human has taken
              over (listed in the worklist's staff_owned_keys) is refused.
  link rule   a state with a front door (column K, else protectthevote.net for
              PTV states) must link there. Otherwise the link must be one of
              that state's own training URLs or share their host.
  content     titles <= 60 chars with no year; descriptions 60-400 chars; no
              email, phone number, or hotline mention; http(s) links only.
  shrink      refuses to disable more than half the currently enabled sweep
              rows (when there are at least 4). The agent may never pass
              --allow-shrink; it exists for Rob.

Rows that leave the proposal are disabled (enabled = FALSE), never deleted.

Usage:
    python scripts/sweep_apply.py --dry-run     # validate + print the diff
    python scripts/sweep_apply.py               # apply
Exit codes: 0 ok (including "no change"), 2 config, 3 validation refused,
4 shrink guard, 5 sheet shape wrong.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sync_opportunities import STATES, as_text, is_http_url, normalize_row  # noqa: E402
from sweep_worklist import host  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
SWEEP_DIR = REPO_ROOT / "tmp" / "sweep"
EASTERN = ZoneInfo("America/New_York")

KEY_RE = re.compile(r"^(ptv|ext|door):([A-Z]{2}):[a-z0-9]+(?:-[a-z0-9]+)*$")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}")
HOTLINE_RE = re.compile(r"866|our[\s-]?vote|hotline", re.I)
YEAR_RE = re.compile(r"\b20\d\d\b")
FIELDS = ("state", "title", "description", "link", "enabled", "source", "key",
          "last updated", "updated by")


def validate(proposal: dict, worklist: dict) -> list[str]:
    errors = []
    staff = set(worklist.get("staff_owned_keys") or [])
    states = worklist["states"]
    seen = set()
    for i, r in enumerate(proposal.get("rows") or []):
        key = as_text(r.get("key"))
        where = f"proposal row {i} ({key or 'no key'})"
        m = KEY_RE.match(key)
        if not m:
            errors.append(f"{where}: key must look like ptv|ext|door:XX:role-slug")
            continue
        code = m.group(2)
        if key in seen:
            errors.append(f"{where}: duplicate key")
        seen.add(key)
        if key in staff:
            errors.append(f"{where}: key is staff-owned; the sweep may not recreate it")
        if code not in STATES or as_text(r.get("state")) != code:
            errors.append(f"{where}: state must be the USPS code in the key ({code})")
            continue
        title, desc, link = (as_text(r.get(f)) for f in ("title", "description", "link"))
        if not title or len(title) > 60 or YEAR_RE.search(title):
            errors.append(f"{where}: title must be 1-60 chars with no year")
        if not 60 <= len(desc) <= 400:
            errors.append(f"{where}: description must be 60-400 chars (got {len(desc)})")
        for text in (title, desc):
            if EMAIL_RE.search(text) or PHONE_RE.search(text):
                errors.append(f"{where}: no email addresses or phone numbers in copy")
            if HOTLINE_RE.search(text):
                errors.append(f"{where}: never mention the hotline (SPEC Q6)")
        if not is_http_url(link):
            errors.append(f"{where}: link is not http(s)")
            continue
        st = states[code]
        if st["front_door"]:
            if link != st["front_door"]:
                errors.append(f"{where}: {code} has a front door; link must be {st['front_door']}")
        else:
            urls = [t["url"] for ts in st["roles"].values() for t in ts]
            if link not in urls and host(link) not in {host(u) for u in urls}:
                errors.append(f"{where}: link is not one of {code}'s training pages or their host")
        if key.startswith("door:") and st["roles"]:
            errors.append(f"{where}: door: items are only for states with no trainings")
        if key.startswith("ptv:") and not st["ptv_state"]:
            errors.append(f"{where}: ptv: key for a state with no PTV trainings")
    return errors


def plan(proposal: dict, current: list[dict]) -> dict:
    by_key = {c["key"]: c for c in current if c["key"]}
    wanted = {as_text(r["key"]): r for r in proposal.get("rows") or []}
    create, update, disable = [], [], []
    for key, r in wanted.items():
        cur = by_key.get(key)
        if cur is None:
            create.append(r)
            continue
        changes = {f: as_text(r[f]) for f in ("state", "title", "description", "link")
                   if as_text(r[f]) != as_text(cur.get(f))}
        if cur.get("enabled", "").upper() == "FALSE":
            changes["enabled"] = "TRUE"
        if changes:
            update.append({"row": cur["row"], "key": key, "changes": changes})
    for key, cur in by_key.items():
        if key not in wanted and cur.get("enabled", "").upper() != "FALSE":
            disable.append({"row": cur["row"], "key": key})
    return {"create": create, "update": update, "disable": disable}


def shrink_refused(p: dict, current: list[dict]) -> bool:
    enabled = [c for c in current if c.get("enabled", "").upper() != "FALSE"]
    return len(enabled) >= 4 and len(p["disable"]) > len(enabled) / 2


def col_letter(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--allow-shrink", action="store_true", help="HUMAN ONLY. Out of contract for the sweep agent.")
    args = ap.parse_args()
    try:
        from dotenv import load_dotenv
        load_dotenv(REPO_ROOT / ".env")
    except ImportError:
        pass
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    tab = os.environ.get("GOOGLE_SHEET_TAB", "Opportunities")
    if not sheet_id:
        print("ERROR: GOOGLE_SHEET_ID not set", file=sys.stderr)
        return 2
    worklist = json.loads((SWEEP_DIR / "worklist.json").read_text(encoding="utf-8"))
    proposal = json.loads((SWEEP_DIR / "proposal.json").read_text(encoding="utf-8"))

    errors = validate(proposal, worklist)
    if errors:
        print("REFUSED — proposal failed validation; nothing written:", file=sys.stderr)
        for e in errors:
            print("  " + e, file=sys.stderr)
        return 3

    from ccef_connections import SheetsConnector
    with SheetsConnector() as conn:
        ws = conn.get_spreadsheet(sheet_id).worksheet(tab)
        headers = [h.strip().lower() for h in ws.row_values(1)]
        missing = [f for f in FIELDS if f not in headers]
        if missing:
            print(f"ERROR: tab '{tab}' lacks column(s) {missing}; nothing written.", file=sys.stderr)
            return 5
        col = {f: headers.index(f) + 1 for f in FIELDS}
        # Re-read the live sheet rather than trusting the worklist: a human may
        # have edited since it was built, and ownership is decided NOW.
        current = []
        for i, raw in enumerate(ws.get_all_records()):
            r = normalize_row(raw)
            if as_text(r.get("source")).lower() == "sweep":
                current.append({"row": i + 2, **{f: as_text(r.get(f)) for f in FIELDS}})
            elif as_text(r.get("key")) in {as_text(x["key"]) for x in proposal["rows"]}:
                print(f"REFUSED — key {r.get('key')} is now staff-owned (row {i + 2}); rebuild the worklist.", file=sys.stderr)
                return 3

        p = plan(proposal, current)
        print(f"create {len(p['create'])}, update {len(p['update'])}, disable {len(p['disable'])} "
              f"(current sweep rows {len(current)})")
        for r in p["create"]:
            print(f"  + {r['key']}: {r['title']}")
        for u in p["update"]:
            print(f"  ~ {u['key']}: {', '.join(u['changes'])}")
        for d in p["disable"]:
            print(f"  - {d['key']}")
        if shrink_refused(p, current) and not args.allow_shrink:
            print("REFUSED — would disable more than half the enabled sweep rows. Diagnose; Rob decides.", file=sys.stderr)
            return 4
        if args.dry_run or not any(p.values()):
            print("Dry run — nothing written." if args.dry_run else "No change.")
            return 0

        stamp = datetime.now(EASTERN).strftime("%Y-%m-%d %H:%M ET")
        cells = []
        for u in p["update"]:
            for f, v in {**u["changes"], "last updated": stamp, "updated by": "training-map sweep"}.items():
                cells.append({"range": f"{col_letter(col[f])}{u['row']}", "values": [[v]]})
        for d in p["disable"]:
            for f, v in {"enabled": "FALSE", "last updated": stamp, "updated by": "training-map sweep"}.items():
                cells.append({"range": f"{col_letter(col[f])}{d['row']}", "values": [[v]]})
        if cells:
            ws.batch_update(cells, value_input_option="RAW")
        if p["create"]:
            width = max(col.values())
            new_rows = []
            for r in p["create"]:
                row = [""] * width
                vals = {"state": r["state"], "title": r["title"], "description": r["description"],
                        "link": r["link"], "enabled": "TRUE", "source": "sweep", "key": r["key"],
                        "last updated": stamp, "updated by": "training-map sweep"}
                for f, v in vals.items():
                    row[col[f] - 1] = v
                new_rows.append(row)
            ws.append_rows(new_rows, value_input_option="RAW", table_range="A1")
    report = {"applied_at": stamp, "counts": {k: len(v) for k, v in p.items()},
              "keys": {k: [x["key"] for x in v] for k, v in p.items()}}
    (SWEEP_DIR / "apply_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Applied. {report['counts']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
