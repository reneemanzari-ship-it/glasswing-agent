"""The 12-initiative golden set (GLASSWING_SPEC.md section 3, Week 2 item
6): classification of every fixture must match its golden expected file
exactly on tier, citation set, and human_review_required per framework,
plus the new NYC LL144 dimension.

Runs fully offline against glasswing.engines.classification -- no
network, no API key (see GLASSWING_OFFLINE marker below).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from glasswing.engines.classification import classify_initiative, classify_nyc_ll144
from schemas.initiative import Initiative

FIXTURES_DIR = Path(__file__).parent / "fixtures"

SLUGS = sorted(
    p.stem.removesuffix(".input_initiative")
    for p in FIXTURES_DIR.glob("*.input_initiative.json")
)


def _load_initiative(slug: str) -> Initiative:
    path = FIXTURES_DIR / f"{slug}.input_initiative.json"
    return Initiative(**json.loads(path.read_text(encoding="utf-8")))


def _load_expected(slug: str) -> dict:
    path = FIXTURES_DIR / f"{slug}.expected.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.skipif(
    os.environ.get("GLASSWING_OFFLINE") != "1",
    reason="run with GLASSWING_OFFLINE=1 to prove no network/API key is needed",
)
def test_golden_suite_runs_fully_offline() -> None:
    """Marker test proving this module needs neither network nor an API
    key under GLASSWING_OFFLINE=1 (GLASSWING_SPEC.md Week 2 acceptance).
    The real proof is that the whole module collects and passes with
    pytest-socket's --disable-socket active (see tests/conftest.py); this
    assertion just gives that a nameable, always-passing anchor."""
    initiative = _load_initiative(SLUGS[0])
    assert classify_initiative(initiative) is not None


@pytest.mark.parametrize("slug", SLUGS)
def test_fixture_matches_golden_expected(slug: str) -> None:
    initiative = _load_initiative(slug)
    expected = _load_expected(slug)

    profile = classify_initiative(initiative)
    ll144 = classify_nyc_ll144(initiative)

    eu = profile.classifications.eu_ai_act
    nist = profile.classifications.nist_ai_rmf
    co = profile.classifications.colorado_sb_205
    expected_nist = expected["nist_ai_rmf"]
    expected_co = expected["colorado_sb_205"]
    expected_ll144 = expected["nyc_ll144"]

    assert eu.tier.value == expected["eu_ai_act"]["tier"], slug
    assert eu.citations == expected["eu_ai_act"]["citations"], slug
    if "confidence" in expected["eu_ai_act"]:
        assert eu.confidence == expected["eu_ai_act"]["confidence"], slug

    assert nist.govern_attention.value == expected_nist["govern_attention"], slug
    assert nist.map_attention.value == expected_nist["map_attention"], slug
    assert nist.measure_attention.value == expected_nist["measure_attention"], slug
    assert nist.manage_attention.value == expected_nist["manage_attention"], slug

    assert co.applicable == expected_co["applicable"], slug
    assert co.high_risk_category == expected_co["high_risk_category"], slug

    assert profile.overall_risk_tier.value == expected["overall_risk_tier"], slug
    assert profile.human_review_required == expected["human_review_required"], slug
    if "human_review_reasons" in expected:
        assert profile.human_review_reasons == expected["human_review_reasons"], slug

    assert ll144.applicable == expected_ll144["applicable"], slug
    if "requires_bias_audit" in expected_ll144:
        assert ll144.requires_bias_audit == expected_ll144["requires_bias_audit"], slug


def test_golden_set_covers_all_four_eu_ai_act_tiers() -> None:
    tiers = {
        classify_initiative(_load_initiative(slug)).classifications.eu_ai_act.tier.value
        for slug in SLUGS
    }
    assert tiers == {"prohibited", "high_risk", "limited_risk", "minimal_risk"}


def test_golden_set_covers_ll144_triggering_and_non_triggering_hiring_cases() -> None:
    results = {
        slug: classify_nyc_ll144(_load_initiative(slug)).applicable for slug in SLUGS
    }
    assert results["06_ll144_triggering_nyc_aedt"] is True
    assert results["07_ll144_non_triggering_no_nyc_nexus"] is False


def test_golden_set_covers_sb205_consequential_decision_cases() -> None:
    applicable_categories = {
        classify_initiative(_load_initiative(slug)).classifications.colorado_sb_205.high_risk_category
        for slug in SLUGS
    } - {None}
    assert {"financial_lending", "employment"}.issubset(applicable_categories)
