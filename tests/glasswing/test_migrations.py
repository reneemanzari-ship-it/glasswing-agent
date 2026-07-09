"""alembic upgrade head / downgrade base against an empty DB.

GLASSWING_SPEC.md section 3, Week 1 acceptance criterion.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config

REPO_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_TABLES = {
    "engagements",
    "governance_profiles",
    "initiatives",
    "evidence_records",
    "risk_profiles",
    "control_prescriptions",
    "control_status",
    "approval_decisions",
    "audit_entries",
    "run_ledger",
    "report_artifacts",
}


def _alembic_config(db_url: str) -> Config:
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _tables(db_path: Path) -> set[str]:
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return {row[0] for row in rows}
    finally:
        con.close()


def test_upgrade_head_creates_all_week_one_tables(tmp_path, monkeypatch):
    monkeypatch.delenv("GLASSWING_DB_URL", raising=False)
    db_path = tmp_path / "migrate_test.db"
    cfg = _alembic_config(f"sqlite:///{db_path.as_posix()}")

    command.upgrade(cfg, "head")

    tables = _tables(db_path)
    assert EXPECTED_TABLES.issubset(tables)
    assert "alembic_version" in tables


def test_downgrade_base_drops_every_week_one_table(tmp_path, monkeypatch):
    monkeypatch.delenv("GLASSWING_DB_URL", raising=False)
    db_path = tmp_path / "migrate_test.db"
    cfg = _alembic_config(f"sqlite:///{db_path.as_posix()}")

    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    tables = _tables(db_path)
    assert tables.isdisjoint(EXPECTED_TABLES)
