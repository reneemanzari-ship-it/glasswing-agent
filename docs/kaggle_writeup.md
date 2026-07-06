# Glasswing: The AI Governance Officer Agent That Prevents the 2:47am Incident

An operating system for AI governance. Every company is deploying AI. Very few have a repeatable governance process. Five agents classify, control, and audit every initiative before it ships.

## Problem statement

At 2:47am, a fully autonomous credit underwriting model approves a consumer loan. No human reviewed it. No one flagged that this exact system profile (full autonomy, no human-in-the-loop, financial and PII data, EU and Colorado jurisdictions) is exactly what the EU AI Act calls high-risk and what Colorado SB 205 calls a consequential decision. By the time anyone in Legal or Risk sees this, the loan is already funded and the audit trail is a debug log nobody trusts.

This happens because four failures compound. Intake is noisy: initiatives get described in Slack messages and pitch decks, not structured data a compliance system can act on. There's no risk-tier enforcement: nothing stops a model from shipping regardless of what tier it falls into. There's no control prescription: even when a system gets flagged as high-risk, nobody automatically generates the specific controls it needs, like human-in-the-loop thresholds, monitoring cadence, or audit retention. And there's no audit trail: when a regulator asks how a decision was made, there's no cryptographically verifiable record, just whatever logs happened to survive.

This isn't speculative. Enterprises are creating AI Delivery Lead and Chief AI Officer roles specifically to own the gap between how fast AI ships and how slowly governance catches up. That these roles are being created is the market signal that this gap exists.

## Solution overview

Glasswing is a three-plane pipeline. Plane one handles intake: an Onboarding Intake Agent turns a freeform initiative description into a validated structured record, and is also the first checkpoint against prompt injection. Plane two handles risk and compliance: a Risk Classifier Agent queries a custom MCP server for the EU AI Act, NIST AI RMF, and Colorado SB 205, and a Control Prescription Agent turns that classification into specific, implementable controls. Plane three handles portfolio and audit: a Portfolio Manager Agent tracks every initiative's lifecycle state in a queryable database, and an Audit Trail Agent writes every action any agent takes into a hash-chained, tamper-evident log.

The MCP server is the part I'd point to first if someone asked what's actually novel here. Instead of hardcoding "if EU and financial, then high-risk" logic into the classifier, the three frameworks live as structured JSON, and the Risk Classifier queries them at runtime through four MCP tools. Adding a fourth framework means adding a JSON file and wiring it into the query logic, not rewriting the classifier.

The classification logic is also packaged as a standalone, publishable Agent Skill: the same rule engine the Risk Classifier Agent uses, importable by another agent or runnable from the command line, with its own documentation, examples, and regression tests that check it never drifts from what the full agent produces.

Three security features run end to end: schema validation that routes to human review on any structurally invalid handoff, a hash-chained audit log with replay verification, and adversarial input detection that catches prompt injection before the pipeline reaches the Risk Classifier.

## Architecture

The system is organized into three planes (see the architecture diagram in the README) because classification accuracy depends on keeping intake, compliance logic, and persistence from bleeding into each other.

Plane 1, Intake: the Onboarding Intake Agent structures a raw initiative description into a validated Initiative object and screens it for adversarial input before anything downstream sees it.

Plane 2, Risk and Compliance: the Risk Classifier Agent queries the MCP server's framework tools and produces a RiskProfile with a tier, citations, and a confidence score for each of the three frameworks. The Control Prescription Agent takes that RiskProfile and generates the controls it implies: guardrails, human-in-the-loop checkpoints, monitoring, audit retention, regulatory submissions.

Plane 3, Portfolio and Audit: the Portfolio Manager Agent commits the initiative's state to a queryable SQLite portfolio and decides what status it lands in. The Audit Trail Agent logs every action from every other agent into a SHA-256 hash chain.

Data flows one direction through the planes: Initiative to RiskProfile to ControlPrescription to GovernanceManifest, with every agent also writing to the audit trail as it goes.

The plane separation isn't organizational tidiness for its own sake. If risk classification and control prescription lived in the same agent, a bug in one would corrupt confidence scoring in the other, and there'd be no clean point to insert a schema validation gate between "what tier is this" and "what does that tier require." Keeping them as separate agents with a validated schema handoff between them means a bad classification gets caught before it produces a control prescription, instead of silently propagating into one.

## Technical implementation

Glasswing operates in two modes. With `ANTHROPIC_API_KEY` configured, agents route through Google ADK and LiteLLM to Claude Sonnet 4.5, using the prompts in `prompts/`. Without a key, agents execute a deterministic offline fallback path that produces the same classifications through Python logic. The offline path is what the test suite and the recorded demo exercise, so both are fully reproducible without external dependencies.

### Multi-agent system with ADK

Each of the five agents wraps a Google ADK Agent object, routed to Claude Sonnet 4.5 through LiteLLM. System prompts aren't hardcoded strings: each agent loads its instructions from a versioned markdown file in `prompts/` at runtime, so tuning behavior means editing a prompt file, not touching Python.

Onboarding Intake (`agents/onboarding_intake.py`), Risk Classifier (`agents/risk_classifier.py`), Control Prescription (`agents/control_prescription.py`), Portfolio Manager (`agents/portfolio_manager.py`), and Audit Trail (`agents/audit_trail.py`) are orchestrated by `GlasswingGovernanceOrchestrator` in `orchestration/flow.py`, which gates every handoff on Pydantic schema validation before the next agent runs.

### MCP server

