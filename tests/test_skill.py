"""
Tests for the packaged AI Risk Tier Classification skill
(skills/ai_risk_tier_classification/). Verifies the skill works standalone
(imported directly, not just through the Risk Classifier Agent), that its
four example inputs produce the classifications they document, that the
CLI entry point works end to end, and that the skill's output matches the
full agent's output on the same input (they must share the same
underlying logic, not diverge into a fork).
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from schemas.initiative import Initiative
from schemas.risk_profile import EUAIActTier
from skills.ai_risk_tier_classification.scripts.classifier import AIRiskTierClassificationSkill
from agents.risk_classifier import RiskClassifierAgent

REPO_ROOT = Path(__file__).parent.parent
EXAMPLES_DIR = REPO_ROOT / "skills" / "ai_risk_tier_classification" / "examples"
EXAMPLE_FILES = [
    "example_high_risk_loan.json",
    "example_low_risk_marketing.json",
    "example_limited_risk_chatbot.json",
    "example_ambiguous_hiring.json",
]


def _load_example(filename: str) -> dict:
    with open(EXAMPLES_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)


def test_skill_invoked_standalone():
    """The skill can be imported and called directly, without going through
    the orchestrator or any agent."""
    skill = AIRiskTierClassificationSkill()
    initiative = Initiative(**_load_example("example_high_risk_loan.json")["input_initiative"])
    profile = skill.classify(initiative)
    assert profile.classifications.eu_ai_act.tier == EUAIActTier.HIGH_RISK


def test_skill_classify_from_description_runs_extraction_first():
    """classify_from_description() must build a real Initiative (not skip
    straight to a canned answer) and correctly reflect the resulting
    intake uncertainty rather than asserting false confidence."""
    skill = AIRiskTierClassificationSkill()
    profile = skill.classify_from_description(
        "Autonomous credit scoring system that approves consumer loans without human review."
    )
    assert profile.classifications.eu_ai_act.tier == EUAIActTier.HIGH_RISK
    # HITL plan can't be determined from bare text, so the skill must not
    # assert unwarranted confidence -- see local_classify's ambiguous-intake
    # handling.
    assert profile.human_review_required is True


@pytest.mark.parametrize("filename", EXAMPLE_FILES)
def test_example_matches_expected_classification(filename):
    example = _load_example(filename)
    initiative = Initiative(**example["input_initiative"])
    expected = example["expected_risk_profile"]

    profile = AIRiskTierClassificationSkill().classify(initiative)
    eu = profile.classifications.eu_ai_act
    nist = profile.classifications.nist_ai_rmf
    co = profile.classifications.colorado_sb_205

    assert eu.tier.value == expected["eu_ai_act"]["tier"]
    if "citation_contains" in expected["eu_ai_act"]:
        assert any(expected["eu_ai_act"]["citation_contains"] in c for c in eu.citations)
    if "min_confidence" in expected["eu_ai_act"]:
        assert eu.confidence >= expected["eu_ai_act"]["min_confidence"]
    if "max_confidence" in expected["eu_ai_act"]:
        assert eu.confidence <= expected["eu_ai_act"]["max_confidence"]

    for field, value in expected.get("nist_ai_rmf", {}).items():
        assert getattr(nist, field).value == value

    co_expected = expected.get("colorado_sb_205", {})
    if "applicable" in co_expected:
        assert co.applicable == co_expected["applicable"]
    if "high_risk_category" in co_expected:
        assert co.high_risk_category == co_expected["high_risk_category"]

    assert profile.overall_risk_tier.value == expected["overall_risk_tier"]
    assert profile.human_review_required == expected["human_review_required"]


def test_cli_invocation():
    """python -m skills.ai_risk_tier_classification --input <file> runs end
    to end and prints a valid RiskProfile JSON to stdout."""
    example_path = EXAMPLES_DIR / "example_high_risk_loan.json"
    result = subprocess.run(
        [sys.executable, "-m", "skills.ai_risk_tier_classification", "--input", str(example_path)],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["classifications"]["eu_ai_act"]["tier"] == "high_risk"
    assert output["classifications"]["colorado_sb_205"]["high_risk_category"] == "financial_lending"


def test_cli_invocation_with_freeform_description():
    """python -m skills.ai_risk_tier_classification --description "..." also
    runs end to end."""
    result = subprocess.run(
        [sys.executable, "-m", "skills.ai_risk_tier_classification", "--description",
         "AI chatbot answering customer product questions"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert "overall_risk_tier" in output


@pytest.mark.parametrize("filename", EXAMPLE_FILES)
def test_skill_output_matches_full_agent_output(filename):
    """Regression test: the standalone skill must produce the same
    classification as the full Risk Classifier Agent (offline path) on the
    same input. This is what proves the skill packages the existing logic
    rather than forking a divergent copy of it."""
    example = _load_example(filename)
    initiative = Initiative(**example["input_initiative"])

    skill_profile = AIRiskTierClassificationSkill().classify(initiative)
    agent_profile = RiskClassifierAgent().classify_initiative(initiative)

    assert skill_profile.classifications.eu_ai_act.tier == agent_profile.classifications.eu_ai_act.tier
    assert skill_profile.classifications.eu_ai_act.confidence == agent_profile.classifications.eu_ai_act.confidence
    assert skill_profile.classifications.nist_ai_rmf.govern_attention == agent_profile.classifications.nist_ai_rmf.govern_attention
    assert skill_profile.classifications.nist_ai_rmf.map_attention == agent_profile.classifications.nist_ai_rmf.map_attention
    assert skill_profile.classifications.nist_ai_rmf.measure_attention == agent_profile.classifications.nist_ai_rmf.measure_attention
    assert skill_profile.classifications.nist_ai_rmf.manage_attention == agent_profile.classifications.nist_ai_rmf.manage_attention
    assert skill_profile.classifications.colorado_sb_205.applicable == agent_profile.classifications.colorado_sb_205.applicable
    assert skill_profile.classifications.colorado_sb_205.high_risk_category == agent_profile.classifications.colorado_sb_205.high_risk_category
    assert skill_profile.overall_risk_tier == agent_profile.overall_risk_tier
    assert skill_profile.human_review_required == agent_profile.human_review_required
