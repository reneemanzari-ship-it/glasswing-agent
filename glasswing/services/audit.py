"""Tamper-evident, per-engagement audit hash chain.

Ported from v0.1's agents/audit_trail.py (GLASSWING_SPEC.md section 2.3):
same SHA-256 chain-hash construction and replay-verification logic, minus
the ADK agent wrapper. Two changes from v0.1:

1. The chain is scoped per engagement (its own `seq` sequence and its own
   genesis entry) instead of one process-global list, per GLASSWING_SPEC.md
   section 2.3: "a client's regulator packet verifies standalone without
   exposing any other client's existence."
2. Entries are rows in the `audit_entries` table (via SQLAlchemy), not an
   in-memory list.

Deterministic, no LLM calls — CLAUDE.md invariant #1.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from glasswing.storage.models import AuditEntryRow

GENESIS_EVENT_TYPE = "engagement_created"


def _hash_payload(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _compute_chain_hash(
    *,
    engagement_id: str,
    seq: int,
    event_type: str,
    actor: str,
    payload_hash: str,
    prev_chain_hash: str | None,
) -> str:
    """Mirrors v0.1's chain_hash construction: hash of the entry's own
    fields (everything except chain_hash itself), chained onto the
    previous entry's chain_hash when one exists. Genesis entries (no
    predecessor) hash only their own fields."""
    entry_dict = {
        "engagement_id": engagement_id,
        "seq": seq,
        "event_type": event_type,
        "actor": actor,
        "payload_hash": payload_hash,
        "prev_chain_hash": prev_chain_hash,
    }
    serialized = json.dumps(entry_dict, sort_keys=True, default=str)
    payload = f"{serialized}_{prev_chain_hash}" if prev_chain_hash else serialized
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _last_entry(session: Session, engagement_id: uuid.UUID) -> AuditEntryRow | None:
    stmt = (
        select(AuditEntryRow)
        .where(AuditEntryRow.engagement_id == engagement_id)
        .order_by(AuditEntryRow.seq.desc())
        .limit(1)
    )
    return session.execute(stmt).scalars().first()


def append_entry(
    session: Session,
    *,
    engagement_id: uuid.UUID,
    event_type: str,
    actor: str,
    payload: dict[str, Any],
) -> AuditEntryRow:
    """Appends the next entry in engagement_id's hash chain.

    Callers write this within the same transaction as the state mutation
    it certifies, and flush (or let the transaction fail) before
    committing either — CLAUDE.md invariant #3: "no entry, no mutation."
    See glasswing/storage/database.py::session_scope for the rollback
    behavior that enforces this.
    """
    prior = _last_entry(session, engagement_id)
    seq = 0 if prior is None else prior.seq + 1
    prev_chain_hash = prior.chain_hash if prior is not None else None
    payload_hash = _hash_payload(payload)
    chain_hash = _compute_chain_hash(
        engagement_id=str(engagement_id),
        seq=seq,
        event_type=event_type,
        actor=actor,
        payload_hash=payload_hash,
        prev_chain_hash=prev_chain_hash,
    )
    entry = AuditEntryRow(
        engagement_id=engagement_id,
        seq=seq,
        event_type=event_type,
        actor=actor,
        payload_hash=payload_hash,
        prev_chain_hash=prev_chain_hash,
        chain_hash=chain_hash,
    )
    session.add(entry)
    session.flush()
    return entry


def append_genesis(
    session: Session, *, engagement_id: uuid.UUID, payload: dict[str, Any]
) -> AuditEntryRow:
    """The first entry in a new engagement's chain, written at engagement
    creation (GLASSWING_SPEC.md section 2.6: "Per-engagement chain,
    genesis at engagement creation")."""
    return append_entry(
        session,
        engagement_id=engagement_id,
        event_type=GENESIS_EVENT_TYPE,
        actor="system",
        payload=payload,
    )


@dataclass(frozen=True)
class ChainVerificationResult:
    valid: bool
    message: str
    corrupted_seq: int | None = None


def verify_chain(session: Session, engagement_id: uuid.UUID) -> ChainVerificationResult:
    """Recomputes every entry's chain_hash from its own fields and its
    predecessor, in seq order, and compares against what's stored. Any
    mismatch — a changed field, a swapped prev_chain_hash, a deleted or
    reordered entry — is reported as the first seq where the chain no
    longer verifies."""
    stmt = (
        select(AuditEntryRow)
        .where(AuditEntryRow.engagement_id == engagement_id)
        .order_by(AuditEntryRow.seq.asc())
    )
    entries = session.execute(stmt).scalars().all()
    if not entries:
        return ChainVerificationResult(
            valid=False,
            message=f"No audit entries found for engagement {engagement_id}.",
        )

    expected_prev: str | None = None
    for entry in entries:
        if entry.prev_chain_hash != expected_prev:
            return ChainVerificationResult(
                valid=False,
                message=(
                    f"CORRUPTION_DETECTED: entry seq={entry.seq} prev_chain_hash "
                    "does not match the preceding entry's chain_hash."
                ),
                corrupted_seq=entry.seq,
            )
        expected_hash = _compute_chain_hash(
            engagement_id=str(entry.engagement_id),
            seq=entry.seq,
            event_type=entry.event_type,
            actor=entry.actor,
            payload_hash=entry.payload_hash,
            prev_chain_hash=entry.prev_chain_hash,
        )
        if entry.chain_hash != expected_hash:
            return ChainVerificationResult(
                valid=False,
                message=(
                    f"CORRUPTION_DETECTED: entry seq={entry.seq} chain_hash does not "
                    f"match its recomputed hash (expected {expected_hash}, found "
                    f"{entry.chain_hash})."
                ),
                corrupted_seq=entry.seq,
            )
        expected_prev = entry.chain_hash

    return ChainVerificationResult(
        valid=True, message="SUCCESS: audit chain verified. Zero tampering detected."
    )


# --- Stable content hashing (CLAUDE.md hash stability rule) -----------------
#
# Carried forward from v0.1's orchestration/flow.py::_stable_hash(). Models
# that carry an auto-generated id and/or a fresh created_at timestamp on
# every construction must be hashed through this function, excluding those
# volatile fields, rather than through raw model_dump_json() — otherwise
# the same logical content would never hash the same way twice, and replay
# verification (comparing a historical output_hash against a freshly
# recomputed one) would be impossible by construction.
_VOLATILE_FIELDS_BY_MODEL: dict[str, set[str]] = {
    "RiskProfile": {"id", "created_at"},
    # risk_profile_id is a foreign key into RiskProfile, which is itself
    # freshly regenerated every run -- exclude it too, or this object's
    # "stable" hash would inherit RiskProfile's volatility.
    "ControlPrescription": {"id", "created_at", "risk_profile_id"},
}


def stable_hash(model: BaseModel) -> str:
    """Content hash for run-ledger output_hash logging and replay
    verification. See _VOLATILE_FIELDS_BY_MODEL for why identity/timestamp
    fields are excluded for the model types listed there."""
    exclude = _VOLATILE_FIELDS_BY_MODEL.get(type(model).__name__, set())
    data = model.model_dump(mode="json", exclude=exclude)
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
