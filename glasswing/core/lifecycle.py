"""Initiative lifecycle states.

Full state set is declared here in Week 1 so the schema never needs to
change shape later (GLASSWING_SPEC.md section 3, Week 1: "Phase 2 states
defined but transitions to them raise NotImplementedError"). See
glasswing/services/portfolio.py for the transition rules themselves.
"""

from enum import Enum


class LifecycleState(str, Enum):
    DRAFT = "draft"
    EVIDENCE_COMPLETE = "evidence_complete"
    CLASSIFIED = "classified"
    CONTROLS_PRESCRIBED = "controls_prescribed"
    PENDING_SIGNOFF = "pending_signoff"
    APPROVED = "approved"
    REQUIRES_REVISION = "requires_revision"
    REJECTED = "rejected"
    # Phase 2+ states (GLASSWING_SPEC.md section 2.6). Declared now so the
    # column/enum never needs a later migration; transitions into them are
    # not implemented until their scoped week.
    DEPLOYED_MONITORING = "deployed_monitoring"
    UNDER_REVIEW = "under_review"
    RETIRED = "retired"
