"""`glasswing intake questionnaire` — GLASSWING_SPEC.md section 3, Week 3
acceptance criteria, exercised through Typer's test client.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from alembic import command
from alembic.config import Config
from typer.testing import CliRunner

from glasswing.cli.app import app
from glasswing.storage.database import make_engine, make_session_factory, session_scope
from glasswing.storage.models import AuditEntryRow, InitiativeRow

REPO_ROOT = Path(__file__).resolve().parents[2]
QUESTIONNAIRE_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "questionnaires"
runner = CliRunner()


def _migrate(db_url: str) -> None:
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "head")


def _new_engagement(monkeypatch, db_url: str) -> str:
    monkeypatch.setenv("GLASSWING_DB_URL", db_url)
    result = runner.invoke(
        app,
        [
            "engagement",
            "new",
            "--client",
            "Fixture Corp",
            "--sector",
            "fintech",
            "--jurisdictions",
            "US-CO,EU",
        ],
    )
    assert result.exit_code == 0, result.output
    return result.stdout.strip()


def test_answers_file_produces_initiative_and_moves_to_evidence_complete(
    tmp_path, monkeypatch
):
    """GLASSWING_SPEC.md section 3, Week 3 acceptance: `glasswing intake
    questionnaire --engagement <id> --answers
    tests/fixtures/questionnaires/sample_answers.yaml` produces a valid
    Initiative + EvidenceRecords and moves state to EVIDENCE_COMPLETE."""
    db_path = tmp_path / "cli_questionnaire_test.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.delenv("GLASSWING_DB_URL", raising=False)
    _migrate(db_url)
    engagement_id = _new_engagement(monkeypatch, db_url)

    result = runner.invoke(
        app,
        [
            "intake",
            "questionnaire",
            "--engagement",
            engagement_id,
            "--questionnaire",
            str(QUESTIONNAIRE_FIXTURES / "sample_intake_v0.yaml"),
            "--answers",
            str(QUESTIONNAIRE_FIXTURES / "sample_answers.yaml"),
        ],
    )
    assert result.exit_code == 0, result.output
    initiative_id = uuid.UUID(result.stdout.strip())

    engine = make_engine(db_url)
    session_factory = make_session_factory(engine)
    with session_scope(session_factory) as session:
        initiative = session.query(InitiativeRow).filter_by(id=initiative_id).one()
        assert initiative.lifecycle_state == "evidence_complete"

        entries = (
            session.query(AuditEntryRow)
            .filter_by(engagement_id=initiative.engagement_id)
            .order_by(AuditEntryRow.seq)
            .all()
        )
        assert [e.event_type for e in entries] == [
            "engagement_created",
            "initiative_created",
            "evidence_recorded",
            "state_transitioned",
        ]


def test_invalid_answers_file_exits_nonzero_and_routes_to_human_review(
    tmp_path, monkeypatch
):
    """GLASSWING_SPEC.md section 3, Week 3 acceptance: an answers file
    failing schema validation routes to human review and logs
    HUMAN_REVIEW_REQUESTED."""
    db_path = tmp_path / "cli_questionnaire_invalid_test.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.delenv("GLASSWING_DB_URL", raising=False)
    _migrate(db_url)
    engagement_id = _new_engagement(monkeypatch, db_url)

    result = runner.invoke(
        app,
        [
            "intake",
            "questionnaire",
            "--engagement",
            engagement_id,
            "--questionnaire",
            str(QUESTIONNAIRE_FIXTURES / "sample_intake_v0.yaml"),
            "--answers",
            str(QUESTIONNAIRE_FIXTURES / "sample_answers_invalid.yaml"),
        ],
    )
    assert result.exit_code == 1
    assert "human review" in result.output.lower()

    engine = make_engine(db_url)
    session_factory = make_session_factory(engine)
    with session_scope(session_factory) as session:
        entries = (
            session.query(AuditEntryRow)
            .filter_by(engagement_id=uuid.UUID(engagement_id))
            .order_by(AuditEntryRow.seq)
            .all()
        )
        assert [e.event_type for e in entries] == [
            "engagement_created",
            "human_review_requested",
        ]
        assert session.query(InitiativeRow).count() == 0
