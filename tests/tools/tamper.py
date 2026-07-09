"""Deliberately corrupts one audit_entries row for an engagement, to
demonstrate that glasswing/services/audit.py's verify_chain() detects it.

GLASSWING_SPEC.md section 3, Week 1 acceptance criterion: "after running
tests/tools/tamper.py against the DB it exits nonzero."

Exit code mirrors `glasswing audit verify`'s own convention: 0 means the
chain still verifies (should never happen after tampering — a bug if it
ever does), 1 means corruption was detected (the expected, successful
outcome of running this tool).

Usage:
    python tests/tools/tamper.py --db-url sqlite:///glasswing.db --engagement <id>
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import select
from sqlalchemy.orm import Session

from glasswing.services import audit
from glasswing.storage.database import make_engine, make_session_factory, session_scope
from glasswing.storage.models import AuditEntryRow


def tamper_last_entry(session: Session, engagement_id: uuid.UUID) -> AuditEntryRow:
    """Flips one character of the last audit entry's payload_hash for
    `engagement_id`. Returns the tampered row."""
    stmt = (
        select(AuditEntryRow)
        .where(AuditEntryRow.engagement_id == engagement_id)
        .order_by(AuditEntryRow.seq.desc())
        .limit(1)
    )
    row = session.execute(stmt).scalars().first()
    if row is None:
        raise ValueError(f"No audit entries found for engagement {engagement_id}.")
    flipped_char = "0" if row.payload_hash[0] != "0" else "1"
    row.payload_hash = flipped_char + row.payload_hash[1:]
    return row


def tamper_and_verify(
    db_url: str, engagement_id: uuid.UUID
) -> audit.ChainVerificationResult:
    engine = make_engine(db_url)
    session_factory = make_session_factory(engine)
    with session_scope(session_factory) as session:
        tamper_last_entry(session, engagement_id)
    with session_factory() as session:
        return audit.verify_chain(session, engagement_id)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-url", required=True)
    parser.add_argument("--engagement", required=True)
    args = parser.parse_args(argv)

    result = tamper_and_verify(args.db_url, uuid.UUID(args.engagement))
    print(result.message)
    return 0 if result.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
