"""v0.1 parity check (GLASSWING_SPEC.md section 3, Week 2 acceptance):
"For the v0.1-representable subset, output is parity-equal with the
frozen pre-migration fixtures."

tests/golden/v0.1_parity/*.v0.1_output.json were captured by running the
untouched v0.1 skill (a one-shot script, since deleted, per its own
docstring) BEFORE glasswing/engines/classification.py existed -- see
DECISIONS.md for why capture-before-migrate is the only order that makes
this test meaningful.

Compares classification-content fields only (tier, citations, confidence,
per-function NIST attention, SB 205 applicability/category,
overall_risk_tier, human_review_required/reasons) -- not bookkeeping
metadata (risk_profile_id, initiative_id, created_at,
classifier_agent_version, model_id). Those are *expected* to differ: v0.1
stamped a live-LLM model_id even in its offline fallback path, which was
never true (CLAUDE.md invariant #1); the migrated engine correctly
records its own engine_version/model_id instead (DECISIONS.md D-012).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from glasswing.engines.classification import classify_initiative
from schemas.initiative import Initiative

FIXTURES_DIR = Path(__file__).parent / "fixtures"
PARITY_DIR = Path(__file__).parent / "v0.1_parity"

PARITY_SLUGS = sorted(
    p.stem.removesuffix(".v0.1_output") for p in PARITY_DIR.glob("*.v0.1_output.json")
)


def _load_initiative(slug: str) -> Initiative:
    path = FIXTURES_DIR / f"{slug}.input_initiative.json"
    return Initiative(**json.loads(path.read_text(encoding="utf-8")))


def _load_frozen_v0_1_output(slug: str) -> dict:
    path = PARITY_DIR / f"{slug}.v0.1_output.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_parity_subset_is_not_empty() -> None:
    """If this is ever empty, the freeze script didn't run, or ran after
    the migration -- either way the parity test below would be vacuous."""
    assert len(PARITY_SLUGS) >= 10


@pytest.mark.parametrize("slug", PARITY_SLUGS)
def test_migrated_engine_matches_frozen_v0_1_output(slug: str) -> None:
    initiative = _load_initiative(slug)
    frozen = _load_frozen_v0_1_output(slug)
    frozen_c = frozen["classifications"]
    frozen_nist = frozen_c["nist_ai_rmf"]
    frozen_co = frozen_c["colorado_sb_205"]

    new_profile = classify_initiative(initiative)
    new_eu = new_profile.classifications.eu_ai_act
    new_nist = new_profile.classifications.nist_ai_rmf
    new_co = new_profile.classifications.colorado_sb_205

    assert new_eu.tier.value == frozen_c["eu_ai_act"]["tier"], slug
    assert new_eu.citations == frozen_c["eu_ai_act"]["citations"], slug
    assert new_eu.confidence == frozen_c["eu_ai_act"]["confidence"], slug

    assert new_nist.govern_attention.value == frozen_nist["govern_attention"], slug
    assert new_nist.map_attention.value == frozen_nist["map_attention"], slug
    assert new_nist.measure_attention.value == frozen_nist["measure_attention"], slug
    assert new_nist.manage_attention.value == frozen_nist["manage_attention"], slug
    assert new_nist.confidence == frozen_nist["confidence"], slug

    assert new_co.applicable == frozen_co["applicable"], slug
    assert new_co.high_risk_category == frozen_co.get("high_risk_category"), slug
    assert new_co.confidence == frozen_co["confidence"], slug

    assert new_profile.overall_risk_tier.value == frozen["overall_risk_tier"], slug
    assert new_profile.human_review_required == frozen["human_review_required"], slug
    assert new_profile.human_review_reasons == frozen["human_review_reasons"], slug
