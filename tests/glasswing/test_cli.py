"""`glasswing engagement new` and `glasswing audit verify` — GLASSWING_SPEC.md
section 3, Week 1 acceptance criteria, exercised through Typer's test
client rather than a subprocess."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from alembic import command
from alembic.config import Config
from typer.testing import CliRunner

from glasswing.cli.app import app

REPO_ROOT = Path(__file__).resolve().parents[2]
runner = CliRunner()


def _migrate(db_url: str) -> None:
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "head")


def test_engagement_new_then_audit_verify_round_trip(tmp_path, monkeypatch):
    db_path = tmp_path / "cli_test.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.delenv("GLASSWING_DB_URL", raising=False)
    _migrate(db_url)
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
    engagement_id = result.stdout.strip()
    assert re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", engagement_id
    )
    uuid.UUID(engagement_id)  # raises if not a valid UUID

    verify_result = runner.invoke(
        app, ["audit", "verify", "--engagement", engagement_id]
    )
    assert verify_result.exit_code == 0, verify_result.output
    assert "SUCCESS" in verify_result.stdout


def test_audit_verify_fails_for_unknown_engagement(tmp_path, monkeypatch):
    db_path = tmp_path / "cli_test_empty.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.delenv("GLASSWING_DB_URL", raising=False)
    _migrate(db_url)
    monkeypatch.setenv("GLASSWING_DB_URL", db_url)

    result = runner.invoke(app, ["audit", "verify", "--engagement", str(uuid.uuid4())])
    assert result.exit_code == 1


def test_engagement_new_requires_at_least_one_jurisdiction(tmp_path, monkeypatch):
    db_path = tmp_path / "cli_test_no_jurisdiction.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.delenv("GLASSWING_DB_URL", raising=False)
    _migrate(db_url)
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
            "  ,  ",
        ],
    )
    assert result.exit_code == 1
