Glasswing Governance OS: Product Specification and Build Plan
Version: 1.0
Date: 2026-07-07
Author role split: Renee Manzari (owner, reviewer, operator), Claude Opus (architect, this document), Claude Sonnet in Claude Code (builder)
Prior art: github.com/reneemanzari-ship-it/glasswing-agent (Kaggle capstone, tag as v0.1-kaggle before any work begins)

How to use this document (instructions to the builder)
If you are Sonnet reading this in a fresh Claude Code session:
This document is the source of truth for scope, architecture, and acceptance criteria. CLAUDE.md in the repo root points here.
Work in the phase and week you are told to work in. Do not build ahead. Interfaces to future phases are defined; stubs for them are allowed, implementations are not.
When this spec is ambiguous, do not ask Renee mid-task. Pick the most conservative interpretation, record it as a numbered entry in DECISIONS.md (date, question, choice, why), and continue. Renee reviews DECISIONS.md weekly.
Non-negotiable invariants, enforced by tests:
No LLM call ever occurs in a classification, prescription, monitoring-evaluation, or state-transition code path. Those are deterministic engines.
Every cross-component handoff is validated against a Pydantic v2 schema. Validation failure routes to human review, never to a crash or a silent continue.
Every state mutation writes an audit entry to the engagement's hash chain before the mutation is considered committed.
Every generated artifact records the versions that produced it (engine version, framework dataset versions, prompt version, model ID).
Definition of done for any week: the listed acceptance criteria pass via commands Renee can run herself, pytest is green, ruff check and mypy glasswing/ are clean, and the week's work is one reviewable PR with a summary that maps changes to acceptance criteria.
Tests run offline. Set GLASSWING_OFFLINE=1 in CI and use pytest-socket to block network. LLM-dependent behavior is tested against recorded fixtures in offline mode; live-mode runs are manual, operator-initiated, never CI-gated.

1. Product strategy

What this is, in one paragraph
Glasswing is a single-operator governance system that performs the mechanical majority of an AI governance officer's job: structured intake of AI initiatives from questionnaires, model cards, and registry metadata; deterministic risk classification against versioned regulatory frameworks; control prescription matched to the classified tier and the client's governance profile; post-approval monitoring of deployed systems against the risk profile they were approved under; and a tamper-evident, replayable record of all of it. It deliberately does not perform the judgment portion of the role. It does not decide whether an initiative ships, does not waive controls, does not interpret ambiguous regulation, and does not represent the company to a regulator. Those are explicit sign-off points in the data model, held open for a named accountable human. In year one that human is Renee, and the product surface a client sees is Firemark deliverables: the AI Governance Teardown report, the monthly monitoring brief, and the regulator packet. The OS is the instrument that makes those deliverables fast, consistent, and defensible.

The sharp line: replacement vs. augmentation
A full "AI Governance Employee" replacement would own four things this system intentionally does not:
Approval authority. Deciding an initiative ships. Glasswing computes everything needed to decide and blocks progress until a named human signs. The ApprovalDecision record with signer identity and a hash of the exact packet signed is a first-class object, not a checkbox.
Waivers and exceptions. Deciding a prescribed control does not apply. Glasswing records waivers with rationale and signer; it never generates them.
Regulatory interpretation. Where a framework is ambiguous (most of the interesting parts of the EU AI Act are), the engine classifies against the encoded rules and flags low-confidence or boundary cases for human review. It does not guess.
External representation. Regulator correspondence, board attestation, audit interviews. The OS produces the packet; the human presents it.
Everything else the role does — evidence gathering, inventory, classification mechanics, control mapping, monitoring, documentation, audit trail — the OS does. This line is not a limitation to apologize for. It is the reason a compliance buyer can adopt the system: a governance function whose judgment is unowned is itself an unmanaged risk, and no serious buyer or regulator accepts it. It is also the wedge against Vanta/Drata/Credo-style tooling, which sells software and leaves the judgment gap unstaffed. Firemark sells the software and the judgment together.

Three corrections to the input vision, baked into this spec
The LLM never classifies. In the v0.1 codebase the classification already had a deterministic path; this spec makes that the only path. LLMs extract (unstructured evidence to structured records), draft (report narrative, deviation summaries), and synthesize. Rules classify. Humans sign. Reproducibility of the classification is the property a client is paying for; an LLM in that path destroys it, and it also solves the API budget constraint, because the expensive calls happen once per engagement, not once per test run.
Not everything is an agent. v0.1 modeled the audit trail and portfolio manager as LLM agents. They are infrastructure: a hash-chain library and a state machine. Rebuilding them as services removes two failure surfaces, most of the token spend, and the possibility that a model hallucinates a lifecycle state.
Single-tenant is not single-client. Firemark operates one deployment but serves many clients. Engagement is the top-level entity and every record is scoped to one, with a per-engagement audit chain, so a client's regulator packet verifies standalone without exposing any other client's existence. This is also, quietly, most of the work of adding a second operator done for free — a delivery hire or a merged practice is just another operator on the same scoping model.