`mcp_server/server.py` is a FastMCP server exposing four tools over three regulatory taxonomies stored as structured JSON: `get_framework`, `get_tier_criteria`, `get_function_attention_triggers`, and `search_frameworks`. The Risk Classifier queries these instead of having EU AI Act Annex III logic baked into its own code. `search_frameworks` does keyword and synonym matching across all three frameworks at once, with a blocklist for terms too generic to be a reliable signal on their own. Words like "service" or "assessment" show up in unrelated categories across all three frameworks and produced false positives before the blocklist existed. Adding a fourth framework means adding a JSON file to `mcp_server/frameworks/` and wiring its keywords into the matcher, not rewriting the classifier's control flow.

### Agent Skill

The Risk Classifier's rule engine is also packaged as a standalone Agent Skill in `skills/ai_risk_tier_classification/`, following the same packaging conventions as the rest of the course: a `SKILL.md` describing inputs, outputs, and example invocations, a CLI entry point (`python -m skills.ai_risk_tier_classification`), four worked examples covering the four risk tiers, and a regression test that asserts the skill's output is identical to what the full Risk Classifier Agent produces on the same input. That regression test matters more than it sounds. It's what would catch it if someone edited the agent's classification logic without updating the skill, or the other way around, since the skill and the agent share the same underlying function rather than two independently maintained copies of the same logic.

### Three security features

Schema validation is not a formality here. Every agent handoff is re-validated against its Pydantic schema, and if validation fails, the pipeline doesn't crash or silently continue. It logs a `HUMAN_REVIEW_REQUESTED` event to the audit trail and routes the initiative to human review. The audit log itself is hash-chained: every entry's `chain_hash` incorporates the SHA-256 hash of the previous entry, so altering any historical entry breaks verification from that point forward, and any single agent phase can be replayed against its recorded input to confirm the output hash still matches. Adversarial input detection runs before any of that. A canonical detector checks intake text for prompt injection patterns like "ignore previous instructions," and if it matches, the Onboarding Intake Agent refuses the submission outright and the orchestrator enforces the same check again, independently, if a flagged initiative ever reaches it directly. Two layers catching the same thing sounds redundant until you remember the point of defense in depth: the second layer doesn't depend on the first one working correctly.

## The 2:47am loan demo

Submit the LendFast Autonomous Underwriter initiative: fully autonomous, no human-in-the-loop planned, financial and PII data, US-CO and EU jurisdictions, deployed today. Here's what actually happens, not the abstract shape of it.

Onboarding Intake completes and logs the initiative. Risk Classifier comes back with EU AI Act tier `HIGH_RISK` citing Annex III(5)(b) (credit scoring), NIST AI RMF Manage attention `CRITICAL`, and Colorado SB 205 applicable under the `financial_lending` category. It also flags `human_review_required`, because a fully autonomous consumer credit system with no HITL plan trips that flag regardless of how confident the classification is.

Control Prescription generates two guardrails, one mandatory human-in-the-loop touchpoint triggered above $500,000, one real-time monitoring requirement, one seven-year audit retention artifact, and four regulatory submissions: EU AI Act Articles 14, 15, and 43, plus a Colorado pre-deployment impact assessment.

Portfolio Manager doesn't approve this for build. It assigns `REQUIRES_REVISION_BEFORE_APPROVAL`, with a rationale that names the specific gaps: the HITL touchpoint isn't satisfied because the initiative reports `hitl_planned=no`, the audit artifact isn't in `existing_controls`, and none of the four regulatory submissions can meet their 30-day lead time against today's deployment date.

Audit Trail verifies the chain and reports it intact. You can expand the run's audit log, pick any entry, hit replay, and confirm the recomputed output hash matches the one that was logged.

## Journey and learnings

I built the initial scaffolding and the Streamlit UI shell in Antigravity, which is good at getting a plausible-looking multi-agent skeleton and a working UI on screen fast. Then I moved into Claude Code for the actual governance logic, because that's where the work stopped being "does this run" and started being "is this classification correct, and can I prove it."

The two tools are good at different things. Antigravity got me from nothing to a five-agent pipeline that imports cleanly and a UI that renders, faster than I'd have wired that up by hand. It did not catch that my early Risk Classifier was misclassifying a plain customer-service chatbot as Minimal Risk, when it should have been Limited Risk under EU AI Act Article 50, because the chatbot interacts directly with a person and owes them a transparency disclosure even without a consequential decision behind it. That took a session of actually reading the classifier's branching logic and noticing `overall_risk_tier` was derived from NIST attention levels instead of the EU AI Act tier assignment, which is backwards.

Same story with control prescription. The first version cited Article 14 (Human Oversight) on the confidence-threshold guardrail, which doesn't fit: 14 is about human oversight, not model accuracy. Fixing that meant separating Article 14 and Article 43 (Conformity Assessment) into two distinct regulatory submissions instead of collapsing them, since they're filed for different reasons at different points in the process.

The harder part wasn't writing new features. It was going back through code that already ran without errors and asking whether it was actually right.

## Future extensions

A2A protocol integration is the most obvious next step: wrapping the Agent Skill as an A2A-compatible service with a proper Agent Card and TaskRequest/TaskResponse schema would let another organization's agents call it directly, not just import it into this codebase.

Two more frameworks are already anticipated in the schema but not implemented: NYC Local Law 144 (automated employment decision tools) and ISO 42001 (AI management systems). Adding either is the same pattern as any other framework: a JSON file in `mcp_server/frameworks/` and matching logic in the classifier.

Runtime monitoring is the gap I'd fix next for production. Glasswing governs the decision to build and deploy, but nothing watches the model afterward for drift against the risk profile it was approved under. That, plus a real GRC platform integration instead of a standalone SQLite portfolio, is what turns this from a governance gate into a governance system.
