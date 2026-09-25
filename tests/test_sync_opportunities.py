"""Tests for the pure parts of scripts/sync_opportunities.py. Rows are fabricated."""

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sync_opportunities as s  # noqa: E402

TODAY = date(2026, 10, 15)


def row(**kw):
    base = {"State": "Ohio", "Title": "Poll monitor", "Description": "Watch the polls.",
            "Link": "https://example.org/signup", "Enabled": "", "Ends": "",
            "Last Updated": "10/1/2026", "Updated By": "someone"}
    base.update(kw)
    return base


def build(*rows):
    return s.build_states(list(rows), TODAY)


def test_basic_row_keyed_by_usps_with_allowlisted_fields():
    assert build(row()) == {"OH": [{"title": "Poll monitor", "description": "Watch the polls.",
                                    "link": "https://example.org/signup"}]}


@pytest.mark.parametrize("value", ["OH", "oh", "Ohio", " ohio ", "OHIO"])
def test_state_name_or_code(value):
    assert list(build(row(State=value))) == ["OH"]


@pytest.mark.parametrize("value", ["DC", "D.C.", "District of Columbia", "Washington DC",
                                   "Washington, D.C."])
def test_dc_forms(value):
    assert list(build(row(State=value))) == ["DC"]


def test_washington_is_the_state():
    assert list(build(row(State="Washington"))) == ["WA"]


@pytest.mark.parametrize("value", ["National", "ALL", "US", "Puerto Rico", "Ohioo"])
def test_unknown_state_skipped_with_warning(value, capsys):
    assert build(row(State=value)) == {}
    assert "unknown state" in capsys.readouterr().err


def test_sheet_order_preserved_within_state_and_states_sorted():
    out = build(row(State="TX", Title="b"), row(Title="z"), row(Title="a"), row(State="AZ"))
    assert list(out) == ["AZ", "OH", "TX"]
    assert [o["title"] for o in out["OH"]] == ["z", "a"]


@pytest.mark.parametrize("value", ["FALSE", "false", "No", "0"])
def test_enabled_false_hides(value):
    assert build(row(Enabled=value)) == {}


@pytest.mark.parametrize("value", ["", "TRUE", "yes"])
def test_enabled_blank_or_true_shows(value):
    assert list(build(row(Enabled=value))) == ["OH"]


def test_blank_row_skipped_silently(capsys):
    assert build(row(State="", Title="", Description="", Link="")) == {}
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("field", ["Title", "Description", "Link"])
def test_missing_required_field_warns(field, capsys):
    assert build(row(**{field: ""})) == {}
    assert "missing" in capsys.readouterr().err


@pytest.mark.parametrize("link", ["javascript:alert(1)", "data:text/html,x", "example.org",
                                  "ftp://example.org", "https://", "https://ex ample.org",
                                  "Sign up here"])
def test_non_http_links_refused(link, capsys):
    assert build(row(Link=link)) == {}
    assert "http(s)" in capsys.readouterr().err


def test_http_and_mixed_case_scheme_accepted():
    assert list(build(row(Link="HTTP://example.org/x?a=1#b"))) == ["OH"]


@pytest.mark.parametrize("ends", ["2026-10-15", "10/15/2026", "10/15/26", "October 15, 2026",
                                  "Oct 15, 2026", 46310])
def test_ends_today_still_shown_and_normalized(ends):
    out = build(row(Ends=ends))
    assert out["OH"][0]["ends"] == "2026-10-15"


def test_ends_yesterday_dropped_silently(capsys):
    assert build(row(Ends="2026-10-14")) == {}
    assert capsys.readouterr().err == ""


def test_unreadable_ends_fails_visible_not_open(capsys):
    assert build(row(Ends="after the election")) == {}
    assert "isn't a date" in capsys.readouterr().err


def test_numericised_title_is_text():
    assert build(row(Title=2026))["OH"][0]["title"] == "2026"


def test_description_paragraphs_collapse():
    out = build(row(Description="one  \r\n \n\n\ntwo\n three"))
    assert out["OH"][0]["description"] == "one\n\ntwo\nthree"


def test_contact_details_are_not_filtered():
    # Rob, 2026-09-25: states publish what they choose.
    desc = "Email organizer@example.org or call 555-0100."
    assert build(row(Description=desc))["OH"][0]["description"] == desc


def test_check_headers():
    assert s.check_headers(["State", " TITLE ", "description", "Link", "ends"]) == []
    assert s.check_headers(["state", "headline", "description", "url"]) == ["title", "link"]
    assert s.check_headers([]) == list(s.REQUIRED_COLUMNS)


def test_hash_ignores_generated_at_and_tracks_content():
    states = build(row())
    a = s.build_payload(states, "2026-10-15T11:00:00+00:00")
    b = s.build_payload(states, "2026-10-15T19:00:00+00:00")
    assert a["_meta"]["content_hash"] == b["_meta"]["content_hash"]
    c = s.build_payload(build(row(Title="changed")), "x")
    assert c["_meta"]["content_hash"] != a["_meta"]["content_hash"]
    assert a["_meta"]["counts"] == {"states": 1, "opportunities": 1}


def test_expiry_changes_hash_so_the_dropping_run_publishes():
    before = s.content_hash(s.build_states([row(Ends="2026-10-15")], date(2026, 10, 15)))
    after = s.content_hash(s.build_states([row(Ends="2026-10-15")], date(2026, 10, 16)))
    assert before != after