Year-one commercial mapping
The build and the first-ten-clients plan are the same motion:
Teardown ($10–15K, 4–6 weeks): produced end-to-end by Phase 1. Intake questionnaire + model card extraction → classification → prescription → gap analysis → signed report.
Governance-as-a-service retainer ($2–5K/month): anchored by Phase 2. Monthly monitoring brief, deviation review, portfolio state.
Regulator/enterprise-readiness packet (priced per engagement): Phase 3. The zip a client hands their auditor, bank counterparty, or regulator.
Modularity constraint honored throughout: framework datasets, the classification engine (already packaged as an Agent Skill), the controls library, and the MCP server are separable assets with their own version numbers and no dependency on Firemark-specific code. The separability serves second operators and acquirer diligence; per GLASSWING_MONETIZATION.md v1.1, the instrument itself is never licensed. Nothing else in this spec architects beyond year one.

2. Architecture

2.1 Runtime stack decisions
Concern | Decision | Why
Language / typing | Python 3.11, Pydantic v2, mypy strict on glasswing/ | Continuity with v0.1; Sonnet productivity
Agent runtime | Claude Agent SDK (Python), replacing Google ADK + LiteLLM | Anthropic-native stack, MCP as integration spine, matches the builder model and the partner ecosystem. Wrap the SDK behind glasswing/agents/base.py so agent code depends on our interface, not the SDK's; the SDK is young and its API will move.
Model | Claude Sonnet (current release) for extraction and narrative | Cost and adequacy. Model ID is config, never hardcoded.
Storage | SQLite via SQLAlchemy 2.x + Alembic migrations | Single operator, zero ops. Alembic from day one because the schema will change every phase. Postgres migration is a year-two problem the ORM keeps cheap.
MCP | One first-party MCP server (glasswing-frameworks), FastMCP, extended from v0.1 | Frameworks and controls are data behind tools. One server year one; splitting later is trivial because it is data plus tools.
Operator UI | Streamlit console (internal only) + Typer CLI (primary interface) | The CLI is what Sonnet tests against and what the acceptance criteria use. Streamlit is convenience, never load-bearing.
Client-facing surface | Generated docx/PDF reports and zip packets | Clients get deliverables, not logins (per operating model).
Reports | docx via python-docx from section templates; PDF rendered from the docx | The report is the product in year one. It gets its own module and its own tests.

2.2 Package layout
Evolve the existing repo in place (tag v0.1-kaggle first). Target layout:
glasswing/
  core/          # Pydantic domain models. No I/O, no LLM, no SQL.
  storage/       # SQLAlchemy models, Alembic migrations, repository classes.
  services/      # audit (hash chain), portfolio (state machine), signoff,
                 # validation gate, run ledger. Deterministic, no LLM.
  engines/       # classification, control prescription, monitoring evaluation,
                 # questionnaire. Deterministic, no LLM. Pure functions where possible.
  agents/        # LLM agents on Claude Agent SDK: extraction, narrative,
                 # monitoring triage. base.py wraps the SDK.
  intake/        # questionnaire runner, model card parser front-end,
                 # evidence normalization, adversarial input middleware.
  monitoring/    # ingest adapters (protocol + implementations).
  reporting/     # section templates, docx/pdf renderers, packet exporter.
  mcp/           # glasswing-frameworks server + framework/control datasets.
  cli/           # Typer app: the operator interface.
  console/       # Streamlit operator console.
collector/       # separate installable package `glasswing-collector` (Phase 2).
skills/          # ai_risk_tier_classification Agent Skill, now importing from
                 # glasswing.engines (single source of truth preserved).
prompts/         # versioned markdown prompts for the three agents.
tests/
  fixtures/      # golden initiatives, model cards, questionnaire answers,
                 # synthetic metrics, tamper tools.
CLAUDE.md
DECISIONS.md
GLASSWING_SPEC.md  (this file)

2.3 Disposition of the five v0.1 agents
v0.1 component | Disposition | Becomes
Onboarding Intake Agent (agents/onboarding_intake.py) | Replaced | Deterministic questionnaire engine (engines/questionnaire.py) + Evidence Extraction Agent (agents/extraction.py) for unstructured sources. Adversarial detection moves to intake/adversarial.py as middleware applied to every LLM-bound input, not one agent's behavior.
Risk Classifier Agent (agents/risk_classifier.py) | Refactored, core kept | Rule engine survives as engines/classification.py (canonical), still exposed via the Agent Skill. The ADK/LiteLLM wrapper and classifier prompts are retired. MCP queries remain the mechanism for framework data access.
Control Prescription Agent (agents/control_prescription.py) | Refactored | Deterministic engines/controls.py driven by a versioned controls library (YAML in glasswing/mcp/data/controls/). The prose it used to generate moves to the Narrative Agent.
Portfolio Manager Agent (agents/portfolio_manager.py) | Replaced | services/portfolio.py state machine. Status decisions become explicit rules (see 2.6); rationale text is template-generated by the engine, with the Narrative Agent optionally elaborating for reports. An LLM never assigns a lifecycle state.
Audit Trail Agent (agents/audit_trail.py) | Replaced | services/audit.py library. Hash-chain design (SHA-256, chain_hash incorporating previous entry, replay verification) survives intact; the agent wrapper does not. Chains become per-engagement with a per-engagement genesis entry.
Orchestrator (orchestration/flow.py) | Retired | Engagement pipeline in cli/ composing services and engines, with the Pydantic validation-gate pattern preserved at every handoff.

