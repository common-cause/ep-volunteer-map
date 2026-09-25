"""
sweep_worklist.py — gather the inputs for the training-map sweep into one file.

The sweep (docs/SPEC.md "Phase 2"; runbook .claude/skills/training-map-sweep)
is a judgment pass: an agent groups roles and writes public copy. This script
does everything that ISN'T judgment, so the agent works from one reviewed,
public-safe document:

  - the EP Training Map's PUBLIC payload (already allowlisted by
    ep-training-map; no Zoom links, no host emails)
  - column K "Recruitment Link - General" of the coalition plan's
    In-Depth Landscape tab (state recruitment front doors). Columns A and K
    ONLY; the tab also holds state leads and partners, which are never read.
  - the sweep's own current rows in the volunteer-map Sheet (source = sweep),
    plus the KEYS of staff-owned rows, so the agent can reuse keys and keep
    approved copy stable

and precomputes the mechanical part of the link rule: a state's front door is
its column K link, else protectthevote.net if it runs PTV trainings. Only
states with neither need the agent to pick a link.

Usage:
    python scripts/sweep_worklist.py            # -> tmp/sweep/worklist.json
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sync_opportunities import STATES, is_http_url, normalize_row, parse_state, as_text  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT = REPO_ROOT / "tmp" / "sweep" / "worklist.json"

TRAINING_PAYLOAD_URL = "https://common-cause.github.io/ep-training-map-public/trainings.json"
COALITION_TAB = "In-Depth Landscape"
PTV_SIGNUP = "https://protectthevote.net/"
PTV_HOST = "app.protectthevote.net"


def host(url: str) -> str:
    m = re.match(r"^https?://([^/?#:]+)", url or "", re.I)
    return m.group(1).lower() if m else ""


def normalize_link(value) -> str | None:
    """A column K cell as a usable URL. Bare 'protectthevote.net' gets https://."""
    text = as_text(value)
    if not text:
        return None
    if not re.match(r"^[a-z][a-z0-9+.\-]*:", text, re.I):
        text = "https://" + text
    return text if is_http_url(text) else None


def fetch_training_payload() -> dict:
    with urllib.request.urlopen(TRAINING_PAYLOAD_URL, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def read_sheets(sheet_id: str, tab: str, coalition_id: str) -> tuple[list[dict], dict[str, str]]:
    from ccef_connections import SheetsConnector

    with SheetsConnector() as conn:
        rows = conn.get_spreadsheet(sheet_id).worksheet(tab).get_all_records()
        ws = conn.get_spreadsheet(coalition_id).worksheet(COALITION_TAB)
        # Two columns, fetched separately so no other column is ever requested.
        col_a = ws.col_values(1)
        col_k = ws.col_values(11)
    header_k = (col_k[0] if col_k else "").strip().lower()
    if not header_k.startswith("recruitment link - general"):
        raise SystemExit(f"ERROR: coalition sheet column K header is {col_k[:1]!r}, "
                         "not 'Recruitment Link - General'. The sheet changed shape; stop.")
    k_links = {}
    for i, name in enumerate(col_a[1:], start=1):
        code = parse_state(as_text(name))
        link = normalize_link(col_k[i] if i < len(col_k) else "")
        if code and link:
            k_links[code] = link
    return rows, k_links


def build_worklist(payload: dict, sheet_rows: list[dict], k_links: dict[str, str]) -> dict:
    trainings = payload.get("states") or {}
    sweep_rows, staff_keys, staff_states = [], [], set()
    for i, raw in enumerate(sheet_rows):
        r = normalize_row(raw)
        src, key = as_text(r.get("source")).lower(), as_text(r.get("key"))
        if src == "sweep":
            sweep_rows.append({"row": i + 2, "key": key, "state": as_text(r.get("state")),
                               "title": as_text(r.get("title")),
                               "description": as_text(r.get("description")),
                               "link": as_text(r.get("link")),
                               "enabled": as_text(r.get("enabled"))})
        elif any(as_text(r.get(c)) for c in ("state", "title", "link")):
            if key:
                staff_keys.append(key)   # taken over from the sweep; never recreate
            code = parse_state(as_text(r.get("state")))
            if code:
                staff_states.add(code)

    states = {}
    for code, name in STATES.items():
        items = trainings.get(code) or []
        ptv = any(host(t.get("url", "")) == PTV_HOST for t in items)
        front_door = k_links.get(code) or (PTV_SIGNUP if ptv else None)
        roles = defaultdict(list)
        for t in items:
            roles[as_text(t.get("role")) or "(no role given)"].append({
                "name": t.get("name"),
                "source": "ptv" if host(t.get("url", "")) == PTV_HOST else host(t.get("url", "")),
                "url": t.get("url"),
                "modality": t.get("modality"),
                "on_demand": bool(t.get("on_demand")),
                "next_date": min((s.get("date") for s in t.get("sessions") or [] if s.get("date")), default=None),
                "n_sessions": len(t.get("sessions") or []),
            })
        states[code] = {
            "name": name,
            "ptv_state": ptv,
            "k_link": k_links.get(code),
            "front_door": front_door,
            "agent_picks_link": bool(items) and front_door is None,
            "has_staff_rows": code in staff_states,
            "roles": dict(roles),
        }

    return {
        "_meta": {
            "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "training_payload_generated_at": (payload.get("_meta") or {}).get("generated_at"),
            "training_counts": (payload.get("_meta") or {}).get("counts"),
            "ptv_signup": PTV_SIGNUP,
            "n_k_links": len(k_links),
        },
        "states": states,
        "current_sweep_rows": sweep_rows,
        "staff_owned_keys": staff_keys,
    }


def main() -> int:
    try:
        from dotenv import load_dotenv
        load_dotenv(REPO_ROOT / ".env")
    except ImportError:
        pass
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    coalition_id = os.environ.get("COALITION_PLAN_SHEET_ID")
    tab = os.environ.get("GOOGLE_SHEET_TAB", "Opportunities")
    if not sheet_id or not coalition_id:
        print("ERROR: GOOGLE_SHEET_ID and COALITION_PLAN_SHEET_ID must be set", file=sys.stderr)
        return 2

    payload = fetch_training_payload()
    rows, k_links = read_sheets(sheet_id, tab, coalition_id)
    wl = build_worklist(payload, rows, k_links)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(wl, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    s = wl["states"]
    with_roles = [c for c, v in s.items() if v["roles"]]
    print(f"Wrote {OUT.relative_to(REPO_ROOT)}")
    print(f"  training payload generated_at {wl['_meta']['training_payload_generated_at']}")
    print(f"  states with trainings: {len(with_roles)}  (PTV {sum(s[c]['ptv_state'] for c in with_roles)})")
    print(f"  column K links: {len(k_links)}  ({', '.join(sorted(k_links))})")
    print(f"  agent picks link: {', '.join(c for c in with_roles if s[c]['agent_picks_link']) or 'none'}")
    print(f"  current sweep rows: {len(wl['current_sweep_rows'])}; staff-owned keys: {len(wl['staff_owned_keys'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
