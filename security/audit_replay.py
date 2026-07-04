import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from datetime import datetime
from agents.audit_trail import AuditTrailAgent
from schemas.audit_log import AgentID, ActionType, SensitivityClassification

def run_audit_validation_demo() -> bool:
    print("=== Running Glasswing Cryptographic Audit Validation Demo ===")
    
    # Initialize agent pointing to a temporary or demo db
    demo_db_path = "glasswing_audit_demo.db"
    if Path(demo_db_path).exists():
        Path(demo_db_path).unlink()
        
    audit_agent = AuditTrailAgent(db_url=f"sqlite:///{demo_db_path}")
    
    print("1. Logging a series of agent events...")
    
    # Action 1: Onboarding Agent completes intake
    e1 = audit_agent.log_action(
        agent_id=AgentID.ONBOARDING,
        action=ActionType.CREATE,
        payload={"initiative_name": "Applicant Screening System", "author": "HR Tech Dept"},
        initiative_id="init-100",
        sensitivity=SensitivityClassification.INTERNAL
    )
    print(f"   [Logged] Action 1. Signature prefix: {e1.signature[:12]}")
    
    # Action 2: Risk Classifier reviews the initiative
    e2 = audit_agent.log_action(
        agent_id=AgentID.RISK_CLASSIFIER,
        action=ActionType.EVALUATE,
        payload={"eu_risk_tier": "High Risk", "colorado_sb_205_high_risk": True, "score": 8.5},
        initiative_id="init-100",
        sensitivity=SensitivityClassification.INTERNAL
    )
    print(f"   [Logged] Action 2. Previous Hash matches Action 1 Sig: {e2.previous_hash == e1.signature}")
    print(f"   [Logged] Action 2. Signature prefix: {e2.signature[:12]}")
    
    # Action 3: Control Prescription registers requirements
    e3 = audit_agent.log_action(
        agent_id=AgentID.CONTROL_PRESCRIPTION,
        action=ActionType.PRESCRIBE,
        payload={"controls_prescribed": ["CTRL-BIAS-01", "CTRL-HITL-02"]},
        initiative_id="init-100",
        sensitivity=SensitivityClassification.INTERNAL
    )
    print(f"   [Logged] Action 3. Previous Hash matches Action 2 Sig: {e3.previous_hash == e2.signature}")
    print(f"   [Logged] Action 3. Signature prefix: {e3.signature[:12]}")

    print("\n2. Validating audit trail hash chain integrity...")
    is_valid_before = audit_agent.validate_chain()
    print(f"   Validation Result: {'[SUCCESS] Chain is intact and fully verified.' if is_valid_before else '[FAILED] Chain is broken!'}")
    
    if not is_valid_before:
        # Cleanup
        Path(demo_db_path).unlink()
        return False

    print("\n3. Simulating a tampering attack (modifying Action 2's payload)...")
    # Tamper with the database records behind the scenes
    tampered_payload = {"eu_risk_tier": "Minimal or No Risk", "colorado_sb_205_high_risk": False, "score": 1.0}
    audit_agent.tamper_entry(e2.entry_id, tampered_payload)
    print("   [Tampered] Log record payload altered manually in SQLite.")

    print("\n4. Re-running validation over the audit trail...")
    is_valid_after = audit_agent.validate_chain()
    print(f"   Validation Result: {'[SUCCESS] Chain is intact (Attack Succeeded/Validation Failed!)' if is_valid_after else '[TAMPER DETECTED] Validation successfully flagged database tampering!'}")
    
    # Cleanup
    if Path(demo_db_path).exists():
        Path(demo_db_path).unlink()
        
    print("=============================================================")
    return is_valid_before and (not is_valid_after)

if __name__ == "__main__":
    success = run_audit_validation_demo()
    sys.exit(0 if success else 1)
