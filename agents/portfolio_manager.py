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
       kept distinct from substantive governance gaps.
    2. Any other RiskProfile.human_review_required flag, or a concrete
       gap between what ControlPrescription mandates and what the
       Initiative currently has in place (HITL, audit artifacts,
       regulatory submission lead time), routes to
       REQUIRES_REVISION_BEFORE_APPROVAL.
    3. Otherwise, fall back to the coarse risk-tier gate.
    """
    low_confidence_frameworks = [
        name
        for name, classification in (
            ("eu_ai_act", risk_profile.classifications.eu_ai_act),
            ("nist_ai_rmf", risk_profile.classifications.nist_ai_rmf),
            ("colorado_sb_205", risk_profile.classifications.colorado_sb_205),
        )
        if classification.confidence < CONFIDENCE_REVIEW_THRESHOLD
    ]
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

        # Run insertions using SQLite commands
        execute_sqlite_command("""
            INSERT OR REPLACE INTO initiatives (id, name, description, status, risk_tier, last_updated, manifest_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            str(initiative.initiative_id),
            initiative.name,
            initiative.description,
            status_assigned.value,
            risk_profile.overall_risk_tier.value,
            datetime.utcnow().isoformat(),
            json.dumps(manifest.model_dump(), default=str)
        ))
        
        execute_sqlite_command("""
            INSERT INTO transitions (initiative_id, from_status, to_status, transitioned_by, timestamp, reason)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            str(initiative.initiative_id),
            InitiativeStatus.INTAKE.value,
            status_assigned.value,
            transitioned_by,
            datetime.utcnow().isoformat(),
            transition_rationale
        ))

        return manifest, status_assigned, transition_rationale

    def update_status(self, initiative_id: str, new_status: InitiativeStatus, transitioned_by: str, reason: str):
        """Updates initiative state in SQLite database."""
        # Find current status
        res_json = query_sqlite_data("SELECT status FROM initiatives WHERE id = ?", (initiative_id,))
        rows = json.loads(res_json)
        if not rows:
            raise ValueError(f"Initiative {initiative_id} not found.")
            
        from_status = rows[0]["status"]
        
        execute_sqlite_command("""
            UPDATE initiatives 
            SET status = ?, last_updated = ?
            WHERE id = ?
        """, (new_status.value, datetime.utcnow().isoformat(), initiative_id))
        
        execute_sqlite_command("""
            INSERT INTO transitions (initiative_id, from_status, to_status, transitioned_by, timestamp, reason)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            initiative_id,
            from_status,
            new_status.value,
            transitioned_by,
            datetime.utcnow().isoformat(),
            reason
        ))

    def get_portfolio_state(self) -> PortfolioState:
        """Retrieves and compiles a complete PortfolioState snapshot from SQLite database."""
        res_json = query_sqlite_data("SELECT id, name, status, risk_tier, last_updated FROM initiatives")
        rows = json.loads(res_json)
        
        summaries = []
        by_status = {s: 0 for s in InitiativeStatus}
        high_risk_count = 0
        deployed_count = 0
        
        for r in rows:
            status = InitiativeStatus(r["status"])
            last_updated = datetime.fromisoformat(r["last_updated"]) if r.get("last_updated") else None
            summaries.append(
                InitiativeSummary(
                    initiative_id=r["id"],
                    name=r["name"],
                    sponsor_business_unit="Unknown",
                    sponsor_owner="Unknown",
                    current_status=status,
                    overall_risk_tier=r["risk_tier"],
                    last_updated=last_updated,
                    days_in_current_state=0
                )
            )
            by_status[status] += 1
            if r["risk_tier"] in ["high", "critical"]:
                high_risk_count += 1
            if status == InitiativeStatus.DEPLOYED:
                deployed_count += 1
                
        import uuid
        return PortfolioState(
            snapshot_id=uuid.uuid4(),
            generated_at=datetime.utcnow(),
            total_initiatives=len(summaries),
            by_status=by_status,
            high_risk_count=high_risk_count,
            deployed_count=deployed_count,
            summaries=summaries
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
            # Fallback format offline
            return f"# Executive Briefing\nActive initiatives total: {len(json.loads(raw_db_json))}"

        try:
            response = self.adk_agent.run(prompt_input)
            return response.text
        except Exception as e:
            return f"Briefing generation error: {str(e)}"
