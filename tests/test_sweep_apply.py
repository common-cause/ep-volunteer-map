"""Tests for the sweep's mechanical guards. All data is fabricated."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sweep_apply as a  # noqa: E402
import sweep_worklist as w  # noqa: E402

DESC = "Spend a shift at a polling place helping voters and watching for problems. Training is online."


def worklist():
    payload = {"_meta": {}, "states": {
        "AZ": [{"role": "2026 Poll Monitor", "url": "https://app.protectthevote.net/volunteer/trainings/1"}],
        "TX": [{"role": "Poll Monitoring", "url": "https://www.mobilize.us/commoncause/event/9"}],
        "VA": [{"role": "Poll Monitor", "url": "https://www.example.org/sign-up"}],
    }}
    return w.build_worklist(payload, sheet_rows=[
        {"State": "OH", "Title": "Staff row", "Link": "https://x.org", "Source": "", "Key": "ext:OH:taken"},
    ], k_links={"VA": "https://www.example.org/", "AL": "https://al.example.org/quiz"})


def row(key, state, link, title="Poll Monitor", desc=DESC):
    return {"key": key, "state": state, "title": title, "description": desc, "link": link}


def errs(*rows):
    return a.validate({"rows": list(rows)}, worklist())


def test_worklist_front_doors():
    s = worklist()["states"]
    assert s["AZ"]["front_door"] == "https://protectthevote.net/" and s["AZ"]["ptv_state"]
    assert s["VA"]["front_door"] == "https://www.example.org/"      # K beats everything
    assert s["AL"]["front_door"] == "https://al.example.org/quiz" and not s["AL"]["roles"]
    assert s["TX"]["front_door"] is None and s["TX"]["agent_picks_link"]
    assert worklist()["staff_owned_keys"] == ["ext:OH:taken"]


def test_normalize_link():
    assert w.normalize_link("protectthevote.net") == "https://protectthevote.net"
    assert w.normalize_link("javascript:alert(1)") is None
    assert w.normalize_link("") is None


def test_valid_rows_pass():
    assert errs(row("ptv:AZ:poll-monitor", "AZ", "https://protectthevote.net/"),
                row("ext:TX:poll-monitor", "TX", "https://www.mobilize.us/commoncause/event/9"),
                row("door:AL:volunteer", "AL", "https://al.example.org/quiz")) == []


def test_front_door_is_enforced():
    assert any("front door" in e for e in errs(
        row("ptv:AZ:poll-monitor", "AZ", "https://app.protectthevote.net/volunteer/trainings/1")))
    assert any("front door" in e for e in errs(row("ext:VA:poll-monitor", "VA", "https://www.example.org/sign-up")))


def test_agent_link_must_be_the_states_own():
    assert any("training pages" in e for e in errs(row("ext:TX:poll-monitor", "TX", "https://evil.example/")))
    assert errs(row("ext:TX:poll-monitor", "TX", "https://www.mobilize.us/commoncause/event/10")) == []


def test_content_rules():
    assert any("year" in e for e in errs(row("ptv:AZ:x", "AZ", "https://protectthevote.net/", title="2026 Poll Monitor")))
    assert any("60-400" in e for e in errs(row("ptv:AZ:x", "AZ", "https://protectthevote.net/", desc="Too short.")))
    for bad in ("Call 555-123-4567 to learn more about monitoring polling places in your county.",
                "Email someone@example.org to learn more about monitoring polling places in your area.",
                "Volunteers may also staff the 866-OUR-VOTE hotline from anywhere in the state today."):
        assert errs(row("ptv:AZ:x", "AZ", "https://protectthevote.net/", desc=bad)), bad


def test_ownership_and_keys():
    assert any("staff-owned" in e for e in errs(row("ext:OH:taken", "OH", "https://x.org")))
    assert any("key must" in e for e in errs(row("AZ poll monitor", "AZ", "https://protectthevote.net/")))
    assert any("duplicate" in e for e in errs(row("ptv:AZ:a", "AZ", "https://protectthevote.net/"),
                                              row("ptv:AZ:a", "AZ", "https://protectthevote.net/")))
    assert any("state must" in e for e in errs(row("ptv:AZ:a", "TX", "https://protectthevote.net/")))
    assert any("no PTV" in e for e in errs(row("ptv:TX:a", "TX", "https://www.mobilize.us/commoncause/event/9")))
    assert any("door:" in e for e in errs(row("door:AZ:volunteer", "AZ", "https://protectthevote.net/")))


def test_plan_create_update_disable_reenable():
    current = [
        {"row": 5, "key": "ptv:AZ:a", "state": "AZ", "title": "Poll Monitor", "description": DESC, "link": "L", "enabled": "TRUE"},
        {"row": 6, "key": "ptv:AZ:b", "state": "AZ", "title": "Old", "description": DESC, "link": "L", "enabled": "TRUE"},
        {"row": 7, "key": "ptv:AZ:c", "state": "AZ", "title": "Gone", "description": DESC, "link": "L", "enabled": "TRUE"},
        {"row": 8, "key": "ptv:AZ:d", "state": "AZ", "title": "Back", "description": DESC, "link": "L", "enabled": "FALSE"},
    ]
    proposal = {"rows": [
        {"key": "ptv:AZ:a", "state": "AZ", "title": "Poll Monitor", "description": DESC, "link": "L"},
        {"key": "ptv:AZ:b", "state": "AZ", "title": "New", "description": DESC, "link": "L"},
        {"key": "ptv:AZ:d", "state": "AZ", "title": "Back", "description": DESC, "link": "L"},
        {"key": "ptv:AZ:e", "state": "AZ", "title": "Fresh", "description": DESC, "link": "L"},
    ]}
    p = a.plan(proposal, current)
    assert [r["key"] for r in p["create"]] == ["ptv:AZ:e"]
    assert {u["key"]: u["changes"] for u in p["update"]} == {"ptv:AZ:b": {"title": "New"}, "ptv:AZ:d": {"enabled": "TRUE"}}
    assert [d["key"] for d in p["disable"]] == ["ptv:AZ:c"]
    assert not a.shrink_refused(p, current)


def test_shrink_guard():
    current = [{"row": i, "key": f"ptv:AZ:k{i}", "enabled": "TRUE"} for i in range(6)]
    p = a.plan({"rows": []}, current)
    assert len(p["disable"]) == 6 and a.shrink_refused(p, current)
    assert not a.shrink_refused(a.plan({"rows": []}, current[:3]), current[:3])  # under 4: no guard


def test_col_letter():
    assert [a.col_letter(n) for n in (1, 10, 26, 27)] == ["A", "J", "Z", "AA"]