2.4 The three LLM agents (the only three)
Evidence Extraction Agent (Phase 1). Input: model cards, third-party risk assessments, vendor security docs, freeform descriptions. Output: EvidenceRecord objects with field-level source citations (character spans or section references into the source document) and per-field extraction confidence. Any field below the confidence threshold (config, default 0.7) is emitted as needs_human_confirmation and the initiative cannot reach EVIDENCE_COMPLETE until the operator confirms or corrects it in the console/CLI. Adversarial middleware screens all input before it reaches the agent, and the pipeline re-screens independently (defense in depth carried over from v0.1).
Narrative Agent (Phase 1). Input: the full computed governance record for an initiative or engagement (classification with citations, prescriptions, gaps, control status). Output: report section drafts where every factual claim carries a record ID that the renderer resolves; a claim with no resolvable ID fails the report build. This agent writes prose, never facts.
Monitoring Triage Agent (Phase 2). Input: deviations already detected by the deterministic evaluation engine. Output: plain-language deviation summaries and suggested investigation steps for the monthly brief. It never opens, closes, or escalates a deviation.
Each agent: system prompt loaded from prompts/<agent>/<version>.md at runtime (v0.1 pattern kept), offline fixture mode for tests, run recorded in the run ledger with prompt version and model ID.

2.5 Plane structure: three planes become four
v0.1's separation logic (keep intake, compliance logic, and persistence from bleeding into each other) was right and survives. The fuller scope needs a fourth plane, and "audit" moves out of plane three because the record is now a product surface of its own:
Evidence plane — intake: questionnaire, model card extraction, third-party doc extraction, registry adapters (Phase 3). Output: validated Initiative + EvidenceRecords.
Governance-logic plane — classification engine, controls engine, the GovernanceProfile (per-client applicable frameworks, jurisdictions, risk appetite parameters), and the MCP framework server it all queries.
Portfolio & runtime plane — lifecycle state machine, sign-off service, monitoring policies, ingest adapters, monitoring evaluation engine, deviations.
Record & reporting plane — audit chains, run ledger, report generation, regulator packet export.
Data flows forward through planes 1→2→3, and every plane writes to plane 4. Plane 4 depends on nothing downstream of it, which is what lets a packet verify standalone.

2.6 Data model
SQLAlchemy models in storage/models.py, mirrored by Pydantic domain models in core/. Alembic owns the schema. Key entities (fields abbreviated; Sonnet defines the rest and records choices in DECISIONS.md):
engagements — id, client_name, sector, jurisdictions[], status, data_dir, created_at. Top-level scope for everything below.
governance_profiles — engagement_id, applicable_framework_ids[] (with pinned framework versions), risk_appetite (JSON: thresholds like autonomous-decision tolerance, HITL dollar thresholds), internal_policy_refs.
initiatives — id, engagement_id, name, description, modality, autonomy_level, data_categories[], jurisdictions[], deployment_date, hitl_planned, lifecycle_state, created_at.
evidence_records — id, initiative_id, source_type ∈ {questionnaire, model_card, third_party_assessment, registry, manual}, content (JSON), source_document_hash, citations (JSON), extraction_confidence, needs_human_confirmation, confirmed_by.
risk_profiles — id, initiative_id, per_framework_results (JSON: tier, citations, confidence per framework), overall_tier, human_review_required, engine_version, framework_versions (JSON), input_evidence_hashes.
control_prescriptions — id, risk_profile_id, controls (JSON list, each with control_id from library, parameters, category ∈ {guardrail, hitl, monitoring, retention, regulatory_submission, privacy}), library_version.
control_status — id, prescription_id, control_id, status ∈ {prescribed, in_progress, implemented, waived}, evidence_ref, waiver_rationale, waiver_signer (waived requires both).
approval_decisions — id, initiative_id, decision ∈ {approved, requires_revision, rejected}, signer_name, signer_role, rationale, packet_hash (hash of the exact record set signed), decided_at. The load-bearing table.
monitoring_policies — id, initiative_id, derived_from_risk_profile_id, metrics (JSON: metric name, threshold, comparison, window, cadence), template_version. (Phase 2)
observation_records — id, initiative_id, metric, value, window_start, window_end, source_adapter, source_file_hash, ingested_at. (Phase 2)
deviations — id, initiative_id, policy_id, observation_ids[], severity ∈ {info, warning, critical}, status ∈ {open, under_review, resolved}, resolution_rationale, resolution_signer. (Phase 2)
data_assets — id, engagement_id, name, classification[] ∈ {pii, phi, financial, biometric, public, internal}, source_system, retention_policy. (Phase 3)
lineage_links — initiative_id, data_asset_id, role ∈ {training, fine_tuning, inference_input, output_storage}, declared_by. Declared lineage, not automated discovery — see Risks. (Phase 3)
audit_entries — id, engagement_id, seq, event_type, actor (service/agent/human name), payload_hash, prev_chain_hash, chain_hash, created_at. Per-engagement chain, genesis at engagement creation.
run_ledger — id, engagement_id, pipeline_step, engine_version, framework_versions, prompt_version, model_id, input_hash, output_hash, started_at, finished_at. Every output reproducible or explainable.
report_artifacts — id, engagement_id, type ∈ {teardown, monitoring_brief, regulator_packet}, path, file_hash, inputs_snapshot (JSON of record IDs and versions), generated_at.

