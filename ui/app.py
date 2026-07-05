import sys
import uuid
import json
import hashlib
import asyncio
from pathlib import Path
from datetime import datetime, date
from decimal import Decimal
import streamlit as st
import pandas as pd

sys.path.append(str(Path(__file__).parent.parent))

from orchestration.flow import GlasswingGovernanceOrchestrator
from schemas.initiative import (
    Initiative, Sponsor, AISystemCharacteristics, DataCharacteristics,
    ImpactCharacteristics, IntakeMetadata, AISystemType, AutonomyLevel,
    HITLPlanned, DataSensitivity, UserScope, BusinessImpactTier, Reversibility
)
from schemas.portfolio_state import InitiativeStatus
from schemas.audit_log import AgentID, ActionType
from agents.audit_trail import AUDIT_LOG_DB

# Set page config for wide layout and dark theme style
st.set_page_config(
    page_title="Glasswing AI Governance System",
    page_icon="🦋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject custom CSS for premium dark-mode, glassmorphism, and gradients
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Space+Grotesk:wght@400;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    .stApp {
        background-color: #0d0f14;
        color: #e2e8f0;
    }
    
    .gradient-text {
        background: linear-gradient(135deg, #38bdf8 0%, #a855f7 50%, #ec4899 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 800;
        font-size: 2.8rem !important;
        margin-bottom: 0.5rem;
    }
    
    .sub-gradient-text {
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 700;
        color: #94a3b8;
        font-size: 1.5rem !important;
        border-bottom: 2px solid #334155;
        padding-bottom: 0.5rem;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
    }

    .glass-card {
        background: rgba(30, 41, 59, 0.4);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
        backdrop-filter: blur(8px);
        margin-bottom: 1rem;
    }
    
    .metric-value {
        font-size: 2rem;
        font-weight: 800;
        color: #38bdf8;
    }
    
    .metric-label {
        font-size: 0.85rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .stButton>button {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid rgba(255,255,255,0.15) !important;
        border-radius: 8px !important;
        color: #f8fafc !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #38bdf8 0%, #a855f7 100%) !important;
        border-color: transparent !important;
        box-shadow: 0 0 15px rgba(56, 189, 248, 0.4) !important;
        transform: translateY(-2px);
    }
</style>
""", unsafe_allow_html=True)

# Initialize Orchestrator pointing to SQLite
DB_NAME = "glasswing_governance.db"
orchestrator = GlasswingGovernanceOrchestrator(db_url=f"sqlite:///{DB_NAME}")

# --- Initialize Form Session State for Preloading Scenarios ---
if "form_name" not in st.session_state:
    st.session_state["form_name"] = "Resume Screening Classifier"
if "form_desc" not in st.session_state:
    st.session_state["form_desc"] = "Vets and parses applicant resumes to match standard developer job requirements."
if "form_bu" not in st.session_state:
    st.session_state["form_bu"] = "Human Resources"
if "form_owner" not in st.session_state:
    st.session_state["form_owner"] = "Jane Doe"
if "form_type" not in st.session_state:
    st.session_state["form_type"] = AISystemType.LLM
if "form_autonomy" not in st.session_state:
    st.session_state["form_autonomy"] = AutonomyLevel.RECOMMEND_ONLY
if "form_hitl" not in st.session_state:
    st.session_state["form_hitl"] = HITLPlanned.YES
if "form_hitl_desc" not in st.session_state:
    st.session_state["form_hitl_desc"] = "HR Specialists sign off on recommended shortlists."
if "form_sources" not in st.session_state:
    st.session_state["form_sources"] = "resumes PDF"
if "form_sensitivity" not in st.session_state:
    st.session_state["form_sensitivity"] = [DataSensitivity.PII]
if "form_jurisdictions" not in st.session_state:
    st.session_state["form_jurisdictions"] = "US-CO"
if "form_scope" not in st.session_state:
    st.session_state["form_scope"] = [UserScope.INTERNAL_EMPLOYEES]
if "form_impact" not in st.session_state:
    st.session_state["form_impact"] = BusinessImpactTier.MODERATE
if "form_reversibility" not in st.session_state:
    st.session_state["form_reversibility"] = Reversibility.FULLY_REVERSIBLE

def load_scenario(scenario_type: str):
    if scenario_type == "loan":
        st.session_state["form_name"] = "LendFast Autonomous Underwriter"
        st.session_state["form_desc"] = "Autonomous credit evaluation and underwriting system that approves consumer loans without human review at 2:47 AM."
        st.session_state["form_bu"] = "Retail Lending Division"
        st.session_state["form_owner"] = "Alex Credit-Lead"
        st.session_state["form_type"] = AISystemType.CLASSICAL_ML
        st.session_state["form_autonomy"] = AutonomyLevel.FULLY_AUTONOMOUS
        st.session_state["form_hitl"] = HITLPlanned.NO
        st.session_state["form_hitl_desc"] = "System approves financial credits directly."
        st.session_state["form_sources"] = "credit scores bureau history, transaction lists"
        st.session_state["form_sensitivity"] = [DataSensitivity.PII, DataSensitivity.FINANCIAL]
        st.session_state["form_jurisdictions"] = "US-CO, EU"
        st.session_state["form_scope"] = [UserScope.CONSUMERS]
        st.session_state["form_impact"] = BusinessImpactTier.HIGH
        st.session_state["form_reversibility"] = Reversibility.PARTIALLY_REVERSIBLE
    elif scenario_type == "marketing":
        st.session_state["form_name"] = "AdCopy Generator"
        st.session_state["form_desc"] = "Generates marketing email copy drafts based on public product feature lists and blog posts."
        st.session_state["form_bu"] = "Marketing Operations"
        st.session_state["form_owner"] = "Sarah Creative"
        st.session_state["form_type"] = AISystemType.LLM
        st.session_state["form_autonomy"] = AutonomyLevel.RECOMMEND_ONLY
        st.session_state["form_hitl"] = HITLPlanned.YES
        st.session_state["form_hitl_desc"] = "All drafts reviewed by copywriters."
        st.session_state["form_sources"] = "public feature docs"
        st.session_state["form_sensitivity"] = [DataSensitivity.NONE]
        st.session_state["form_jurisdictions"] = "US-NY"
        st.session_state["form_scope"] = [UserScope.INTERNAL_EMPLOYEES]
        st.session_state["form_impact"] = BusinessImpactTier.LOW
        st.session_state["form_reversibility"] = Reversibility.FULLY_REVERSIBLE
    elif scenario_type == "chatbot":
        st.session_state["form_name"] = "Customer Support Assistant"
        st.session_state["form_desc"] = "Interactive assistant that answers general customer questions regarding shipping and refunds."
        st.session_state["form_bu"] = "Customer Care"
        st.session_state["form_owner"] = "Marcus Lead"
        st.session_state["form_type"] = AISystemType.HYBRID
        st.session_state["form_autonomy"] = AutonomyLevel.APPROVE_WITH_OVERRIDE
        st.session_state["form_hitl"] = HITLPlanned.PARTIAL
        st.session_state["form_hitl_desc"] = "Support agents take over chat on request."
        st.session_state["form_sources"] = "knowledge base, past support history"
        st.session_state["form_sensitivity"] = [DataSensitivity.PII]
        st.session_state["form_jurisdictions"] = "US-CO, US-NY"
        st.session_state["form_scope"] = [UserScope.CONSUMERS]
        st.session_state["form_impact"] = BusinessImpactTier.MODERATE
        st.session_state["form_reversibility"] = Reversibility.FULLY_REVERSIBLE

# --- SIDEBAR: System Status ---
st.sidebar.markdown("<h2 style='font-family:Space Grotesk; font-weight:700;'>GLASSWING CONTROL</h2>", unsafe_allow_html=True)
st.sidebar.markdown("---")
st.sidebar.markdown("### Agent Status")
st.sidebar.markdown("🟢 **Onboarding Intake Agent** (Plane 1)")
st.sidebar.markdown("🟢 **Risk Classifier Agent** (Plane 2)")
st.sidebar.markdown("🟢 **Control Prescription Agent** (Plane 2)")
st.sidebar.markdown("🟢 **Portfolio Manager Agent** (Plane 3)")
st.sidebar.markdown("🟢 **Audit Trail Agent** (Plane 3)")
st.sidebar.markdown("---")

if st.sidebar.button("Verify Hash Chain (Verify Trail)"):
    verify_result = orchestrator.audit_trail.verify_trail()
    if "CORRUPTION_DETECTED" not in verify_result:
        st.sidebar.success("Audit Trail Verification Succeeded! Zero tampering detected.")
    else:
        st.sidebar.error("Ledger validation failed!")

if st.sidebar.button("Reset Governance Database"):
    db_file = Path(DB_NAME)
    if db_file.exists():
        db_file.unlink()
    orchestrator.portfolio_manager.initialize_db()
    st.sidebar.warning("Database reset and schemas re-applied.")
    st.rerun()

# --- MAIN DASHBOARD HEADER ---
st.markdown("<h1 class='gradient-text'>GLASSWING AI GOVERNANCE</h1>", unsafe_allow_html=True)
st.markdown("<p style='color:#94a3b8; font-size:1.1rem;'>Autonomous Multi-Agent Guard Plane & Compliance Ledger</p>", unsafe_allow_html=True)

# Fetch stats
p_state = orchestrator.portfolio_manager.get_portfolio_state()
verify_str = orchestrator.audit_trail.verify_trail()
is_valid_ledger = "CORRUPTION_DETECTED" not in verify_str

# Metrics Card Layout
m_col1, m_col2, m_col3, m_col4 = st.columns(4)
with m_col1:
    st.markdown(f"<div class='glass-card'><div class='metric-label'>Audited Initiatives</div><div class='metric-value'>{p_state.total_initiatives}</div></div>", unsafe_allow_html=True)
with m_col2:
    st.markdown(f"<div class='glass-card'><div class='metric-label'>High Risk Systems</div><div class='metric-value' style='color:#f43f5e;'>{p_state.high_risk_count}</div></div>", unsafe_allow_html=True)
with m_col3:
    pending_count = p_state.by_status.get(InitiativeStatus.CONTROL_PRESCRIPTION_PENDING, 0)
    st.markdown(f"<div class='glass-card'><div class='metric-label'>Pending Controls</div><div class='metric-value' style='color:#fbbf24;'>{pending_count}</div></div>", unsafe_allow_html=True)
with m_col4:
    ledger_status = "<span style='color:#10b981;'>SECURE</span>" if is_valid_ledger else "<span style='color:#ef4444;'>TAMPERED</span>"
    st.markdown(f"<div class='glass-card'><div class='metric-label'>Ledger Integrity</div><div class='metric-value'>{ledger_status}</div></div>", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["Initiative Intake Portal", "Portfolio Directory", "Cryptographic Audit Ledger"])

with tab1:
    st.markdown("<h3 class='sub-gradient-text'>Load Pre-configured Scenario</h3>", unsafe_allow_html=True)
    sc_col1, sc_col2, sc_col3 = st.columns(3)
    with sc_col1:
        if st.button("Load 2:47am Loan Scenario"):
            load_scenario("loan")
            st.rerun()
    with sc_col2:
        if st.button("Load Low-Risk Marketing Scenario"):
            load_scenario("marketing")
            st.rerun()
    with sc_col3:
        if st.button("Load Medium-Risk Chatbot Scenario"):
            load_scenario("chatbot")
            st.rerun()

    st.markdown("<h3 class='sub-gradient-text'>Structured Intake Form</h3>", unsafe_allow_html=True)
    
    with st.form("structured_intake_form"):
        # Section A: Basics
        st.markdown("##### Section A: Initiative Basics")
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            name = st.text_input("Initiative Name", value=st.session_state["form_name"])
            target_date = st.date_input("Target Deployment Date", value=date.today())
        with col_a2:
            bu = st.text_input("Sponsor Business Unit", value=st.session_state["form_bu"])
            owner = st.text_input("Sponsor Named Owner", value=st.session_state["form_owner"])
            
        desc = st.text_area("System Description (Detailed)", value=st.session_state["form_desc"])
        
        st.markdown("---")
        
        # Section B: AI System Characteristics
        st.markdown("##### Section B: AI System Characteristics")
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            sys_type = st.selectbox("AI System Type", options=list(AISystemType), index=list(AISystemType).index(st.session_state["form_type"]))
            autonomy = st.selectbox("Autonomy Level", options=list(AutonomyLevel), index=list(AutonomyLevel).index(st.session_state["form_autonomy"]))
        with col_b2:
            hitl = st.selectbox("Human-In-The-Loop Planned", options=list(HITLPlanned), index=list(HITLPlanned).index(st.session_state["form_hitl"]))
            hitl_desc = st.text_input("HITL Action / Role Description", value=st.session_state["form_hitl_desc"])
            
        st.markdown("---")
        
        # Section C: Data Characteristics
        st.markdown("##### Section C: Data Characteristics")
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            sources = st.text_input("Data Sources (comma-separated)", value=st.session_state["form_sources"])
            sensitivity = st.multiselect("Data Sensitivity", options=list(DataSensitivity), default=st.session_state["form_sensitivity"])
        with col_c2:
            jurisdictions = st.text_input("Jurisdiction(s) of Data Subjects", value=st.session_state["form_jurisdictions"])
            
        st.markdown("---")
        
        # Section D: Impact Characteristics
        st.markdown("##### Section D: Impact Characteristics")
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            scope = st.multiselect("Customer/User Scope", options=list(UserScope), default=st.session_state["form_scope"])
            impact_tier = st.selectbox("Business Impact Tier", options=list(BusinessImpactTier), index=list(BusinessImpactTier).index(st.session_state["form_impact"]))
        with col_d2:
            reversibility = st.selectbox("Reversibility of Decisions", options=list(Reversibility), index=list(Reversibility).index(st.session_state["form_reversibility"]))
            
        submit_btn = st.form_submit_button("Submit Initiative to Governance Plane")

    if submit_btn:
        # Check for adversarial prompt injection triggers
        desc_lower = desc.lower()
        adversarial_indicators = ["ignore previous instructions", "you are now", "your new role is", "system:"]
        triggered_indicator = next((ind for ind in adversarial_indicators if ind in desc_lower), None)
        
        if triggered_indicator:
            # Visible Warning Defense Demonstration
            st.error("🚨 **Adversarial Pattern Detected. Submission Blocked.**")
            st.warning(f"**Security Flag Triggered**: The system identified an override bypass directive matching: *'{triggered_indicator}'* inside your description.")
            
            # Log adversarial attempt to compliance ledger immediately
            h_input = hashlib.sha256(desc.encode("utf-8")).hexdigest()
            h_output = hashlib.sha256(b"Blocked Adversarial Intent").hexdigest()
            orchestrator.audit_trail.log_event(
                agent_id=AgentID.ONBOARDING_INTAKE,
                action_type=ActionType.SECURITY_FLAG_RAISED,
                initiative_id=uuid.uuid4(),
                input_hash=h_input,
                output_hash=h_output,
                public_context=f"Security Alert: Blocked adversarial input containing override triggers: '{triggered_indicator}'"
            )
            st.info("The security alert and raw payload hash have been committed to the compliance audit trail ledger.")
        else:
            with st.spinner("Glasswing multi-agent plane coordinating evaluation..."):
                sources_list = [s.strip() for s in sources.split(",") if s.strip()]
                jurisdictions_list = [j.strip() for j in jurisdictions.split(",") if j.strip()]
                
                # Build Initiative model
                initiative_obj = Initiative(
                    name=name,
                    sponsor=Sponsor(business_unit=bu, owner=owner),
                    description=desc,
                    target_deployment_date=target_date,
                    ai_system=AISystemCharacteristics(
                        type=sys_type,
                        autonomy_level=autonomy,
                        hitl_planned=hitl,
                        hitl_description=hitl_desc if hitl_desc else None
                    ),
                    data=DataCharacteristics(
                        sources=sources_list,
                        sensitivity=sensitivity,
                        jurisdictions=jurisdictions_list
                    ),
                    impact=ImpactCharacteristics(
                        user_scope=scope,
                        business_impact_tier=impact_tier,
                        reversibility=reversibility
                    ),
                    intake_metadata=IntakeMetadata(
                        completeness_score=0.95,
                        intake_duration_minutes=10.0,
                        intake_agent_version="1.0.0",
                        prompt_manifest_sha="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
                        adversarial_flag=False
                    )
                )
                
                # Run through Orchestrator via the async pipeline so the UI
                # thread isn't blocked synchronously for the run's duration.
                # (evaluate_new_initiative() itself remains the sync path
                # that tests call directly.)
                manifest, verified = asyncio.run(orchestrator.evaluate_new_initiative_async(initiative_obj))

                # manifest is None when the pipeline halted before Control
                # Prescription ever ran (low classification confidence,
                # routed straight to human review) -- do not fabricate a
                # control-prescription report for a phase that never
                # executed.
                if manifest is None:
                    risk_profile = orchestrator.risk_classifier.classify_initiative(initiative_obj)
                    st.warning("⚠️ Routed to human review: classification confidence was below threshold. Control prescription was not run.")
                    st.markdown("<h3 class='sub-gradient-text'>Risk Classification (Pending Human Review)</h3>", unsafe_allow_html=True)
                    st.write(f"- **Overall Assigned Tier**: `{risk_profile.overall_risk_tier.value.upper()}`")
                    st.write(f"- **EU AI Act Risk Level**: `{risk_profile.classifications.eu_ai_act.tier.value.upper()}`")
                    st.write(f"- **Colorado SB 205 Applicability**: `{risk_profile.classifications.colorado_sb_205.applicable}` (Category: `{risk_profile.classifications.colorado_sb_205.high_risk_category}`)")
                    if risk_profile.human_review_reasons:
                        st.markdown(f"<span style='color:#ef4444;'>*Reasons: {', '.join(risk_profile.human_review_reasons)}*</span>", unsafe_allow_html=True)
                else:
                    st.success("✅ Multi-Agent Intake & Governance Review Executed Successfully!")

                    # Query generated structures for display
                    risk_profile = orchestrator.risk_classifier.classify_initiative(initiative_obj)
                    control_prescription = orchestrator.control_prescriber.prescribe_controls(risk_profile)

                    # Render Report
                    st.markdown("<h3 class='sub-gradient-text'>Active Governance Report</h3>", unsafe_allow_html=True)

                    r_col1, r_col2 = st.columns(2)
                    with r_col1:
                        st.markdown("##### Framework Risk Classifications")
                        st.write(f"- **Overall Assigned Tier**: `{risk_profile.overall_risk_tier.value.upper()}`")
                        st.write(f"- **EU AI Act Risk Level**: `{risk_profile.classifications.eu_ai_act.tier.value.upper()}`")
                        st.write(f"- **Colorado SB 205 Applicability**: `{risk_profile.classifications.colorado_sb_205.applicable}` (Category: `{risk_profile.classifications.colorado_sb_205.high_risk_category}`)")
                        st.write(f"- **NIST RMF Manage Focus**: `{risk_profile.classifications.nist_ai_rmf.manage_attention.value.upper()}`")
                        st.write(f"- **Human Oversight Required**: `{risk_profile.human_review_required}`")
                        if risk_profile.human_review_reasons:
                            st.markdown(f"<span style='color:#ef4444;'>*Reasons: {', '.join(risk_profile.human_review_reasons)}*</span>", unsafe_allow_html=True)
                    with r_col2:
                        st.markdown("##### Prescribed Safeguards")
                        if not control_prescription.controls.guardrails:
                            st.info("No mandatory technical controls prescribed.")
                        else:
                            for g in control_prescription.controls.guardrails:
                                st.write(f"**[{g.control_id}] {g.category.value.upper()}**")
                                st.write(f"- *Framework*: `{', '.join([f.value for f in g.source_framework])}`")
                                st.write(f"- *Instruction*: {g.description}")

                    st.markdown("---")
                    st.info(f"**Immutable Manifest Hash Seal**: `{manifest.manifest_hash}` | Compliance Ledger: **{'VERIFIED' if verified else 'CORRUPT'}**")

with tab2:
    st.markdown("<h3 class='sub-gradient-text'>Active Inventory Directory</h3>", unsafe_allow_html=True)
    p_state = orchestrator.portfolio_manager.get_portfolio_state()
    if not p_state.summaries:
        st.write("No active initiatives logged.")
    else:
        inv_data = []
        for s in p_state.summaries:
            inv_data.append({
                "Initiative ID": str(s.initiative_id)[:8],
                "Name": s.name,
                "Status": s.current_status.value,
                "Assigned Risk": s.overall_risk_tier,
                "Last Updated": s.last_updated.strftime("%Y-%m-%d %H:%M") if s.last_updated else "—"
            })
        st.dataframe(pd.DataFrame(inv_data), use_container_width=True)

with tab3:
    st.markdown("<h3 class='sub-gradient-text'>Immutable Audit Ledger</h3>", unsafe_allow_html=True)
    if not AUDIT_LOG_DB:
        st.write("Audit ledger is empty.")
    else:
        for idx, entry in enumerate(reversed(AUDIT_LOG_DB)):
            with st.expander(f"Block Index {len(AUDIT_LOG_DB) - idx}: [{entry['action_type'].value}] - Agent: {entry['agent_id'].value} (Timestamp: {entry['timestamp']})"):
                st.markdown(f"**Block ID**: `{entry['audit_log_id']}`")
                st.markdown(f"**Previous Log ID**: `{entry['previous_audit_log_id']}`")
                st.markdown(f"**Chain Hash**: `{entry['chain_hash']}`")
                st.markdown(f"**Payload Input Hash (SHA256)**: `{entry['input_hash']}`")
                st.markdown(f"**Payload Output Hash (SHA256)**: `{entry['output_hash']}`")
                st.write(f"**Public Log Context**: {entry['public_context']}")
