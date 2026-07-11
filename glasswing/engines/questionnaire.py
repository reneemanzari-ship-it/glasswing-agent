"""Deterministic questionnaire engine (GLASSWING_SPEC.md section 3, Week 3).

Loads a YAML questionnaire definition (question id, text, type, options,
branching, field mappings into Initiative/EvidenceRecord per section 2.6)
and an answers mapping, and produces validated field values for an
Initiative and an EvidenceRecord.

This module knows only the schema below -- it never hardcodes any
question's id, text, or content. The real governance_intake_v1.yaml
content is authored externally as a structural generalization of
Firemark's intake methodology (DECISIONS.md D-019); it must drop in as
data with zero changes to this file. tests/fixtures/questionnaires/
sample_intake_v0.yaml is engine test scaffolding only, never a client
deliverable.

Deterministic, no LLM calls -- CLAUDE.md invariant #1.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic import ValidationError as PydanticValidationError


class QuestionType(str, Enum):
    TEXT = "text"
    BOOLEAN = "boolean"
    NUMBER = "number"
    SINGLE_SELECT = "single_select"
    MULTI_SELECT = "multi_select"


class Question(BaseModel):
    id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    type: QuestionType
    options: list[str] = Field(default_factory=list)
    maps_to: str = Field(..., min_length=1)
    required: bool = True
    # branch: {answer_value: [question_id, ...]} -- questions unlocked
    # when this question's answer equals answer_value. Answer values are
    # matched as their YAML-native type stringified (see
    # active_question_sequence()) so "yes"/"no" and true/false both work
    # as branch keys without the author needing to know which internally.
    branch: dict[str, list[str]] = Field(default_factory=dict)


class Questionnaire(BaseModel):
    questionnaire_id: str = Field(..., min_length=1)
    version: str = Field(..., min_length=1)
    questions: list[Question] = Field(..., min_length=1)

    def question_by_id(self) -> dict[str, Question]:
        return {q.id: q for q in self.questions}

    def base_question_ids(self) -> list[str]:
        """Questions not referenced as any branch target -- always active,
        in questionnaire-file order."""
        branch_targets = {
            qid for q in self.questions for ids in q.branch.values() for qid in ids
        }
        return [q.id for q in self.questions if q.id not in branch_targets]


def load_questionnaire(path: Path) -> Questionnaire:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Questionnaire.model_validate(data)


class QuestionnaireValidationError(ValueError):
    """An answers submission fails the questionnaire's own schema (missing
    required answer, answer outside a question's declared type/options,
    or an unrecognized maps_to target). Callers route this to human
    review; it is never allowed to propagate as an unhandled crash."""


def _branch_key(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def active_question_sequence(
    questionnaire: Questionnaire, answers: dict[str, Any]
) -> list[str]:
    """Computes, in order, exactly which question ids are active given the
    answers provided so far: base questions plus any branch targets
    unlocked by an already-given answer. Deterministic; no LLM.

    This is what makes two answer sets to the same questionnaire
    genuinely diverge: a "lending" answer to a branching question
    unlocks different follow-up questions than a "chatbot" answer would,
    not the same fixed list filtered after the fact.
    """
    by_id = questionnaire.question_by_id()
    queue = list(questionnaire.base_question_ids())
    seen = set(queue)
    i = 0
    while i < len(queue):
        question = by_id.get(queue[i])
        if question is not None:
            answer = answers.get(question.id)
            if answer is not None:
                for target_id in question.branch.get(_branch_key(answer), []):
                    if target_id not in seen:
                        queue.insert(i + 1, target_id)
                        seen.add(target_id)
        i += 1
    return queue


def _validate_answer(question: Question, value: Any) -> Any:
    if question.type == QuestionType.BOOLEAN:
        if not isinstance(value, bool):
            raise QuestionnaireValidationError(
                f"{question.id}: expected boolean, got {value!r}"
            )
    elif question.type == QuestionType.NUMBER:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise QuestionnaireValidationError(
                f"{question.id}: expected number, got {value!r}"
            )
    elif question.type == QuestionType.SINGLE_SELECT:
        if value not in question.options:
            raise QuestionnaireValidationError(
                f"{question.id}: {value!r} not in allowed options {question.options}"
            )
    elif question.type == QuestionType.MULTI_SELECT:
        if not isinstance(value, list) or any(v not in question.options for v in value):
            raise QuestionnaireValidationError(
                f"{question.id}: {value!r} not a valid subset of {question.options}"
            )
    elif question.type == QuestionType.TEXT:
        if not isinstance(value, str) or not value.strip():
            raise QuestionnaireValidationError(
                f"{question.id}: expected non-empty text"
            )
    return value


def build_initiative_and_evidence_fields(
    questionnaire: Questionnaire, answers: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Maps answers to active questions into Initiative field values and
    EvidenceRecord content, per each question's `maps_to`.

    Raises QuestionnaireValidationError -- never crashes, never silently
    drops an answer -- when:
    - a required active question has no answer,
    - an answer fails its question's declared type/options,
    - a maps_to target isn't a recognized `initiative.<field>` or
      `evidence.<field>` path.

    Returns (initiative_fields, evidence_content), both plain dicts. The
    caller still constructs and validates the real Initiative Pydantic
    model from initiative_fields -- this function's checks are the
    questionnaire-schema layer, not a replacement for the Initiative
    model's own validation (CLAUDE.md invariant #2: every handoff
    validates a schema).
    """
    by_id = questionnaire.question_by_id()
    active_ids = active_question_sequence(questionnaire, answers)

    initiative_fields: dict[str, Any] = {}
    evidence_content: dict[str, Any] = {}

    for qid in active_ids:
        question = by_id[qid]
        if qid not in answers:
            if question.required:
                raise QuestionnaireValidationError(
                    f"{qid}: required question has no answer"
                )
            continue

        value = _validate_answer(question, answers[qid])

        if question.maps_to.startswith("initiative."):
            initiative_fields[question.maps_to.removeprefix("initiative.")] = value
        elif question.maps_to.startswith("evidence."):
            evidence_content[question.maps_to.removeprefix("evidence.")] = value
        else:
            raise QuestionnaireValidationError(
                f"{qid}: maps_to {question.maps_to!r} must start with "
                "'initiative.' or 'evidence.'"
            )

    return initiative_fields, evidence_content


__all__ = [
    "PydanticValidationError",
    "Question",
    "QuestionType",
    "Questionnaire",
    "QuestionnaireValidationError",
    "active_question_sequence",
    "build_initiative_and_evidence_fields",
    "load_questionnaire",
]