Lifecycle states (services/portfolio.py): DRAFT → EVIDENCE_COMPLETE → CLASSIFIED → CONTROLS_PRESCRIBED → PENDING_SIGNOFF → {APPROVED | REQUIRES_REVISION | REJECTED}; APPROVED → DEPLOYED_MONITORING (Phase 2); DEPLOYED_MONITORING ↔ UNDER_REVIEW (critical deviation opens review; resolution requires sign-off); any state → RETIRED. Transitions are the only way state changes; each transition validates preconditions (e.g., PENDING_SIGNOFF → APPROVED requires an ApprovalDecision row whose packet_hash matches current records) and writes an audit entry.

2.7 MCP server
glasswing/mcp/server.py, FastMCP, evolved from v0.1:
Datasets: existing EU AI Act, NIST AI RMF, Colorado SB 205 JSON, plus ISO/IEC 42001 and NYC Local Law 144 (already anticipated in the v0.1 schema). Every framework file gains version metadata: framework_version, content_date, effective_from, effective_to, status ∈ {enacted, delayed, amended, repealed}, verification_note. Regulatory content changes are new versions, never in-place edits — a classification pinned to a framework version must replay identically forever.
Tools: the four v0.1 tools (get_framework, get_tier_criteria, get_function_attention_triggers, search_frameworks) gain an optional as_of_date/version parameter; new tools get_controls_for_tier(framework, tier, context) and get_monitoring_template(tier) serve the controls library and Phase 2 policy templates. The keyword blocklist in search_frameworks survives.
Controls library: versioned YAML under glasswing/mcp/data/controls/, mapping (framework, tier, modality, data classification) → control definitions with parameter schemas. This is a separable licensing asset; it imports nothing from Firemark-specific code.
No second MCP server in year one. Monitoring ingest is adapters, not MCP: the data flows in on operator command, not on agent tool-call.

2.8 Integration surface
Year one principle: file-based first, API second, nothing speculative. No committed design partner means every integration is built against a fixture Sonnet can run locally.
System class | Year-one implementation | Phase
Intake questionnaires | YAML-defined questionnaire (generalized from the Voyager 47-question framework), run via CLI or console, answers stored as evidence | 1
Model cards | Markdown/PDF/HTML parsing → Extraction Agent | 1
Third-party risk assessments, vendor docs | Same extraction path, source_type=third_party_assessment | 1
Monitoring platforms (Arize, Evidently, CloudWatch) | IngestAdapter protocol (monitoring/adapters/base.py); implementations: generic CSV/JSON adapter + Evidently JSON-export adapter. Others are new adapter classes when a client materializes. | 2
Clients with no monitoring | glasswing-collector: standalone package run against prediction logs (CSV/parquet), computes input-distribution drift (PSI), confidence-score statistics, latency percentiles; emits ObservationRecord JSON the OS ingests. Explicitly not an Arize competitor: three metric families, enough to satisfy the governance function. | 2
Model registries | MLflow adapter against a dockerized local MLflow fixture; pulls model version metadata, params, tags into evidence. SageMaker/Databricks adapters deferred until a client requires one. | 3
GRC platforms (ServiceNow, Archer) | Deferred entirely. Year one, Glasswing's SQLite portfolio is the GRC record and the packet export is the interchange format. Building a GRC connector without a client's instance is wasted motion. | —
Policy repositories | internal_policy_refs on the governance profile point at client documents ingested as evidence. No live connector. | 1

2.9 Security and observability at the OS layer
Data isolation: per-engagement data directories (data/engagements/<id>/) holding source documents, generated artifacts, and packet exports; DB rows engagement-scoped everywhere; per-engagement audit chains. A packet export contains exactly one engagement's material by construction.
Data at rest: operator machine uses full-disk encryption (operational requirement, documented in SECURITY.md); source documents stored with hash manifests so tampering with client evidence is detectable even outside the DB. SQLCipher deferred; revisit if a client contract demands it.
Secrets: environment variables only, .env gitignored, no key ever in code, prompts, fixtures, or DECISIONS.md.
LLM boundary controls: adversarial middleware on every LLM-bound input (pattern set carried from v0.1, extended, versioned); redaction pass strips configured PII patterns from anything logged; outbound network from the OS process limited to the Anthropic API (documented; enforced by the offline flag in tests).
Logging: structlog, JSON lines, every log line carries engagement_id and run_ledger id. Client-identifying content never in logs, only IDs.
Reproducibility (the real observability requirement here): the run ledger (2.6) plus versioned frameworks, controls, prompts, and engines means any historical output can be replayed or, if the LLM was involved, explained by its recorded inputs/outputs. Replay verification from v0.1 extends beyond audit entries to whole pipeline steps.
Backup: glasswing backup produces a dated copy of the DB plus data directories with a hash manifest; documented weekly operator routine.
Retention: engagement close-out command archives or purges per contract terms and records the action in the chain.

