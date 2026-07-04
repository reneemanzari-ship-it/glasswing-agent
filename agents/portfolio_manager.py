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
from datetime import datetime
from typing import Dict, Any, List, Optional
from google.adk import Agent

from schemas.initiative import Initiative
from schemas.risk_profile import RiskProfile
from schemas.control_prescription import ControlPrescription
from schemas.governance_manifest import GovernanceManifest, ManifestStatus
from schemas.portfolio_state import PortfolioState, InitiativeStatus, InitiativeSummary, StateTransition

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
                intended_use TEXT,
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
                            transitioned_by: str = "system") -> GovernanceManifest:
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

        status_assigned = InitiativeStatus.CLASSIFICATION_PENDING
        if risk_profile.overall_risk_tier == OverallRiskTier.HIGH or risk_profile.overall_risk_tier == OverallRiskTier.CRITICAL:
            status_assigned = InitiativeStatus.CONTROL_PRESCRIPTION_PENDING

        # Run insertions using SQLite commands
        execute_sqlite_command("""
            INSERT OR REPLACE INTO initiatives (id, name, description, intended_use, status, risk_tier, last_updated, manifest_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(initiative.initiative_id),
            initiative.name,
            initiative.description,
            initiative.intended_use,
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
            "Completed onboarding and initial framework risk review."
        ))
        
        return manifest

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
            summaries.append(
                InitiativeSummary(
                    initiative_id=r["id"],
                    name=r["name"],
                    sponsor_business_unit="Unknown",
                    sponsor_owner="Unknown",
                    current_status=status,
                    overall_risk_tier=r["risk_tier"],
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
