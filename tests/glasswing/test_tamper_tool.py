"""tests/tools/tamper.py — GLASSWING_SPEC.md section 3, Week 1 acceptance:
"after running tests/tools/tamper.py against the DB it exits nonzero."

Exercised two ways: as a subprocess (the literal acceptance command) and
by importing its functions directly (for a faster, in-process check of
the same behavior).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from typer.testing import CliRunner

from glasswing.cli.app import app

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tests" / "tools"))
import tamper  # noqa: E402  (path must be set before this import)

runner = CliRunner()


def _migrate(db_url: str) -> None:
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "head")


def _new_engagement(db_url: str, monkeypatch) -> str:
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


def test_tamper_tool_exits_nonzero_as_a_subprocess(tmp_path, monkeypatch):
    db_path = tmp_path / "tamper_subprocess.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.delenv("GLASSWING_DB_URL", raising=False)
    _migrate(db_url)
    engagement_id = _new_engagement(db_url, monkeypatch)

    # Sanity check: the chain verifies before tampering.
    pre_verify = runner.invoke(app, ["audit", "verify", "--engagement", engagement_id])
    assert pre_verify.exit_code == 0

    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "tests" / "tools" / "tamper.py"),
            "--db-url",
            db_url,
            "--engagement",
            engagement_id,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0, proc.stdout + proc.stderr
    assert "CORRUPTION_DETECTED" in proc.stdout

    # And the CLI itself now also reports the corruption.
    post_verify = runner.invoke(app, ["audit", "verify", "--engagement", engagement_id])
    assert post_verify.exit_code == 1


def test_tamper_last_entry_corrupts_the_stored_hash(session):
    from glasswing.services import audit
    from glasswing.storage.models import EngagementRow

    engagement = EngagementRow(
        client_name="Fixture Corp",
        sector="fintech",
        jurisdictions=["US-CO"],
        data_dir="",
    )
    session.add(engagement)
    session.flush()
    engagement.data_dir = f"data/engagements/{engagement.id}"
    audit.append_genesis(session, engagement_id=engagement.id, payload={"n": 1})
    session.commit()

    assert audit.verify_chain(session, engagement.id).valid

    tamper.tamper_last_entry(session, engagement.id)
    session.commit()

    result = audit.verify_chain(session, engagement.id)
    assert not result.valid
