"""
Google ADK to Anthropic Claude Routing Pattern:
----------------------------------------------
Model: anthropic/claude-sonnet-4-5-20250115 (via LiteLLM router)
Instructions: Dynamically loaded from prompts/portfolio_manager.md
Tools: Exposes SQLite operations as tools.
"""

import os
import sqlite3
import json
import uuid
from pathlib import Path
from datetime import date, datetime
from typing import Dict, Any, List, Optional, Tuple
from google.adk import Agent

from schemas.initiative import Initiative, HITLPlanned
from schemas.risk_profile import RiskProfile, OverallRiskTier
from schemas.control_prescription import ControlPrescription
from schemas.governance_manifest import GovernanceManifest, ManifestStatus
from schemas.portfolio_state import PortfolioState, InitiativeStatus, InitiativeSummary, StateTransition

CONFIDENCE_REVIEW_THRESHOLD = 0.75


def get_low_confidence_frameworks(risk_profile: RiskProfile, threshold: float = CONFIDENCE_REVIEW_THRESHOLD) -> List[str]:
    """Names of the frameworks whose classification confidence falls below
    threshold. Shared by _determine_initiative_status() below and by
    orchestration/flow.py's pre-control-prescription gate, so the two
    don't independently re-implement (and risk drifting on) the same
    check."""
    return [
        name
        for name, classification in (
            ("eu_ai_act", risk_profile.classifications.eu_ai_act),
            ("nist_ai_rmf", risk_profile.classifications.nist_ai_rmf),
            ("colorado_sb_205", risk_profile.classifications.colorado_sb_205),
        )
        if classification.confidence < threshold
    ]


def _determine_initiative_status(
    initiative: Initiative,
    risk_profile: RiskProfile,
    control_prescription: ControlPrescription,
) -> Tuple[InitiativeStatus, str]:
    """Decides the InitiativeStatus to assign after control prescription,
    and the rationale that must be cited on the state transition record.

    Precedence:
    1. Low-confidence framework classifications (<0.75) route to
       AWAITING_HUMAN_REVIEW — this is a triage/analyst-review state,
       kept distinct from substantive governance gaps. In the normal
       pipeline (orchestration/flow.py) this case is caught upstream,
       before control prescription even runs; this check remains here as
       a defensive backstop for any caller that invokes
       register_initiative() directly.
    2. Any other RiskProfile.human_review_required flag, or a concrete
       gap between what ControlPrescription mandates and what the
       Initiative currently has in place (HITL, audit artifacts,
       regulatory submission lead time), routes to
       REQUIRES_REVISION_BEFORE_APPROVAL.
    3. Otherwise, fall back to the coarse risk-tier gate.
    """
    low_confidence_frameworks = get_low_confidence_frameworks(risk_profile)
    if low_confidence_frameworks:
        return InitiativeStatus.AWAITING_HUMAN_REVIEW, (
            f"Classification confidence below {CONFIDENCE_REVIEW_THRESHOLD} for: "
            f"{', '.join(low_confidence_frameworks)}. Requires analyst review "
            f"before further pipeline processing."
        )

    gaps: List[str] = []

    mandatory_hitl_touchpoints = [
        t for t in control_prescription.controls.hitl_touchpoints if t.mandatory
    ]
    if mandatory_hitl_touchpoints and initiative.ai_system.hitl_planned == HITLPlanned.NO:
        triggers = "; ".join(t.trigger_description for t in mandatory_hitl_touchpoints)
        citations = ", ".join(
            sorted({f.value for t in mandatory_hitl_touchpoints for f in t.source_framework})
        )
        gaps.append(
            f"HITL required ({triggers}) per {citations}, but initiative has "
            f"hitl_planned=no."
        )

    # AuditArtifactRequirement has no `mandatory` flag of its own — every
    # entry the Control Prescription agent lists is a requirement.
    mandatory_audit_types = {
        a.artifact_type for a in control_prescription.controls.audit_artifacts
    }
    missing_audit_artifacts = mandatory_audit_types - set(initiative.existing_controls)
    if missing_audit_artifacts:
        gaps.append(
            f"Mandatory audit artifact(s) not present in existing_controls: "
            f"{', '.join(sorted(missing_audit_artifacts))}."
        )

    if initiative.target_deployment_date:
        days_to_deploy = (initiative.target_deployment_date - date.today()).days
        for submission in control_prescription.controls.regulatory_submissions:
            if submission.mandatory and days_to_deploy < submission.submission_deadline_days_before_deployment:
                gaps.append(
                    f"Mandatory regulatory submission '{submission.submission_type}' to "
                    f"{submission.submission_authority} requires "
                    f"{submission.submission_deadline_days_before_deployment} days' lead time "
                    f"before deployment, but target deployment is only {days_to_deploy} day(s) away."
                )

    if gaps or risk_profile.human_review_required:
        rationale_parts = gaps if gaps else list(risk_profile.human_review_reasons)
        if not rationale_parts:
            rationale_parts = ["Flagged for human review by Risk Classifier."]
        return InitiativeStatus.REQUIRES_REVISION_BEFORE_APPROVAL, " ".join(rationale_parts)

    if risk_profile.overall_risk_tier in (OverallRiskTier.HIGH, OverallRiskTier.CRITICAL):
        return InitiativeStatus.CONTROL_PRESCRIPTION_PENDING, (
            "High/critical risk tier requires control prescription review before build approval."
        )

    return InitiativeStatus.APPROVED_FOR_BUILD, (
        "Low/moderate risk tier with no outstanding mandatory control gaps."
    )

