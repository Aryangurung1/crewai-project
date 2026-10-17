"""Tests for the deterministic layer (no LLM, no API key needed)."""

from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from astro.ganita import compute_chart
from astro.shastra import load_rules, match_rules
from guardrails import check_question, evidence_guardrail, safety_guardrail
from tools import SESSION

ON = datetime(2026, 10, 17, tzinfo=ZoneInfo("UTC"))
CHART = compute_chart("2000-01-01", "17:45", 27.7172, 85.3240, "Asia/Kathmandu", on=ON)


def test_sun_position_matches_ephemeris():
    # Sidereal Sun on 1 Jan 2000 is ~16.5 degrees Sagittarius.
    assert CHART["planets"]["Sun"]["sign"] == "Sagittarius"
    assert abs(CHART["planets"]["Sun"]["degree"] - 16.5) < 0.5


def test_dasha_sequence():
    # Moon in Swati (Rahu) -> Jupiter -> Saturn mahadasha running in 2026.
    assert CHART["nakshatra"] == "Swati"
    assert CHART["dasha"]["mahadasha"] == "Saturn"


def test_rule_ids_unique_and_matching_is_deterministic():
    ids = [r["id"] for r in load_rules()]
    assert len(ids) == len(set(ids))
    assert match_rules(CHART, "career") == match_rules(CHART, "career")
    assert "R-GEN-01" in [m["rule_id"] for m in match_rules(CHART, "career")]  # Gaja Kesari


def test_input_guardrail():
    assert check_question("When will I die?")[0] is False
    assert check_question("Will I win my court case?")[0] is False
    assert check_question("Should I take the Japan job offer?")[0] is True


def test_evidence_guardrail_rejects_invented_rules():
    SESSION["matched_rule_ids"] = {"R-CAR-01"}
    assert evidence_guardrail(SimpleNamespace(raw="Good career [R-CAR-01]"))[0] is True
    assert evidence_guardrail(SimpleNamespace(raw="Good career [R-CAR-09]"))[0] is False
    assert evidence_guardrail(SimpleNamespace(raw="Good career."))[0] is False


def test_safety_guardrail():
    assert safety_guardrail(SimpleNamespace(raw="A steady period [R-DAS-SAT]"))[0] is True
    assert safety_guardrail(SimpleNamespace(raw="You will face an accident [R-DAS-SAT]"))[0] is False
    assert safety_guardrail(SimpleNamespace(raw="Buy a blue sapphire gemstone [R-DAS-SAT]"))[0] is False
    assert safety_guardrail(SimpleNamespace(raw="This is guaranteed [R-DAS-SAT]"))[0] is False
