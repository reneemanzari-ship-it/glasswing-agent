"""Engine/session factory for the Governance OS database.

Single-tenant SQLite per GLASSWING_SPEC.md section 2.1. Alembic (see
glasswing/storage/migrations/) owns the schema; this module only ever
opens connections to it, never creates or alters tables itself.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def make_engine(db_url: str) -> Engine:
    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    return create_engine(db_url, connect_args=connect_args)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    """One committed transaction per `with` block; rolls back whole on
    any exception so a failed audit-entry write can never leave a state
    mutation committed without it (CLAUDE.md invariant #3)."""
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
