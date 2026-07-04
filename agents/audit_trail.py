"""
Google ADK to Anthropic Claude Routing Pattern:
----------------------------------------------
Model: anthropic/claude-sonnet-4-5-20250115 (via LiteLLM router)
Instructions: Dynamically loaded from prompts/audit_trail.md
Tools: Exposes hash-chain verification tool.
"""

import os
import hashlib
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from google.adk import Agent
from schemas.audit_log import AuditLogEntry, AgentID, ActionType, SensitivityClassification

AUDIT_LOG_DB: List[Dict[str, Any]] = []

def verify_audit_log_chain() -> str:
    """Verifies the integrity of the audit log hash chain."""
    previous_hash = None
    for idx, entry in enumerate(AUDIT_LOG_DB):
        entry_data = entry.copy()
        # Exclude chain_hash to verify
        chain_hash = entry_data.pop("chain_hash")
        
        # Calculate expected hash
        serialized = json.dumps(entry_data, default=str, sort_keys=True)
        if previous_hash:
            payload = f"{serialized}_{previous_hash}"
        else:
            payload = serialized
        expected = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        
        if expected != chain_hash:
            return f"CORRUPTION_DETECTED: Entry index {idx} (ID: {entry.get('audit_log_id')}) failed hash matching. Expected: {expected}, Found: {chain_hash}"
            
        previous_hash = chain_hash
    return "SUCCESS: Audit trail hash chain verified. Zero tampering detected."


class AuditTrailAgent:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if self.api_key:
            os.environ["ANTHROPIC_API_KEY"] = self.api_key
            
        self.prompt_path = Path(__file__).parent.parent / "prompts" / "audit_trail.md"
        self.system_prompt = self._load_prompt()
        
        # Instantiate ADK Agent, giving it audit chain verification tools
        self.adk_agent = Agent(
            name="audit_trail",
            model="anthropic/claude-sonnet-4-5-20250115",
            instruction=self.system_prompt,
            tools=[verify_audit_log_chain]
        )

    def _load_prompt(self) -> str:
        if self.prompt_path.exists():
            return self.prompt_path.read_text(encoding="utf-8")
        return "You are the Audit Trail Agent. Write append-only cryptographic compliance trails."

    def log_event(self, 
                  agent_id: AgentID, 
                  action_type: ActionType, 
                  initiative_id: Optional[Any], 
                  input_hash: str, 
                  output_hash: str,
                  public_context: Optional[str] = None) -> AuditLogEntry:
        """Appends a new event entry into the cryptographic hash chain."""
        import uuid
        
        prev_id = None
        prev_hash = None
        if AUDIT_LOG_DB:
            last_entry = AUDIT_LOG_DB[-1]
            prev_id = last_entry["audit_log_id"]
            prev_hash = last_entry["chain_hash"]
            
        entry_id = uuid.uuid4()
        timestamp = datetime.utcnow()
        
        # Build entry without chain hash first
        entry_dict = {
            "audit_log_id": entry_id,
            "timestamp": timestamp,
            "agent_id": agent_id,
            "agent_version": "1.0.0",
            "action_type": action_type,
            "initiative_id": initiative_id,
            "model_id": "claude-sonnet-4-5-20250115",
            "prompt_manifest_sha": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
            "input_hash": input_hash,
            "output_hash": output_hash,
            "duration_ms": 100,
            "sensitivity_classification": SensitivityClassification.INTERNAL,
            "previous_audit_log_id": prev_id,
            "public_context": public_context
        }
        
        # Compute chain hash
        serialized = json.dumps(entry_dict, default=str, sort_keys=True)
        if prev_hash:
            payload = f"{serialized}_{prev_hash}"
        else:
            payload = serialized
        chain_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        
        # Store
        entry_dict["chain_hash"] = chain_hash
        AUDIT_LOG_DB.append(entry_dict)
        
        return AuditLogEntry(**entry_dict)

    def verify_trail(self) -> str:
        """Invokes ADK agent to perform chain verification and write audit assurance report."""
        prompt_input = """
        Please run verify_audit_log_chain to verify all log blocks, and write a compliance verification summary report.
        """
        
        if not self.api_key:
            # Fallback local query offline
            return f"Audit Trail Status: {verify_audit_log_chain()}"

        try:
            response = self.adk_agent.run(prompt_input)
            return response.text
        except Exception as e:
            return f"Audit verification execution error: {str(e)}"
