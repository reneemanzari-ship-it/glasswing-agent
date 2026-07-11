"""Typer CLI — the primary operator interface (GLASSWING_SPEC.md section
2.1: "The CLI is what Sonnet tests against and what the acceptance
criteria use.").

Schema is owned by Alembic (alembic.ini / glasswing/storage/migrations/) —
run `alembic upgrade head` before using any command here.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

import typer
import yaml
from sqlalchemy.orm import Session, sessionmaker

from glasswing.engines.questionnaire import (
    Question,
    Questionnaire,
    QuestionType,
    load_questionnaire,
)
from glasswing.engines.questionnaire import active_question_sequence as _active_sequence
from glasswing.intake.questionnaire_runner import (
    HumanReviewRequiredError,
    submit_questionnaire,
)
from glasswing.services import audit
from glasswing.storage.database import make_engine, make_session_factory, session_scope
from glasswing.storage.models import EngagementRow

app = typer.Typer(help="Glasswing Governance OS operator CLI.")
engagement_app = typer.Typer(help="Manage engagements.")
audit_app = typer.Typer(help="Inspect and verify audit chains.")
intake_app = typer.Typer(help="Run intake questionnaires.")
app.add_typer(engagement_app, name="engagement")
app.add_typer(audit_app, name="audit")
app.add_typer(intake_app, name="intake")

DEFAULT_QUESTIONNAIRE_PATH = "questionnaires/governance_intake_v1.yaml"


def _db_url() -> str:
    return os.environ.get("GLASSWING_DB_URL", "sqlite:///glasswing.db")


def _session_factory() -> sessionmaker[Session]:
    engine = make_engine(_db_url())
    return make_session_factory(engine)


@engagement_app.command("new")
def engagement_new(
    client: str = typer.Option(..., "--client", help="Client name."),
    sector: str = typer.Option(..., "--sector", help="Client sector."),
    jurisdictions: str = typer.Option(
        ...,
        "--jurisdictions",
        help="Comma-separated jurisdictions, e.g. US-CO,EU.",
    ),
) -> None:
    """Creates a new engagement and writes its genesis audit entry."""
    jurisdiction_list = [j.strip() for j in jurisdictions.split(",") if j.strip()]
    if not jurisdiction_list:
        typer.echo("At least one jurisdiction is required.", err=True)
        raise typer.Exit(code=1)

    session_factory = _session_factory()
    with session_scope(session_factory) as session:
        engagement = EngagementRow(
            client_name=client,
            sector=sector,
            jurisdictions=jurisdiction_list,
            data_dir="",
        )
        session.add(engagement)
        session.flush()  # assigns engagement.id
        engagement.data_dir = f"data/engagements/{engagement.id}"

        audit.append_genesis(
            session,
            engagement_id=engagement.id,
            payload={
                "client_name": client,
                "sector": sector,
                "jurisdictions": jurisdiction_list,
            },
        )
        engagement_id = engagement.id

    typer.echo(str(engagement_id))


@audit_app.command("verify")
def audit_verify(
    engagement: str = typer.Option(..., "--engagement", help="Engagement id."),
) -> None:
    """Verifies the tamper-evident hash chain for an engagement.

    Exits 0 if the chain verifies, 1 otherwise.
    """
    try:
        engagement_id = uuid.UUID(engagement)
    except ValueError as exc:
        typer.echo(f"Invalid engagement id: {engagement}", err=True)
        raise typer.Exit(code=1) from exc

    session_factory = _session_factory()
    with session_scope(session_factory) as session:
        result = audit.verify_chain(session, engagement_id)

    typer.echo(result.message)
    if not result.valid:
        raise typer.Exit(code=1)


def _coerce_interactive_answer(question: Question, raw: str) -> Any:
    """Turns a raw interactive prompt string into the value type
    build_initiative_and_evidence_fields() expects for this question's
    type. Malformed input for boolean/number is reported and re-prompted
    by the caller, not silently coerced to something wrong."""
    if question.type == QuestionType.BOOLEAN:
        lowered = raw.strip().lower()
        if lowered in ("yes", "y", "true"):
            return True
        if lowered in ("no", "n", "false"):
            return False
        raise ValueError(f"expected yes/no, got {raw!r}")
    if question.type == QuestionType.NUMBER:
        return float(raw) if "." in raw else int(raw)
    if question.type == QuestionType.MULTI_SELECT:
        return [v.strip() for v in raw.split(",") if v.strip()]
    return raw


def _run_interactive(
    questionnaire: Questionnaire, resume_path: Path | None
) -> dict[str, Any]:
    """Asks each currently-active, unanswered question in order, saving
    progress after every answer when --resume-file is given so a partial
    session can be interrupted and continued."""
    answers: dict[str, Any] = {}
    if resume_path is not None and resume_path.exists():
        answers = yaml.safe_load(resume_path.read_text(encoding="utf-8")) or {}
        typer.echo(f"Resumed {len(answers)} answer(s) from {resume_path}.")

    by_id = questionnaire.question_by_id()
    while True:
        active = _active_sequence(questionnaire, answers)
        unanswered = [qid for qid in active if qid not in answers]
        if not unanswered:
            break
        question = by_id[unanswered[0]]
        prompt_text = question.text
        if question.options:
            prompt_text += f" [{'/'.join(question.options)}]"
        raw = typer.prompt(prompt_text)
        try:
            answers[question.id] = _coerce_interactive_answer(question, raw)
        except ValueError as exc:
            typer.echo(f"Invalid answer: {exc}. Try again.", err=True)
            continue
        if resume_path is not None:
            resume_path.write_text(yaml.safe_dump(answers), encoding="utf-8")
    return answers


@intake_app.command("questionnaire")
def intake_questionnaire(
    engagement: str = typer.Option(..., "--engagement", help="Engagement id."),
    answers_file: str | None = typer.Option(
        None, "--answers", help="Path to a YAML answers file (answers-file mode)."
    ),
    questionnaire_path: str = typer.Option(
        DEFAULT_QUESTIONNAIRE_PATH,
        "--questionnaire",
        help="Path to the questionnaire YAML.",
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        help="Prompt for answers interactively instead of --answers.",
    ),
    resume_file: str | None = typer.Option(
        None, "--resume-file", help="Save/resume partial interactive progress here."
    ),
    actor: str = typer.Option(
        "operator", "--actor", help="Actor name recorded on audit entries."
    ),
) -> None:
    """Runs a questionnaire intake: produces a validated Initiative and
    EvidenceRecord, and transitions the initiative DRAFT -> EVIDENCE_COMPLETE.

    Exits 0 on success (prints the initiative id), 1 if the submission is
    routed to human review (schema validation failure -- see the
    HUMAN_REVIEW_REQUESTED audit entry for the reason).
    """
    try:
        engagement_id = uuid.UUID(engagement)
    except ValueError as exc:
        typer.echo(f"Invalid engagement id: {engagement}", err=True)
        raise typer.Exit(code=1) from exc

    if not answers_file and not interactive:
        typer.echo("Provide either --answers <file> or --interactive.", err=True)
        raise typer.Exit(code=1)

    questionnaire = load_questionnaire(Path(questionnaire_path))

    if interactive:
        resume_path = Path(resume_file) if resume_file else None
        answers = _run_interactive(questionnaire, resume_path)
    else:
        assert answers_file is not None
        answers = yaml.safe_load(Path(answers_file).read_text(encoding="utf-8")) or {}

    session_factory = _session_factory()
    outcome: tuple[str, str]
    with session_scope(session_factory) as session:
        try:
            initiative_row, _evidence_row = submit_questionnaire(
                session,
                engagement_id=engagement_id,
                questionnaire=questionnaire,
                answers=answers,
                actor=actor,
            )
            outcome = ("ok", str(initiative_row.id))
        except HumanReviewRequiredError as exc:
            # Caught INSIDE session_scope so the HUMAN_REVIEW_REQUESTED
            # audit entry already written by submit_questionnaire commits
            # normally, instead of being rolled back by an exception
            # propagating out of the `with` block.
            outcome = ("human_review", str(exc))

    if outcome[0] == "human_review":
        typer.echo(f"Routed to human review: {outcome[1]}", err=True)
        raise typer.Exit(code=1)

    if interactive and resume_file:
        resume_path = Path(resume_file)
        if resume_path.exists():
            resume_path.unlink()

    typer.echo(outcome[1])


def main() -> None:
    app()


if __name__ == "__main__":
    main()