2.10 API budget
Fits inside $150/month with headroom. LLM spend occurs at three points only: extraction (per source document, once), narrative (per report), triage (per monthly brief). Rough Sonnet economics: a Teardown engagement with five model cards and one report ≈ 300–600K tokens total ≈ single-digit dollars. Development spend stays low because CI is offline and live runs are manual. The $300 ceiling is only relevant if you run many extraction experiments in one month; no architectural provision needed.

3. Build phases
Sixteen weeks, three phases. Every criterion is a command with a checkable outcome.

Phase 1 — Instrument the Teardown (weeks 1–6)
Goal: a full engagement runs end-to-end on the new stack: create engagement → structured intake → classification → prescription → sign-off → client-ready Teardown report. At the end of Phase 1, Renee can sell and deliver a $10–15K Teardown with this instrument.

Week 1 — Foundation.
Tag v0.1-kaggle. New package layout. SQLAlchemy models + Alembic for: engagements, governance_profiles, initiatives, evidence_records, risk_profiles, control_prescriptions, control_status, approval_decisions, audit_entries, run_ledger, report_artifacts. Port hash chain to services/audit.py with per-engagement genesis. services/portfolio.py state machine through REJECTED (Phase 2 states defined but transitions to them raise NotImplementedError). Typer CLI skeleton. CI: pytest + pytest-socket, ruff, mypy strict.
Acceptance: alembic upgrade head from empty DB and alembic downgrade base both succeed. glasswing engagement new --client "Fixture Corp" --sector fintech --jurisdictions US-CO,EU creates an engagement with a genesis audit entry; glasswing audit verify --engagement <id> exits 0; after running tests/tools/tamper.py against the DB it exits nonzero. Every state-machine transition test asserts a matching audit entry exists. CI green with network blocked.

Week 2 — Engines and frameworks.
Migrate the v0.1 rule engine into engines/classification.py as canonical; repoint skills/ai_risk_tier_classification/ to import it; keep the skill's CLI and regression test. Extend the MCP server: version metadata on all framework files, as_of_date parameter, ISO 42001 and NYC LL144 datasets authored (Renee reviews content; Sonnet builds structure from the existing three as templates). Golden fixture set: 12 initiatives spanning all four EU AI Act tiers, LL144-triggering and non-triggering hiring cases, SB 205 consequential-decision cases.
Acceptance: classification of the 12 fixtures matches golden files exactly on tier, citation set, and human_review_required per framework (tests/golden/). For the subset representable in v0.1, output is parity-equal with the v0.1 skill (regression fixtures recorded before migration). A pytest marker proves the classification test module passes with GLASSWING_OFFLINE=1 and pytest-socket active — no network, no API key. python -m skills.ai_risk_tier_classification CLI still works.

Week 3 — Questionnaire intake.
engines/questionnaire.py: questionnaires defined in YAML (question id, text, type, options, branching conditions, mapping into Initiative/EvidenceRecord fields). Author questionnaires/governance_intake_v1.yaml generalized from the Voyager 47-question framework (Renee supplies the source framework; Sonnet structures it; unresolvable mappings go to DECISIONS.md). CLI runner with resume, plus answers-file mode for testing and for pre-filled client sessions.
Acceptance: glasswing intake questionnaire --engagement <id> --answers tests/fixtures/fixturecorp_answers.yaml produces a valid Initiative + EvidenceRecords and moves state to EVIDENCE_COMPLETE; branching logic covered by tests (a fintech-lending answer path yields the lending questions, a chatbot path does not); an answers file failing schema validation routes to human review and logs HUMAN_REVIEW_REQUESTED, verified by test.

Week 4 — Extraction agent and adversarial middleware.
agents/base.py wrapping the Claude Agent SDK (consult current SDK docs at build time; isolate all SDK-specific types here). Evidence Extraction Agent per 2.4 with offline fixture mode. intake/adversarial.py middleware ported from v0.1, applied at intake and re-checked by the pipeline. Prompt files under prompts/extraction/v1.md.
Acceptance: in offline mode, extraction against tests/fixtures/model_cards/ (at least 4 cards: one clean/complete, one sparse, one with conflicting fields, one containing injection text) yields schema-valid EvidenceRecords with citations; sparse-card fields below threshold carry needs_human_confirmation=True and the initiative cannot reach EVIDENCE_COMPLETE until glasswing evidence confirm is run (tested). Injection fixtures are refused at middleware with an audit entry, and a test proves the pipeline-level re-check fires when the middleware is bypassed. One documented live-mode run recorded in docs/live_runs.md (manual, not CI).