# Global DB Path
DB_PATH = "glasswing_governance.db"

def execute_sqlite_command(query: str, params: tuple = ()) -> str:
    """Executes a modification SQL query (INSERT, UPDATE, DELETE) against the portfolio database."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return "SQL Command completed successfully."
    except Exception as e:
        return f"Database error: {str(e)}"

def query_sqlite_data(query: str, params: tuple = ()) -> str:
    """Executes a selection SQL query (SELECT) and returns the output in JSON format."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return json.dumps([dict(row) for row in rows], default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


class PortfolioManagerAgent:
    def __init__(self, db_url: str = None):
        global DB_PATH
        if db_url:
            if db_url.startswith("sqlite:///"):
                DB_PATH = db_url.replace("sqlite:///", "")
            else:
                DB_PATH = db_url
                
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        if self.api_key:
            os.environ["ANTHROPIC_API_KEY"] = self.api_key
            
        self.prompt_path = Path(__file__).parent.parent / "prompts" / "portfolio_manager.md"
        self.system_prompt = self._load_prompt()
        self.initialize_db()
        
        # Instantiate the ADK agent, equipping it with SQLite database tools
        self.adk_agent = Agent(
            name="portfolio_manager",
            model="anthropic/claude-sonnet-4-5-20250115",
            instruction=self.system_prompt,
            tools=[execute_sqlite_command, query_sqlite_data]
        )

    def _load_prompt(self) -> str:
        if self.prompt_path.exists():
            return self.prompt_path.read_text(encoding="utf-8")
        return "You are the Portfolio Manager Agent. Manage SQLite records."

    def initialize_db(self):
        """Prepares database tables."""
        execute_sqlite_command("""
            CREATE TABLE IF NOT EXISTS initiatives (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL,
                risk_tier TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                manifest_json TEXT
            )
        """)
        execute_sqlite_command("""
            CREATE TABLE IF NOT EXISTS transitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                initiative_id TEXT NOT NULL,
                from_status TEXT NOT NULL,
                to_status TEXT NOT NULL,
                transitioned_by TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reason TEXT,
                FOREIGN KEY (initiative_id) REFERENCES initiatives(id)
            )
        """)
        # The original schema only ever stored a manifest *hash* plus a
        # single flat risk_tier string -- no sponsor, no target date, and
        # no way to retrieve the actual RiskProfile/ControlPrescription
        # content after the fact. Reports A/B/C all need that content, so
        # extend the table. ALTER TABLE ADD COLUMN has no IF NOT EXISTS in
        # SQLite, so check PRAGMA table_info() first -- this makes it safe
        # to run against a database created by an earlier session.
        for column, col_type in (
            ("sponsor_business_unit", "TEXT"),
            ("sponsor_owner", "TEXT"),
            ("target_deployment_date", "TEXT"),
            ("risk_profile_json", "TEXT"),
            ("control_prescription_json", "TEXT"),
        ):
            self._ensure_column("initiatives", column, col_type)

    @staticmethod
    def _ensure_column(table: str, column: str, col_type: str) -> None:
        existing_cols = json.loads(query_sqlite_data(f"PRAGMA table_info({table})"))
        if not any(c["name"] == column for c in existing_cols):
            execute_sqlite_command(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")

    def create_initiative_record(self, initiative: Initiative) -> None:
        """Creates the initiative's row in the portfolio DB with
        status=INTAKE. Called once, at the start of the pipeline, before
        any state transition is logged — a transition needs a real
        previous state to reference, and INTAKE is that starting point.
        INSERT OR IGNORE makes this safe to call more than once (e.g. on
        replay) without clobbering whatever state the initiative has
        since moved to."""
        execute_sqlite_command("""
            INSERT OR IGNORE INTO initiatives
                (id, name, description, status, risk_tier, last_updated, manifest_json,
                 sponsor_business_unit, sponsor_owner, target_deployment_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(initiative.initiative_id),
            initiative.name,
            initiative.description,
            InitiativeStatus.INTAKE.value,
            None,
            datetime.utcnow().isoformat(),
            None,
            initiative.sponsor.business_unit,
            initiative.sponsor.owner,
            initiative.target_deployment_date.isoformat() if initiative.target_deployment_date else None,
        ))

    def _record_transition(
        self,
        initiative_id,
        previous_status: InitiativeStatus,
        new_status: InitiativeStatus,
        transitioned_by: str,
        rationale: str,
    ) -> StateTransition:
        """Single choke point for writing a state transition. Constructs
        and validates a StateTransition Pydantic object — this is the
        actual enforcement of the `rationale` min_length=10 validator;
        previously nothing in this file ever built a StateTransition, so
        that constraint was never checked at runtime. Raises
        pydantic.ValidationError if rationale is too short."""
        transition = StateTransition(
            initiative_id=initiative_id,
            previous_state=previous_status,
            new_state=new_status,
            transitioned_at=datetime.utcnow(),
            transitioned_by=transitioned_by,
            rationale=rationale,
        )
        execute_sqlite_command("""
            UPDATE initiatives SET status = ?, last_updated = ? WHERE id = ?
        """, (new_status.value, transition.transitioned_at.isoformat(), str(initiative_id)))
        execute_sqlite_command("""
            INSERT INTO transitions (initiative_id, from_status, to_status, transitioned_by, timestamp, reason)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            str(initiative_id),
            previous_status.value,
            new_status.value,
            transitioned_by,
            transition.transitioned_at.isoformat(),
            rationale,
        ))
        return transition

    def register_initiative(self,
                            initiative: Initiative,
                            risk_profile: RiskProfile,
                            control_prescription: ControlPrescription,
                            transitioned_by: str = "system") -> Tuple[GovernanceManifest, InitiativeStatus, str]:
        """Invokes SQLite tools to log the new initiative and creates the versioned manifest."""
        import hashlib
        manifest_data = {
            "initiative": initiative.model_dump(),
            "risk_profile": risk_profile.model_dump(),
            "control_prescription": control_prescription.model_dump()
        }
        manifest_str = json.dumps(manifest_data, default=str, sort_keys=True)
        manifest_hash = hashlib.sha256(manifest_str.encode("utf-8")).hexdigest()
        
        # Build manifest
        manifest = GovernanceManifest(
            manifest_version=1,
            initiative_id=initiative.initiative_id,
            status=ManifestStatus.DRAFT,
            initiative_ref=initiative.initiative_id,
            risk_profile_ref=risk_profile.risk_profile_id,
            control_prescription_ref=control_prescription.control_prescription_id,
            initiative_hash=hashlib.sha256(json.dumps(initiative.model_dump(), default=str).encode("utf-8")).hexdigest(),
            risk_profile_hash=hashlib.sha256(json.dumps(risk_profile.model_dump(), default=str).encode("utf-8")).hexdigest(),
            control_prescription_hash=hashlib.sha256(json.dumps(control_prescription.model_dump(), default=str).encode("utf-8")).hexdigest(),
            manifest_hash=manifest_hash,
            executive_summary=control_prescription.executive_summary
        )

        status_assigned, transition_rationale = _determine_initiative_status(
            initiative, risk_profile, control_prescription
        )

        # Look up whatever status is actually on record before overwriting
        # it — previously this hardcoded from_status=INTAKE regardless of
        # the initiative's real prior state, which is wrong as soon as any
        # intermediate transition (e.g. classification_pending ->
        # control_prescription_pending) has already been logged upstream.
        existing_rows = json.loads(
            query_sqlite_data("SELECT status FROM initiatives WHERE id = ?", (str(initiative.initiative_id),))
        )
        previous_status = (
            InitiativeStatus(existing_rows[0]["status"]) if existing_rows else InitiativeStatus.INTAKE
        )

        # Run insertions using SQLite commands. Status/last_updated get
        # written again by _record_transition() below, immediately after —
        # this INSERT OR REPLACE exists to persist the manifest_json,
        # risk_tier, and full risk_profile/control_prescription content
        # (needed for reporting — previously only their hashes were kept,
        # so nothing could ever reconstruct the actual classification or
        # prescribed controls after the fact) which _record_transition()
        # doesn't touch.
        execute_sqlite_command("""
            INSERT OR REPLACE INTO initiatives
                (id, name, description, status, risk_tier, last_updated, manifest_json,
                 sponsor_business_unit, sponsor_owner, target_deployment_date,
                 risk_profile_json, control_prescription_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(initiative.initiative_id),
            initiative.name,
            initiative.description,
            previous_status.value,
            risk_profile.overall_risk_tier.value,
            datetime.utcnow().isoformat(),
            json.dumps(manifest.model_dump(), default=str),
            initiative.sponsor.business_unit,
            initiative.sponsor.owner,
            initiative.target_deployment_date.isoformat() if initiative.target_deployment_date else None,
            risk_profile.model_dump_json(),
            control_prescription.model_dump_json(),
        ))

        self._record_transition(
            initiative.initiative_id, previous_status, status_assigned, transitioned_by, transition_rationale
        )

        return manifest, status_assigned, transition_rationale

    def update_status(self, initiative_id: str, new_status: InitiativeStatus, transitioned_by: str, reason: str, risk_tier: Optional[str] = None) -> StateTransition:
        """Updates initiative state in SQLite database. Returns the
        validated StateTransition record (raises pydantic.ValidationError
        if `reason` is shorter than the schema's 10-character minimum).

        `risk_tier`, if given, is persisted alongside the transition. This
        matters for the low-confidence early-exit gate in
        orchestration/flow.py: a RiskProfile does exist at that point (it's
        what triggered the gate), even though no ControlPrescription or
        GovernanceManifest was ever produced — without this, initiatives
        routed to AWAITING_HUMAN_REVIEW would show a null risk tier in
        every report, despite the classification data being available."""
        # Find current status
        res_json = query_sqlite_data("SELECT status FROM initiatives WHERE id = ?", (initiative_id,))
        rows = json.loads(res_json)
        if not rows:
            raise ValueError(f"Initiative {initiative_id} not found.")

        previous_status = InitiativeStatus(rows[0]["status"])
        if risk_tier is not None:
            execute_sqlite_command(
                "UPDATE initiatives SET risk_tier = ? WHERE id = ?", (risk_tier, initiative_id)
            )
        return self._record_transition(
            uuid.UUID(initiative_id), previous_status, new_status, transitioned_by, reason
        )

    def get_portfolio_state(self) -> PortfolioState:
        """Retrieves and compiles a complete PortfolioState snapshot from SQLite database."""
        res_json = query_sqlite_data("""
            SELECT id, name, status, risk_tier, last_updated,
                   sponsor_business_unit, sponsor_owner, target_deployment_date
            FROM initiatives
        """)
        rows = json.loads(res_json)

        now = datetime.utcnow()
        terminal_statuses = {InitiativeStatus.DEPLOYED, InitiativeStatus.KILLED, InitiativeStatus.PARKED}

        summaries = []
        at_risk = []
        bottlenecks = []
        by_status = {s: 0 for s in InitiativeStatus}
        high_risk_count = 0
        deployed_count = 0

        for r in rows:
            status = InitiativeStatus(r["status"])
            last_updated = datetime.fromisoformat(r["last_updated"]) if r.get("last_updated") else None
            days_in_state = (now - last_updated).days if last_updated else 0
            target_date = date.fromisoformat(r["target_deployment_date"]) if r.get("target_deployment_date") else None

            summary = InitiativeSummary(
                initiative_id=r["id"],
                name=r["name"],
                sponsor_business_unit=r.get("sponsor_business_unit") or "Unknown",
                sponsor_owner=r.get("sponsor_owner") or "Unknown",
                current_status=status,
                overall_risk_tier=r["risk_tier"],
                target_deployment_date=target_date,
                last_updated=last_updated,
                days_in_current_state=days_in_state,
                blocking=status not in terminal_statuses and days_in_state > 14,
            )
            summaries.append(summary)

            by_status[status] += 1
            if r["risk_tier"] in ["high", "critical"]:
                high_risk_count += 1
            if status == InitiativeStatus.DEPLOYED:
                deployed_count += 1

            if target_date and status not in terminal_statuses and (target_date - now.date()).days <= 30:
                at_risk.append(summary)
            if status not in terminal_statuses and days_in_state > 14:
                bottlenecks.append(summary)

        recent_transitions_7d = []
        transition_rows = json.loads(query_sqlite_data("""
            SELECT initiative_id, from_status, to_status, transitioned_by, timestamp, reason
            FROM transitions
            ORDER BY id DESC
        """))
        for t in transition_rows:
            ts = datetime.fromisoformat(t["timestamp"])
            if (now - ts).days > 7:
                continue
            recent_transitions_7d.append(
                StateTransition(
                    initiative_id=t["initiative_id"],
                    previous_state=InitiativeStatus(t["from_status"]),
                    new_state=InitiativeStatus(t["to_status"]),
                    transitioned_at=ts,
                    transitioned_by=t["transitioned_by"],
                    rationale=t["reason"],
                )
            )

        return PortfolioState(
            snapshot_id=uuid.uuid4(),
            generated_at=now,
            total_initiatives=len(summaries),
            by_status=by_status,
            high_risk_count=high_risk_count,
            deployed_count=deployed_count,
            summaries=summaries,
            at_risk_of_missing_deadline=at_risk,
            recent_transitions_7d=recent_transitions_7d,
            bottlenecks=bottlenecks,
        )

    def generate_executive_briefing(self) -> str:
        """Instructs the ADK Agent to review database query results and write a briefing report."""
        # Query summaries to provide as context to Claude
        raw_db_json = query_sqlite_data("SELECT name, status, risk_tier FROM initiatives")

        prompt_input = f"""
        Please write a high-level executive portfolio briefing based on this database state:
        {raw_db_json}

        Format it as a clean regulator-ready Markdown report.
        """

        if not self.api_key:
            # Deterministic offline fallback -- this is the path actually
            # exercised without an ANTHROPIC_API_KEY. The previous version
            # of this fallback was a one-line stub ("Active initiatives
            # total: N") that didn't remotely satisfy the report's real
            # content requirements; this builds the real thing.
            return self._build_executive_briefing_markdown()

        try:
            response = self.adk_agent.run(prompt_input)
            return response.text
        except Exception as e:
            return f"Briefing generation error: {str(e)}"

    def _build_executive_briefing_markdown(self) -> str:
        """Report A: one-page executive briefing. Leads with whatever needs
        the exec's attention (bottlenecks, at-risk deadlines, unresolved
        high-risk items) before the routine status breakdown."""
        state = self.get_portfolio_state()
        lines = ["# Executive Portfolio Briefing", ""]
        lines.append(f"_Generated {state.generated_at.strftime('%Y-%m-%d %H:%M UTC')} - {state.total_initiatives} initiative(s) in the portfolio._")
        lines.append("")

        needs_attention = state.bottlenecks or state.at_risk_of_missing_deadline
        lines.append("## REQUIRES YOUR ATTENTION" if needs_attention else "## Nothing Currently Requires Escalation")
        lines.append("")
        # At-risk deployment deadlines lead — a missed regulatory/customer
        # commitment date is the most time-sensitive thing an exec can act
        # on, so it must be the first thing under the surfaced items, not
        # after bottlenecks.
        if state.at_risk_of_missing_deadline:
            lines.append(f"**{len(state.at_risk_of_missing_deadline)} initiative(s) at risk of missing their target deployment date:**")
            for s in state.at_risk_of_missing_deadline:
                days_left = (s.target_deployment_date - state.generated_at.date()).days
                deadline_desc = f"{days_left} day(s) away" if days_left >= 0 else f"{-days_left} day(s) OVERDUE"
                lines.append(f"- **{s.name}** ({s.sponsor_business_unit}) - target {s.target_deployment_date}, {deadline_desc}, currently `{s.current_status.value}`")
            lines.append("")
        if state.bottlenecks:
            lines.append(f"**{len(state.bottlenecks)} initiative(s) stalled more than 14 days in their current state:**")
            for s in state.bottlenecks:
                lines.append(f"- **{s.name}** ({s.sponsor_business_unit}) - stuck in `{s.current_status.value}` for {s.days_in_current_state} days")
            lines.append("")

        high_risk_unresolved = [
            s for s in state.summaries
            if s.overall_risk_tier in ("high", "critical")
            and s.current_status not in (InitiativeStatus.DEPLOYED, InitiativeStatus.KILLED, InitiativeStatus.PARKED, InitiativeStatus.APPROVED_FOR_BUILD, InitiativeStatus.IN_BUILD, InitiativeStatus.AWAITING_DEPLOYMENT_GATE)
        ]
        lines.append(f"## High-Risk Initiatives Needing Attention: {len(high_risk_unresolved)}")
        for s in high_risk_unresolved:
            lines.append(f"- **{s.name}** - `{s.current_status.value}` (risk tier: {s.overall_risk_tier})")
        lines.append("")

        lines.append("## Portfolio by Status")
        lines.append("| Status | Count |")
        lines.append("|---|---|")
        for status, count in state.by_status.items():
            if count:
                lines.append(f"| {status.value} | {count} |")
        lines.append("")
        lines.append(f"**Total: {state.total_initiatives}** | **High/Critical risk: {state.high_risk_count}** | **Deployed: {state.deployed_count}**")
        lines.append("")

        lines.append(f"## Recent State Changes (last 7 days): {len(state.recent_transitions_7d)}")
        for t in state.recent_transitions_7d[:15]:
            lines.append(f"- {t.transitioned_at.strftime('%Y-%m-%d')}: `{t.previous_state.value}` -> `{t.new_state.value}` (by {t.transitioned_by}) - {t.rationale}")
        lines.append("")

        lines.append("## Recommended Executive Actions")
        actions = []
        for s in state.at_risk_of_missing_deadline:
            actions.append(f"Escalate **{s.name}** - target deployment date is at risk; still in `{s.current_status.value}`.")
        for s in state.bottlenecks:
            actions.append(f"Unblock **{s.name}** - has been in `{s.current_status.value}` for {s.days_in_current_state} days with no progress.")
        for s in high_risk_unresolved:
            actions.append(f"Assign a reviewer to **{s.name}** - high/critical risk tier awaiting resolution.")
        if not actions:
            actions.append("No executive action required this period - portfolio is moving normally.")
        for a in actions:
            lines.append(f"1. {a}")

        return "\n".join(lines)

    def generate_operational_dashboard(self) -> Dict[str, Any]:
        """Report B: structured JSON for Streamlit consumption. Everything
        is derived from get_portfolio_state() plus per-initiative control
        prescription content, not re-queried independently, so this can
        never drift from what the executive briefing and the DB itself
        show."""
        state = self.get_portfolio_state()

        by_state: Dict[str, list] = {}
        for s in state.summaries:
            by_state.setdefault(s.current_status.value, []).append({
                "initiative_id": str(s.initiative_id),
                "name": s.name,
                "sponsor_business_unit": s.sponsor_business_unit,
                "sponsor_owner": s.sponsor_owner,
                "overall_risk_tier": s.overall_risk_tier,
                "target_deployment_date": s.target_deployment_date.isoformat() if s.target_deployment_date else None,
                "last_updated": s.last_updated.isoformat() if s.last_updated else None,
                "days_in_current_state": s.days_in_current_state,
            })

        bottlenecks = [
            {
                "initiative_id": str(s.initiative_id),
                "name": s.name,
                "current_status": s.current_status.value,
                "days_in_current_state": s.days_in_current_state,
                "sponsor_owner": s.sponsor_owner,
            }
            for s in state.bottlenecks
        ]

        # Control implementation progress for in_build initiatives. NOTE:
        # ControlPrescription has no per-control "implemented" flag
        # anywhere in the schema, so this reports the *count of controls
        # that must be implemented* (from the stored prescription), not
        # actual completion progress -- that data doesn't exist yet. Flagged
        # in the session report as a gap, not silently glossed over here.
        in_build_progress = []
        in_build_rows = json.loads(query_sqlite_data(
            "SELECT id, name, control_prescription_json FROM initiatives WHERE status = ?",
            (InitiativeStatus.IN_BUILD.value,)
        ))
        for row in in_build_rows:
            entry = {"initiative_id": row["id"], "name": row["name"], "controls_to_implement": 0, "breakdown": {}}
            if row.get("control_prescription_json"):
                cp = json.loads(row["control_prescription_json"])
                controls = cp.get("controls", {})
                breakdown = {k: len(v) for k, v in controls.items() if isinstance(v, list)}
                entry["breakdown"] = breakdown
                entry["controls_to_implement"] = sum(breakdown.values())
            in_build_progress.append(entry)

        # Pending reviews by reviewer role.
        pending_by_role: Dict[str, list] = {}
        review_rows = json.loads(query_sqlite_data(
            "SELECT id, name, status, control_prescription_json FROM initiatives WHERE status IN (?, ?)",
            (InitiativeStatus.AWAITING_HUMAN_REVIEW.value, InitiativeStatus.REQUIRES_REVISION_BEFORE_APPROVAL.value)
        ))
        for row in review_rows:
            role = "Risk Classification Analyst" if row["status"] == InitiativeStatus.AWAITING_HUMAN_REVIEW.value else "Governance Reviewer"
            if row.get("control_prescription_json"):
                cp = json.loads(row["control_prescription_json"])
                hitl = cp.get("controls", {}).get("hitl_touchpoints", [])
                if hitl:
                    role = hitl[0].get("reviewer_role", role)
            pending_by_role.setdefault(role, []).append({
                "initiative_id": row["id"], "name": row["name"], "status": row["status"],
            })

        return {
            "generated_at": state.generated_at.isoformat(),
            "total_initiatives": state.total_initiatives,
            "by_state": by_state,
            "bottlenecks": bottlenecks,
            "in_build_control_progress": in_build_progress,
            "pending_reviews_by_role": pending_by_role,
        }

    def generate_regulator_inventory(self) -> str:
        """Report C: formal Markdown inventory of all DEPLOYED initiatives
        with their full multi-framework classification and control
        citations, for regulator on-demand review."""
        deployed_rows = json.loads(query_sqlite_data(
            "SELECT id, name, status, last_updated, risk_profile_json, control_prescription_json "
            "FROM initiatives WHERE status = ?",
            (InitiativeStatus.DEPLOYED.value,)
        ))

        lines = ["# Regulator-Ready AI Systems Inventory", ""]
        lines.append(f"_As of {datetime.utcnow().strftime('%Y-%m-%d')}. Covers all initiatives currently in DEPLOYED status._")
        lines.append("")

        if not deployed_rows:
            lines.append("No initiatives are currently in DEPLOYED status.")
            return "\n".join(lines)

        for row in deployed_rows:
            lines.append(f"## {row['name']}")
            lines.append(f"- **Last updated**: {row['last_updated']}")
            if row.get("risk_profile_json"):
                rp = json.loads(row["risk_profile_json"])
                eu = rp["classifications"]["eu_ai_act"]
                nist = rp["classifications"]["nist_ai_rmf"]
                co = rp["classifications"]["colorado_sb_205"]
                lines.append(f"- **EU AI Act tier**: {eu['tier']} (citations: {', '.join(eu['citations']) or 'none'})")
                lines.append(
                    f"- **NIST AI RMF attention**: Govern={nist['govern_attention']}, "
                    f"Map={nist['map_attention']}, Measure={nist['measure_attention']}, "
                    f"Manage={nist['manage_attention']} (citations: {', '.join(nist['citations']) or 'none'})"
                )
                lines.append(
                    f"- **Colorado SB 205**: applicable={co['applicable']}"
                    + (f", category={co['high_risk_category']}" if co.get("high_risk_category") else "")
                    + f" (citations: {', '.join(co['citations']) or 'none'})"
                )
            # Control prescription citations, grouped by framework. Guardrails
            # carry a dedicated source_citation string; HITL touchpoints and
            # audit artifacts only carry source_framework (no citation field
            # in the schema), so those are labeled by what they require;
            # regulatory submissions' submission_type text already names the
            # specific article (e.g. "EU AI Act Article 14 (Human
            # Oversight)..."), so it's used directly. This section is always
            # printed, even when empty, rather than silently omitted, since a
            # regulator needs to see "no mandatory controls" as an explicit
            # statement, not an absent line.
            lines.append("- **Control prescription citations**:")
            citations_by_framework = {}
            if row.get("control_prescription_json"):
                cp = json.loads(row["control_prescription_json"])
                controls = cp.get("controls", {})
                for g in controls.get("guardrails", []):
                    if g.get("source_citation"):
                        for fw in g.get("source_framework", []):
                            citations_by_framework.setdefault(fw, set()).add(g["source_citation"])
                for sub in controls.get("regulatory_submissions", []):
                    if sub.get("submission_type"):
                        for fw in sub.get("source_framework", []):
                            citations_by_framework.setdefault(fw, set()).add(sub["submission_type"])
                for hitl in controls.get("hitl_touchpoints", []):
                    for fw in hitl.get("source_framework", []):
                        citations_by_framework.setdefault(fw, set()).add(
                            f"HITL requirement: {hitl.get('trigger_description', 'human review')[:70]}"
                        )
                for aud in controls.get("audit_artifacts", []):
                    for fw in aud.get("source_framework", []):
                        citations_by_framework.setdefault(fw, set()).add(
                            f"Audit artifact: {aud.get('artifact_type', 'retention requirement')[:70]}"
                        )
            if citations_by_framework:
                for framework in sorted(citations_by_framework):
                    for citation in sorted(citations_by_framework[framework]):
                        lines.append(f"  - {framework}: {citation}")
            else:
                lines.append("  - None (no mandatory controls prescribed for this risk tier)")
            lines.append("")

        return "\n".join(lines)
