"""glasswing/engines/questionnaire.py: deterministic branching and field
mapping (GLASSWING_SPEC.md section 3, Week 3).

Exercised entirely against tests/fixtures/questionnaires/sample_intake_v0.yaml,
which is engine test scaffolding only -- never a client deliverable.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from glasswing.engines.questionnaire import (
    QuestionnaireValidationError,
    active_question_sequence,
    build_initiative_and_evidence_fields,
    load_questionnaire,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "questionnaires"
QUESTIONNAIRE_PATH = FIXTURES_DIR / "sample_intake_v0.yaml"


def _load_answers(filename: str) -> dict:
    return yaml.safe_load((FIXTURES_DIR / filename).read_text(encoding="utf-8"))


def test_lending_path_unlocks_lending_questions_not_chatbot_questions():
    questionnaire = load_questionnaire(QUESTIONNAIRE_PATH)
    answers = _load_answers("sample_answers.yaml")

    active = active_question_sequence(questionnaire, answers)

    assert "q_lending_details" in active
    assert "q_chatbot_details" not in active


def test_chatbot_path_unlocks_chatbot_questions_not_lending_questions():
    questionnaire = load_questionnaire(QUESTIONNAIRE_PATH)
    answers = _load_answers("sample_answers_chatbot.yaml")

    active = active_question_sequence(questionnaire, answers)

    assert "q_chatbot_details" in active
    assert "q_lending_details" not in active


def test_the_two_paths_genuinely_diverge_not_just_a_filtered_common_list():
    """The two paths' active question sets differ by their branch-specific
    question, not merely by which happen to have answers -- proving this
    is real branching, not a fixed list post-filtered."""
    questionnaire = load_questionnaire(QUESTIONNAIRE_PATH)
    lending_active = set(
        active_question_sequence(questionnaire, _load_answers("sample_answers.yaml"))
    )
    chatbot_active = set(
        active_question_sequence(
            questionnaire, _load_answers("sample_answers_chatbot.yaml")
        )
    )

    assert lending_active - chatbot_active == {"q_lending_details"}
    assert chatbot_active - lending_active == {"q_chatbot_details"}


def test_lending_answers_map_into_initiative_and_evidence_fields():
    questionnaire = load_questionnaire(QUESTIONNAIRE_PATH)
    answers = _load_answers("sample_answers.yaml")

    initiative_fields, evidence_content = build_initiative_and_evidence_fields(
        questionnaire, answers
    )

    assert initiative_fields == {
        "name": "FixtureCorp Lending Assistant",
        "description": "Recommends credit pre-approval tiers for consumer loans.",
        "modality": "classical_ml",
        "autonomy_level": "recommend_only",
        "hitl_planned": "yes",
    }
    assert evidence_content == {
        "system_type_category": "lending",
        "lending_details": "Pre-approval scoring for unsecured personal loans.",
    }


def test_missing_required_answer_raises_questionnaire_validation_error():
    questionnaire = load_questionnaire(QUESTIONNAIRE_PATH)
    answers = _load_answers("sample_answers_invalid.yaml")

    with pytest.raises(QuestionnaireValidationError, match="q_hitl"):
        build_initiative_and_evidence_fields(questionnaire, answers)


def test_answer_outside_declared_options_raises_questionnaire_validation_error():
    questionnaire = load_questionnaire(QUESTIONNAIRE_PATH)
    answers = _load_answers("sample_answers.yaml")
    answers["q_hitl"] = "definitely-not-an-option"

    with pytest.raises(QuestionnaireValidationError, match="q_hitl"):
        build_initiative_and_evidence_fields(questionnaire, answers)


def test_optional_question_absent_is_not_an_error():
    """q_lending_details/q_chatbot_details are required: false -- a path
    that skips them (e.g. an 'other' system type) must not raise."""
    questionnaire = load_questionnaire(QUESTIONNAIRE_PATH)
    answers = {
        "q_name": "Other System",
        "q_description": "Something that is neither lending nor a chatbot.",
        "q_system_type": "other",
        "q_modality": "other",
        "q_autonomy": "recommend_only",
        "q_hitl": "unknown",
    }

    initiative_fields, evidence_content = build_initiative_and_evidence_fields(
        questionnaire, answers
    )
    assert initiative_fields["name"] == "Other System"
    assert "lending_details" not in evidence_content
    assert "chatbot_scope_notes" not in evidence_content
