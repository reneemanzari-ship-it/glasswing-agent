"""Fixtures for Week 1 Governance OS tests.

Schema is created directly from glasswing.storage.models.Base metadata
(not via Alembic) for test speed and isolation — the migration itself is
tested separately, once, in test_migrations.py. The two are kept
byte-for-byte in sync by hand (glasswing/storage/migrations/versions/
0001_initial_schema.py mirrors glasswing/storage/models.py column for
column); test_migrations.py is what actually proves that.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from glasswing.storage.database import make_engine, make_session_factory
from glasswing.storage.models import Base


@pytest.fixture()
def engine(tmp_path) -> Iterator[Engine]:
    db_path = tmp_path / "test.db"
    eng = make_engine(f"sqlite:///{db_path.as_posix()}")
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return make_session_factory(engine)


@pytest.fixture()
def session(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    s = session_factory()
    try:
        yield s
        s.commit()
    finally:
        s.close()
