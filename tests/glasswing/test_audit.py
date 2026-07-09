"""services/audit.py: per-engagement hash chain construction, tamper
detection, and the stable-hash rule (CLAUDE.md hash stability rule)."""

from __future__ import annotations

import uuid
from datetime import timedelta

from glasswing.core.risk import RiskProfile
from glasswing.services import audit
from glasswing.storage.models import AuditEntryRow, EngagementRow


def _make_engagement(session) -> EngagementRow:
    engagement = EngagementRow(
        client_name="Fixture Corp",
        sector="fintech",
        jurisdictions=["US-CO"],
        data_dir="",
    )
    session.add(engagement)
    session.flush()
    engagement.data_dir = f"data/engagements/{engagement.id}"
    return engagement


def test_genesis_entry_has_no_predecessor(session):
    engagement = _make_engagement(session)
    entry = audit.append_genesis(
        session, engagement_id=engagement.id, payload={"client_name": "Fixture Corp"}
    )
    session.commit()

    assert entry.seq == 0
    assert entry.prev_chain_hash is None
    assert audit.verify_chain(session, engagement.id).valid


def test_chain_extends_and_links_to_predecessor(session):
    engagement = _make_engagement(session)
    audit.append_genesis(
        session, engagement_id=engagement.id, payload={"client_name": "Fixture Corp"}
    )
    audit.append_entry(
        session,
        engagement_id=engagement.id,
        event_type="test_event",
        actor="tester",
        payload={"k": "v"},
    )
    session.commit()

    rows = (
        session.query(AuditEntryRow)
        .filter_by(engagement_id=engagement.id)
        .order_by(AuditEntryRow.seq)
        .all()
    )
    assert len(rows) == 2
    assert rows[1].prev_chain_hash == rows[0].chain_hash
    assert audit.verify_chain(session, engagement.id).valid


def test_two_engagements_have_independent_chains(session):
    e1 = _make_engagement(session)
    e2 = _make_engagement(session)
    audit.append_genesis(session, engagement_id=e1.id, payload={"n": 1})
    audit.append_genesis(session, engagement_id=e2.id, payload={"n": 2})
    session.commit()

    assert audit.verify_chain(session, e1.id).valid
    assert audit.verify_chain(session, e2.id).valid

    e1_entries = session.query(AuditEntryRow).filter_by(engagement_id=e1.id).all()
    e2_entries = session.query(AuditEntryRow).filter_by(engagement_id=e2.id).all()
    assert len(e1_entries) == 1
    assert len(e2_entries) == 1
    assert e1_entries[0].seq == 0
    assert e2_entries[0].seq == 0


def test_tampering_a_field_is_detected(session):
    engagement = _make_engagement(session)
    audit.append_genesis(
        session, engagement_id=engagement.id, payload={"client_name": "Fixture Corp"}
    )
    session.commit()

    row = session.query(AuditEntryRow).filter_by(engagement_id=engagement.id).one()
    row.payload_hash = "0" * 64
    session.commit()

    result = audit.verify_chain(session, engagement.id)
    assert not result.valid
    assert result.corrupted_seq == 0
    assert "CORRUPTION_DETECTED" in result.message


def test_tampering_the_chain_link_is_detected(session):
    engagement = _make_engagement(session)
    audit.append_genesis(session, engagement_id=engagement.id, payload={"n": 1})
    audit.append_entry(
        session,
        engagement_id=engagement.id,
        event_type="test_event",
        actor="tester",
        payload={"k": "v"},
    )
    session.commit()

    second = (
        session.query(AuditEntryRow)
        .filter_by(engagement_id=engagement.id)
        .order_by(AuditEntryRow.seq.desc())
        .first()
    )
    second.prev_chain_hash = "f" * 64
    session.commit()

    result = audit.verify_chain(session, engagement.id)
    assert not result.valid
    assert result.corrupted_seq == 1


def test_stable_hash_ignores_id_and_created_at() -> None:
    """CLAUDE.md hash stability rule: a re-serialized object with a new
    auto-generated id/timestamp must produce the same content hash."""
    initiative_id = uuid.uuid4()
    rp1 = RiskProfile(
        initiative_id=initiative_id,
        overall_tier="high",
        engine_version="0.1.0",
    )
    rp2 = rp1.model_copy(
        update={
            "id": uuid.uuid4(),
            "created_at": rp1.created_at + timedelta(days=1),
        }
    )

    assert rp1.id != rp2.id
    assert rp1.created_at != rp2.created_at
    assert audit.stable_hash(rp1) == audit.stable_hash(rp2)


def test_stable_hash_changes_with_real_content_changes() -> None:
    rp1 = RiskProfile(
        initiative_id=uuid.uuid4(), overall_tier="high", engine_version="0.1.0"
    )
    rp2 = rp1.model_copy(update={"overall_tier": "critical"})

    assert audit.stable_hash(rp1) != audit.stable_hash(rp2)