Week 5 — Controls and sign-off.
Controls library YAML v1 covering the four tiers across the five frameworks (guardrails, HITL, monitoring requirements, retention, regulatory submissions, with parameter schemas — v0.1's LendFast outputs are the seed content). engines/controls.py consuming risk profile + governance profile (risk-appetite parameters modulate control parameters, e.g. HITL dollar threshold). services/signoff.py with packet hashing. New MCP tools live.
Acceptance: golden control-prescription tests for the 12 fixtures; the LendFast-style fixture yields the v0.1-equivalent prescription (2 guardrails, HITL threshold, monitoring, 7-year retention, 4 regulatory submissions) adjusted only where the governance profile modulates parameters, and those adjustments are asserted. glasswing signoff --initiative <id> --decision approve --signer "Renee Manzari" transitions state and stores packet_hash; a test mutates a record after sign-off and shows the stored packet_hash no longer matches recomputation (tamper evidence at the decision level). Approving without prescriptions present is impossible (precondition test).

Week 6 — Teardown report.
reporting/: section templates, docx renderer, PDF from docx. Narrative Agent with offline fixtures. Report sections (all required): executive summary; engagement scope and method; AI initiative inventory; per-initiative classification with framework citations; control prescriptions and gap analysis vs. existing controls; data and evidence register; prioritized remediation roadmap; sign-off record; appendix of framework versions and methodology.
Acceptance: glasswing report teardown --engagement <id> emits docx + PDF; a structural test opens the docx and asserts all nine sections exist and every narrative factual claim's record ID resolves (unresolvable ID fails the build — tested with a poisoned fixture); report_artifacts row records file hash and inputs snapshot; regenerating with identical inputs is flagged as a duplicate rather than silently versioned. Full end-to-end test: new engagement → answers file → classify → prescribe → signoff → report, one command chain, chain verify exits 0, and the run ledger contains every step with versions populated.

Phase 1 exit deliverable: the Fixture Corp Teardown docx, generated by one scripted run (make demo-teardown), reviewed by Renee against "would I hand this to a client." That review is the one intentionally human criterion in this plan; everything else is mechanical.

Phase 2 — Watch what you approved (weeks 7–11)
Goal: approved initiatives are monitored against the risk profile they were approved under; deviations force human review; the monthly monitoring brief (the retainer deliverable) generates from real ingested data.

Weeks 7–8 — Policy derivation and ingestion.
Monitoring policy templates per tier in the controls library (get_monitoring_template). monitoring_policies, observation_records, deviations tables. IngestAdapter protocol; generic CSV/JSON adapter; Evidently JSON-export adapter. State machine gains DEPLOYED_MONITORING.
Acceptance: approving a HIGH_RISK fixture and running glasswing monitor init --initiative <id> derives a policy matching the tier template (snapshot test); glasswing monitor ingest --adapter csv --file tests/fixtures/metrics/clean_month.csv creates ObservationRecords with source file hash; ingesting the same file twice is idempotent (test); Evidently fixture export parses to the same record shape; every ingest writes an audit entry.

Weeks 9–10 — Evaluation, deviations, collector.
engines/monitoring_eval.py: observations vs. policy thresholds → deviations with severity; critical deviation transitions DEPLOYED_MONITORING → UNDER_REVIEW; resolution requires sign-off. collector/ package: PSI input drift against a stored baseline, confidence stats, latency percentiles from prediction logs; emits ObservationRecord JSON.
Acceptance: synthetic fixture pairs (baseline + drifted parquet) with precomputed PSI: collector output matches within 1e-6; clean_month.csv produces zero deviations, drifted_month.csv produces the expected deviation set exactly (golden); the critical-deviation fixture flips state to UNDER_REVIEW and glasswing signoff on the deviation resolution flips it back, both audited; collector installs into a fresh venv with no glasswing dependency (pip install ./collector && glasswing-collector --help in a clean-env test).

Week 11 — Monitoring brief.
Monitoring Triage Agent (offline fixtures). Monthly brief report type: portfolio monitoring status, per-initiative metric summaries vs. thresholds, open and resolved deviations with narratives, attestation block.
Acceptance: glasswing report monitoring-brief --engagement <id> --period 2026-09 emits docx with all sections from fixture data; deviation narratives carry resolvable deviation IDs; a period with no data produces an explicit "no observations ingested" brief rather than an empty or fabricated one (tested). End-to-end: Phase 1 fixture engagement → approve → init monitoring → ingest drifted month → deviation → resolve → brief, single scripted run.

Phase 3 — Data governance and the regulator packet (weeks 12–16)
Goal: data classification and lineage feed control prescription; the regulator packet exports and verifies standalone; registry ingestion works against a real (local) MLflow; operator console covers the portfolio.

Weeks 12–13 — Data governance.
data_assets, lineage_links tables; questionnaire module v2 adding the data-governance section (asset inventory, classification, lineage declaration); controls engine consumes data classification (PII → privacy control set: minimization, DSR handling, retention; PHI adds its own set). Declared lineage only — the operator or client asserts it; the OS records and reasons over it.
Acceptance: golden tests where the same initiative with and without PII classification yields prescriptions differing by exactly the expected privacy controls; lineage queries via CLI (glasswing data lineage --asset <id> lists dependent initiatives); questionnaire v2 branching tested; migrations up/down clean.

Week 14 — Regulator packet.
glasswing packet export --initiative <id> → zip: manifest with hashes; evidence register with source hashes; classification with citations and framework versions; prescriptions and control status including waivers; approval decisions; monitoring history and deviations; audit chain export; verify_packet.py — stdlib-only standalone verifier checking manifest hashes and chain integrity.
Acceptance: packet verifies in a fresh container/venv with no glasswing install (python verify_packet.py exits 0); flipping any byte in any packet file makes it exit nonzero (parameterized test across file types); packet for engagement A contains no string identifiers from engagement B (isolation test with two fixture engagements).

Weeks 15–16 — Registry adapter and console.
MLflow ingest adapter against docker-compose local MLflow seeded with fixture models: model versions, params, tags → EvidenceRecords (source_type=registry). Streamlit console: engagement dashboard, portfolio table with lifecycle states, deviation queue, evidence-confirmation queue, report generation buttons. Hardening pass: error paths, empty states, SECURITY.md, operator runbook (docs/runbook.md) covering weekly backup, engagement close-out, framework update procedure.
Acceptance: make mlflow-fixture && glasswing intake registry --adapter mlflow --uri http://localhost:5000 --model fixture-credit-model produces registry EvidenceRecords (integration test, docker-marked, excluded from offline CI but in the make integration target); console pages import and render in Streamlit's AppTest harness without exceptions; runbook procedures each reference a working command; full-system scripted demo (make demo-full) runs Phases 1–3 flows on fixtures from a clean checkout.

4. Interfaces between phases
Phase 1 → Phase 2: the RiskProfile is the contract. Phase 2's policy derivation consumes overall_tier and per-framework results; Phase 1 freezes that schema (changes after week 6 require a DECISIONS.md entry and a migration). The state machine ships in week 1 with Phase 2 states declared, so Phase 2 adds transitions, not states. The audit service and run ledger are shared infrastructure from week 1; monitoring events are new event types, not new mechanisms.
Phase 1 → Phase 3: engines/controls.py is written in week 5 with an optional data_classification input defaulting to "undeclared" — Phase 3 populates it rather than modifying the engine's signature. EvidenceRecord.source_type includes registry from week 1 so the MLflow adapter adds rows, not schema. The report renderer is section-driven, so the packet and brief are new section sets on the same machinery.
Phase 2 → Phase 3: the regulator packet includes monitoring history by reading observation_records and deviations through the same repository layer the brief uses; no new query paths.
Everything → the record: every phase writes to the same per-engagement chain and run ledger established in week 1. The Phase 3 packet is a projection of records that have been accumulating since the engagement's genesis entry, which is why it needs no backfill.

5. What breaks in the existing Glasswing code
Tag v0.1-kaggle first; the Kaggle submission stays intact at that tag. Then:
agents/onboarding_intake.py — retired. Freeform-description intake survives only as a manual-evidence path; questionnaire and extraction replace it. Adversarial patterns extracted to intake/adversarial.py before deletion.
agents/risk_classifier.py — ADK wrapper and its prompt retired; rule engine extracted to engines/classification.py. The overall_risk_tier derivation bug class you already fixed (NIST attention vs. EU tier precedence) gets pinned by an explicit golden test so it can never regress silently.
agents/control_prescription.py — retired as an agent; deterministic mapping moves to engines/controls.py, prose moves to the Narrative Agent. Article 14 vs. Article 43 separation you fixed is encoded as distinct control-library entries with a test.
agents/portfolio_manager.py — retired; state decisions become state-machine preconditions (the LendFast REQUIRES_REVISION_BEFORE_APPROVAL rationale becomes three checkable preconditions: HITL satisfied, retention artifact present, submission lead times met against deployment date).
agents/audit_trail.py — retired as an agent; chain logic ported to services/audit.py. Breaking: chain format changes to per-engagement genesis, so v0.1 chains do not verify under the new code. Old data is not migrated; v0.1 records live at the tag. (Nothing in the POC DB is client data; starting fresh is correct.)
orchestration/flow.py — GlasswingGovernanceOrchestrator retired; validation-gate pattern re-implemented in the pipeline with the same route-to-human-review semantics.
Google ADK + LiteLLM — removed from dependencies entirely in week 4 when agents/base.py lands on the Claude Agent SDK.
prompts/ — classifier and portfolio prompts retired; extraction/narrative/triage prompts are new files; versioned-markdown loading pattern survives.
mcp_server/ — moves to glasswing/mcp/; server survives and extends. Framework JSON files gain version metadata (structural migration of each file); tool signatures gain optional parameters (backward compatible).
skills/ai_risk_tier_classification/ — survives; internals repoint to glasswing.engines.classification. The v0.1 regression test inverts direction: it now asserts the skill matches the engine (same single source of truth, new canonical home).
Streamlit UI — v0.1 shell retired as a client-facing surface; rebuilt in Phase 3 as the operator console. Between weeks 1 and 15 the CLI is the only supported interface.
SQLite schema — v0.1's portfolio table replaced wholesale by the Alembic-managed schema; no data migration.
Dual-mode execution — the v0.1 "offline fallback produces the same classifications" idea is promoted from fallback to architecture: engines are offline-only by definition; only the three agents have live/offline modes.

6. Risks and dependencies
Regulatory motion is the product's weather. Colorado SB 205's effective date was pushed to June 30, 2026 and faced further amendment attempts; as of this document's date it should be newly effective, but verify current status before authoring the versioned dataset. EU AI Act high-risk (Annex III) obligations phase in around August 2026, with EU-level simplification/omnibus proposals having floated delays. NYC LL144 is stable; ISO 42001 revs slowly. Mitigation is architectural, not predictive: frameworks are versioned data with effective dates and status fields, classifications pin the versions they used, and the operator runbook includes a monthly framework-review procedure (check sources, author new version file, never edit old ones). Sonnet: verify current regulatory status via web search when authoring or updating any framework dataset, and record findings in the dataset's verification_note.
Claude Agent SDK churn. Young SDK, moving API. Mitigation: pin the version, isolate every SDK type behind agents/base.py, keep offline fixture mode so a broken SDK never blocks CI, and treat SDK upgrades as their own PRs.
No design partner means fixture-shaped blind spots. Intake and monitoring built against fixtures will meet messier reality: model cards that are marketing PDFs, prediction logs with no stable schema, clients who can't name their AI systems. Mitigation: run the first paid (or discounted pilot) Teardown in weeks 7–8, while Phase 2 is underway, and feed every mismatch back as a fixture. Budget one buffer week in Phase 2 for exactly this; the phase plan above leaves week 11 light for that reason.
Solo-operator capacity. 10–15 review hours/week across 16 weeks is sufficient only because acceptance criteria are machine-checkable; the human review budget should go to the three places tests can't cover: framework dataset content (weeks 2, 12), controls library content (week 5), and report prose quality (weeks 6, 11). If a week slips, cut console polish (weeks 15–16) first, then the MLflow adapter — never the packet, the collector, or any engine.
Report quality is the commercial risk, not code quality. The Teardown docx is what a client judges. The mitigation is the citation-resolution constraint (narrative can't state anything without a record behind it) plus Renee's explicit week-6 review gate. If the report reads like a template, iterate on section templates and prompts in week 7 alongside Phase 2 — the machinery supports it without schedule damage.
Collector scope creep. The moment the collector grows a fourth metric family or a dashboard, it's competing with Arize and losing. Hard scope: PSI drift, confidence stats, latency percentiles. New client need → new ingest adapter for their tool, not new collector features. This rule goes in CLAUDE.md.
Lineage honesty. Automated lineage discovery is a multi-year data-engineering product. Declared lineage (client asserts, OS records, packet discloses the assertion basis) is defensible and honest; the packet's evidence register must state lineage is declared, not discovered. Overclaiming here is the one thing that could damage Firemark's credibility with exactly the buyers who matter.
SQLite and single-operator assumptions. Fine for year one by design. The tripwire that means it's time to revisit (Postgres, auth, roles): a second operator touching the system, whether a delivery hire or a practice combination. Likely a month-10-plus event; the ORM and engagement scoping keep the migration cost low.
Anthropic API dependency. Single-vendor by choice. The deterministic core means a total API outage degrades extraction and narrative drafting but never classification, monitoring evaluation, sign-off, or audit — the governance record keeps functioning. Document that property in SECURITY.md; it is a selling point, not just a mitigation.

Appendix A — CLAUDE.md seed content
# Glasswing Governance OS — builder instructions
Read GLASSWING_SPEC.md before any work. It defines scope, architecture,
and acceptance criteria. Current phase/week is stated in the task you were given.
Invariants (tests enforce these; do not weaken the tests):
- No LLM calls in glasswing/engines/ or glasswing/services/. Ever.
- Every handoff validates a Pydantic schema; failure routes to human review.
- Every state mutation writes an audit entry first.
- Every artifact records engine/framework/prompt/model versions.
- Collector scope is fixed: PSI drift, confidence stats, latency percentiles.
Conventions:
- Python 3.11, Pydantic v2, SQLAlchemy 2.x, Alembic, Typer, structlog.
- mypy strict on glasswing/, ruff clean, pytest offline (GLASSWING_OFFLINE=1,
  pytest-socket). Live LLM runs are manual only, logged in docs/live_runs.md.
- Ambiguity: choose conservatively, log in DECISIONS.md, continue.
- One PR per week of spec work; PR description maps changes to acceptance criteria.
- Never commit secrets, client names, or client data. Fixtures are fictional.

Appendix B — Week-one Monday handoff
The literal first instruction to Sonnet:
Read GLASSWING_SPEC.md. Execute Phase 1, Week 1. Start by tagging the current main as v0.1-kaggle, then restructure the package per section 2.2 and implement the week-1 scope per section 3. Do not build anything from later weeks except type stubs explicitly required by week-1 code. Finish with the week-1 acceptance commands demonstrated in the PR description.
