Governance Teardown — Delivery Methodology

Version: 1.0
Date: 2026-07-10
Owner: Renee Manzari, Firemark
Companion documents: GLASSWING_SPEC.md v1.0, GLASSWING_MONETIZATION.md v1.1, CLAUDE.md
Readers: Renee (operator), a future delivery hire (runbook user), Sonnet in Claude Code (for the OS gap register in Section 10)
SKU: AI Governance Teardown — $12,500 fixed price, fixed scope, four weeks, fully remote. Pilot price $7,500, offered once, with a named end date.

This document is the methodology of record. Every Teardown is delivered from it, every deviation is logged in the engagement record, and the version of this document used is stamped into the attestation record of every report. When the methodology changes, this file gets a new version — never an in-place edit — same rule as framework datasets.


1. Scope

What a Teardown assesses

A Teardown answers four questions about a client's AI portfolio, in this order:


What AI do you actually have? An inventory of AI initiatives — declared by the sponsor plus surfaced through structured stakeholder interviews (the shadow-AI sweep).
What risk tier is each one, under which frameworks? Deterministic classification of up to 10 initiatives against the client's applicable framework set (from the five in the OS: EU AI Act, NIST AI RMF, Colorado SB 205, ISO/IEC 42001, NYC LL144), with citations, confidence scores, and pinned framework dataset versions.
What controls does each tier require, and which are missing? Control prescription per assessed initiative, compared against the controls the client actually has, producing a findings-and-gaps analysis.
What should you do, in what order? A prioritized remediation roadmap with effort classes and owner types.


The 10-initiative cap is a scope boundary, not a soft target. Initiatives surfaced beyond the cap appear in the inventory with a triage-level tier (an indicative classification on minimal fields, confidence-capped, flagged TRIAGE — NOT ASSESSED) and are candidates for a follow-on Teardown or the retainer. The sponsor chooses which 10 get full assessment at the end of Stage 2, with Firemark's recommendation; the choice is recorded in the engagement audit trail.

What a Teardown explicitly does not assess


Technical discovery. The inventory reflects declared and interview-surfaced initiatives only. No network scanning, no code review, no log analysis, no vendor-system probing. (See the mandatory limitation sentence, Section 8.)
Model performance or accuracy. The Teardown assesses governance posture, not whether the model is good.
Security posture generally. Adjacent to, not part of, this engagement. SOC 2-style controls appear only where a framework's required controls reference them.
Legal advice. The Teardown cites regulatory requirements; it does not interpret ambiguous law for the client's specific facts. Findings of that shape are flagged COUNSEL_RECOMMENDED.
Ongoing monitoring. The Teardown identifies what must be watched (standing obligations); watching it is the retainer.
Regulator-grade export. The report is the deliverable. The full evidentiary bundle — source documents with hashes, audit chain export, standalone verifier — is the regulator packet SKU ($5,000/initiative). See the boundary rules in Section 9.


Where the Teardown ends and the next SKU begins

The Teardown deliversThe next SKU deliversInventory + assessed classifications + gaps + roadmap + standing obligations—A statement of what must be monitored, per tierRetainer: the monitoring itself, monthly briefs, deviation review, reclassification on framework version changesThe report and two-page shareable summaryPacket: per-initiative evidentiary bundle — hashed source evidence, chain export, verify_packet.py, fit for a regulator, auditor, or enterprise buyer's diligence teamAssessed classification of up to 10 initiativesSecond Teardown: full assessment of beyond-cap inventory


2. Delivery process — five stages plus pre-sale

Fixed four-week calendar from kickoff. Fully remote. Client-response SLAs are stated in the kickoff email; late client evidence extends the timeline day-for-day, never the scope. Every stage closes with a logged stage-close entry (hours, role, notes) in the engagement metrics ledger.

Each step is tagged [F] founder-only (judgment; never delegated in year one) or [R] runbook-executable (a trained delivery hire runs it from this document). The fungibility metric (Section 7) is computed from these tags.

Stage 0 — Pre-sale research (before signature; not billed engagement hours)


[R] 30–45 minutes of company research producing 2–3 specific AI-native compliance gap hypotheses, used as outreach insight. Recorded as hypotheses in the engagement record at kickoff.
Rule: hypotheses are never presented as findings. They enter the report only if Stage 2–3 evidence confirms them, through the same classification path as everything else. A pre-sale hypothesis that dies on evidence is noted in the working file and disappears from the report.


Stage 1 — Kickoff (Days 1–3)


[R] Create the engagement in the OS (glasswing engagement new), sector, jurisdictions, data directory. Genesis audit entry confirmed.
[F] Draft the governance profile (applicable frameworks, risk-appetite parameters) from the contract and Stage 0 research; confirm it with the sponsor on the kickoff call. The framework set determines everything downstream — this is a judgment call.
[R] Kickoff call (60 min): confirm sponsor, confirm the 3–5 interviewees (roles to cover: product/engineering owner of the largest AI system, whoever handles compliance or legal even part-time, one business-unit user of AI), walk the document-request list, state the two client-owned dates.
[R] Kickoff email same day, containing: the two client-owned dates (document deadline: end of Week 1; interviews complete: end of Week 2), the document-request list, the day-for-day extension rule, and the sentence "absence of documentation does not block delivery — it becomes a documented finding."


Standard document-request list: AI system descriptions or model cards (any format); vendor contracts or DPAs for third-party AI; any AI policy, acceptable-use policy, or governance charter; data inventory or privacy documentation; any prior audit, assessment, or diligence questionnaire touching AI; monitoring or logging documentation for deployed systems. All of it optional in fact, requested in full.

Stage 2 — Evidence (Weeks 1–2)


[R] Sponsor intake questionnaire session (60–90 min, screen-share, CLI questionnaire — the generalized 47-question instrument): produces the declared initiative set and the governance-context evidence.
[R] Ingest client documents; run Evidence Extraction Agent on model cards and vendor docs; work the evidence-confirmation queue for below-threshold fields (confirm with sponsor by email, batch, one pass).
[R] Stakeholder interviews, 30–45 min each, from the versioned interview guide. Every interview includes the shadow-AI sweep block: "What tools with AI features does your team use day to day, including free tiers and browser extensions? What have you built or configured yourselves, including prompts, GPTs, or automations? What does your biggest vendor do with AI on your data?" Surfaced items become inventory entries with source_type=interview.
[F] Sponsor interview conducted by founder in engagements 1–5 (relationship and calibration); [R] thereafter.
[R] Close Stage 2 with the inventory list; [F] founder and sponsor select the ≤10 for full assessment (Firemark recommends by exposure: deployed before pre-deployment, consumer-facing before internal, regulated-population-touching first). Selection and rationale logged.


Thin evidence is the norm, not a failure state. A mid-market client with no governance function will produce few documents. The methodology's response is structural, not apologetic: every unanswered field is unknown or declined in the record, confidence caps flow through classification automatically (rule engine R8), the evidence register shows exactly how thin the basis was, and "no evidence of X was provided" is a finding.

Stage 3 — Classification and prescription (Weeks 2–3)


[R] Run classification on the assessed 10 (deterministic; the operator runs a command). Run triage classification on beyond-cap inventory items.
[F] Clear every human_review_required flag personally: mandatory-control gaps, confidence-capped classifications, boundary cases. This is the assessment's judgment core and is never delegated.
[R] Run control prescription; run the gap comparison against existing_controls.
[F] Review the gap set for false positives (a control the client has under a different name) — one pass, with corrections entered as confirmed evidence, never as manual edits to engine output.


Stage 4 — Findings and report (Weeks 3–4)


[R] Draft findings in the findings format (Section 5) from engine output; run Narrative Agent for section prose; assemble the report.
[F] Prioritize the remediation roadmap (sequence, effort classes, what to do first and why — pure judgment).
[F] Founder read of the full report. In engagements 1–5 the founder edits directly; the target state is hire-drafted, founder-final-read.
[R] Run the quality gates checklist (Section 8). Every unchecked box blocks delivery.
[F] Sign the attestation (Section 6). No attestation, no delivery.


Stage 5 — Delivery (Week 4)


[F] Readout call (60–90 min): founder-led in year one. Walk the executive summary, the top findings, the roadmap — and the standing obligations section, which ends with the retainer question asked plainly: "These are the monitoring obligations your tiers carry. Who is going to run this?"
[R] Deliver the report and the two-page shareable summary; close the engagement metrics ledger; log conversion outcome (retainer yes/no/pending) at day 60.



3. Evidence map

Evidence typeSourceOS ingestion pathWhat it informsIntake questionnaireSponsor session, Stage 2Questionnaire engine → Initiative + EvidenceRecords (source_type=questionnaire)Declared inventory; all 15 intake fields; governance context; data classificationModel cards / system docsClient documentsExtraction Agent (source_type=model_card) with citations + confidenceAI system characteristics, autonomy, HITL, data sources — the classification-critical fieldsVendor contracts, DPAs, third-party assessmentsClient documentsExtraction Agent (source_type=third_party_assessment)Vendor inventory, data-flow obligations, contractual controls that count toward existing_controlsPolicies, charters, prior auditsClient documentsExtraction Agent → governance-context evidenceexisting_controls, governance-profile calibration, gap false-positive checksStakeholder interviews3–5 sessions, Stage 2Structured notes entered as source_type=interview (interviewer, interviewee role, date)Shadow-AI inventory, undocumented controls, ground truth vs. documentation, business-impact calibrationAbsence of evidenceEverywhereunknown/declined fields; empty document categoriesFindings ("no evidence of X was provided"), confidence caps, the evidence register's honesty

Rule: every finding in the report resolves to at least one evidence record ID or to a recorded absence. The report renderer enforces this mechanically (citation-resolution check, spec Week 6); a finding that cannot name its evidence does not ship.


4. The deliverable

Two artifacts. One report (docx + PDF), three internal layers, one audience each; plus a two-page shareable summary the client may forward externally.

Report structure (nine sections, all mandatory)


Executive summary — board layer, ≤3 pages. Portfolio risk picture, top 3–5 findings in plain language, the roadmap's first moves, the attestation statement. A board member reads it in ten minutes with no undefined acronyms.
Engagement scope, method, and limitations — contains, verbatim and without exception, the limitation sentence (Section 8) and the attestation scope statement.
AI initiative inventory — every initiative found, declared and interview-surfaced, with source; assessed items marked; beyond-cap items marked TRIAGE — NOT ASSESSED with indicative tier.
Classification findings — compliance/product layer. Per assessed initiative: tier per framework, citations, confidence, human-review dispositions, in the required phrasing.
Control prescriptions and gap analysis — prescribed controls per tier vs. evidenced existing controls; the findings table (format below).
Evidence register — every evidence record: type, source, date, extraction confidence, confirmation status; plus the absence findings. This is the section that makes thin evidence visible instead of hidden.
Prioritized remediation roadmap — engineering appendix. Sequenced, effort-classed (S: days / M: weeks / L: quarter+), owner-typed (engineering / compliance / legal / vendor).
Standing obligations — the monitoring, review, and retention obligations the assessed tiers carry, with cadence. The retainer bridge; auto-derived from monitoring-category prescribed controls.
Attestation record and version appendix — the signed attestation (Section 6), methodology version, framework dataset versions with verification notes, engine version, report artifact hash.


Findings format

F-## | Initiative | Finding statement (required phrasing only) | Evidence basis (record IDs or recorded absence) | Citation (framework, article/section, dataset version) | Severity | Confidence | Prescribed response | Effort class.

Severity definitions (fixed):


Critical — a deployed system missing a legally mandatory control under an applicable, enacted framework.
High — the same gap pre-deployment; or a deployed high-tier system missing prescribed (non-mandatory) controls.
Moderate — limited-tier gaps, transparency obligations unmet, documentation absences that cap classification confidence.
Low — hygiene: naming, versioning, inventory upkeep.


What the client can do with it

Hand the executive summary to the board as the AI governance briefing it has been asking for. Use the findings and roadmap as the compliance function's work plan. Forward the two-page summary to an enterprise buyer's diligence team as evidence that a credentialed third party has assessed the portfolio — and when that buyer asks for the underlying evidence, that is the packet SKU, deliverable same-week because the record already exists. What the client cannot do with it: represent any system as approved or compliant, because the report never says that (Section 8).


5. Operator-hours breakdown

Targets from the monetization plan: ≤30 hours by engagement three, ≤20 by engagement six. Engagements 1–2 will run 28–35 hours; that is expected, and the delta is the training signal.

StageSteady-state hoursTagNotes0 Pre-sale research0.75 (not in delivery count)RTracked separately as CAC time1 Kickoff2.01.5 R / 0.5 FF = governance profile confirmation2 Evidence6.55.5 R / 1.0 FF = sponsor interview (engagements 1–5), review-queue judgment calls3 Classification2.51.0 R / 1.5 FF = clearing every human-review flag; never delegated4 Findings & report6.04.0 R / 2.0 FF = roadmap prioritization + final read5 Delivery3.01.0 R / 2.0 FF = readout leadTotal20.013.0 R / 7.0 F65% runbook at steady state; 70% as interviews and readout co-lead transfer by month 9

The founder-only set, permanently: governance profile confirmation, human-review flag clearance, roadmap prioritization, attestation signature, readout lead (year one). Everything else transfers to a trained delivery hire following this document. The judgment steps never reach 100% transfer by design — they are the product.


6. The attestation

The signature is the value anchor and the liability boundary, and the boundary runs one way: the signature attests to the assessment, never to the client's AI.

What the attestation states, in the report, in exactly this form:


Firemark attests that this assessment was performed in accordance with Governance Teardown Methodology v[X.Y]; that classifications were produced by the Glasswing classification engine v[X.Y.Z] against the framework dataset versions listed in Section 9; that the assessment is based solely on the evidence received and registered in Section 6 of this report; and that the scope and limitations stated in Section 2 apply in full. Signed: Renee Manzari, AIGP — [date].



Per-initiative results are signed as assessed classifications. Nothing in the report is an approval, a certification, or a compliance determination. The OS encodes this as a distinct decision type (build gap G1, Section 10): a Teardown closes with an attestation, not an approval — ApprovalDecision(decision=approved) remains reserved for governance contexts where a client's own accountable owner approves a system to ship, which is not what a Teardown does.


7. Unit-economics instrumentation

Three numbers, tracked per engagement from the pilot, logged in the engagement metrics ledger (glasswing metrics log, gap G6) at every stage close:


Operator-hours per Teardown. Sum of stage-close hour entries, split by role (founder / hire). Stage 0 logged separately as acquisition time. Targets: ≤30 by engagement three, ≤20 by engagement six.
Gross margin. (price − hours × $250 shadow rate − API cost − direct costs) / price. API cost from the run ledger's per-engagement token records. Target ≥60% — at $12,500 that means total delivery hours × $250 + costs ≤ $5,000, i.e. roughly the 20-hour steady state. The pilot at $7,500 will miss this target; log it anyway, honestly.
Fungibility. R-tagged hours actually executed per this methodology ÷ total delivery hours. The tags in Section 5 are the denominator's structure; the measurement is real executed hours, not the plan. Target 70% by month 9. When a hire exists, fungibility is measured directly as hire-hours ÷ total; until then, it is measured as hours spent on R-tagged steps (the "could a trained non-founder have done this from the runbook" proxy, answered honestly at stage close).


One ledger line per stage close, entered the same day, no reconstruction from memory. Plus one conversion field per engagement at day 60: retainer outcome. These four fields are the YC application, the hire gate, and the Elevare pricing, so the ledger discipline is not optional.


8. Language rules and quality gates

The limitation sentence (verbatim, in every report, Section 2, no exceptions)


The AI initiative inventory in this report reflects initiatives declared by [Client] and surfaced through structured stakeholder interviews only; systematic technical discovery of AI systems was out of scope for this engagement, and initiatives unknown to interviewed personnel may exist and are not assessed here.



Forbidden phrasings

These may not appear anywhere in a Teardown report, the shareable summary, the readout deck, or delivery correspondence, in any tense or negation, applied to a client system:


"is compliant" / "complies with" / "compliant with [framework]" / "non-compliant" (as a verdict; describing a gap against a cited requirement uses the required forms below)
"is approved" / "we approve" / "approved for deployment" / "sign-off on the system"
"meets the requirements of" / "satisfies [framework]" / "passes" / "clears"
"certified" / "certification" / "validated the system" / "verified the system is"
"is safe" / "presents no risk" / "no compliance issues" / "fully covered"
"green light" / "good to go" / and any equivalent verdict idiom


The only exceptions: quoting a regulation's own text, or quoting a client's claim while attributing it ("the vendor contract states the system 'is compliant with'…").

Required phrasings


Classification: "[System] was assessed as [TIER] under [framework], dataset version [X], on the evidence provided and registered in this report."
Gap finding: "The evidence provided did not demonstrate [control], which [framework, citation] requires for the assessed tier."
Absence: "No evidence of [X] was provided" — never "[X] does not exist."
Recommendation: "The prescribed control set for this tier includes [X]" — never "you must implement [X]" (Firemark prescribes; the client's accountable owner decides).
Positive evidence: "Evidence was provided demonstrating [control] ([record IDs])" — never a compliance verdict built on top of it.


Why this survives a delivery hire: the distinction being protected is that Firemark attests to its assessment and holds no authority over, and no liability for, the client's systems. A verdict word converts an attestation into an approval and transfers liability Firemark does not hold and did not price. A hire does not need to internalize the legal theory; they need to use only the required forms. Enforcement is triple: this section (training), the pre-delivery checklist (process), and the report renderer's forbidden-phrase lint that fails the build on a match (mechanical — gap G4). New phrasing patterns require founder approval logged in DECISIONS.md.

Quality gates — the pre-delivery checklist

Mechanical (the OS enforces; the operator confirms):


 Full test suite green; engagement audit chain verifies
 Every finding's evidence IDs resolve (renderer citation check passed)
 Forbidden-phrase lint passed on report, summary, and readout deck
 Methodology, engine, framework dataset, and prompt versions stamped in Section 9; framework verification_notes present
 Report artifact hash and inputs snapshot recorded


Content (the operator judges; founder confirms in year one):


 Limitation sentence present verbatim; attestation statement present in exact form with signer and date
 All nine sections present; inventory counts consistent across Sections 1, 3, and 4
 Every human-review flag has a founder disposition recorded — none open
 Every finding uses required phrasing, has severity per the fixed definitions, and has confidence shown
 Absence findings present for every empty document-request category
 Roadmap: every item has sequence, effort class, and owner type; the first three moves are defensible out loud
 Executive summary passes the board-member test: ≤3 pages, ten-minute read, no undefined acronyms, no finding that isn't in the body
 Standing obligations present if any assessed initiative carries monitoring-category controls; the retainer question is in the readout notes
 Shareable summary contains no packet-grade content (Section 9 boundary checked)
 Client name, sector, and jurisdictions correct everywhere (the embarrassing-error sweep)
 Attestation record complete in the OS (all G1 fields) before the report leaves the building


Delivery is blocked while any box is unchecked. The checklist is the successor to the spec's week-6 "would I hand this to a client" review; the founder's final read remains, but it rides on top of the checklist rather than substituting for it.


9. Upsell boundaries — what a Teardown never gives away

A delivery hire must be able to apply these mechanically:


The report contains the evidence register (metadata, confidence, status). It never contains the underlying source documents, document hashes, the audit chain export, or verify_packet.py. That bundle is the packet SKU.
The report states standing obligations. It never contains monitoring policies configured in the OS, ingest setup, or a monitoring brief. That is the retainer.
The shareable summary contains the portfolio picture, assessed tiers with framework versions, finding counts by severity, and the attestation statement. It never contains per-finding evidence detail, the evidence register, or remediation specifics — it is designed to make the reader want the diligence conversation, in which the packet is the answer.
Triage-tier items are never upgraded to assessed language, in any artifact, under any client pressure. The upgrade path is a second Teardown.
When a client asks for packet-grade or retainer-grade content inside the Teardown, the answer is the price list, warmly, and the request is logged as a conversion signal.



10. OS capability gap register — for Sonnet

Every capability this methodology depends on that GLASSWING_SPEC.md v1.0 does not already deliver, mapped to the build week that should carry it. Renee: verify each lands in the named week's PR. Sonnet: treat each as in-scope for the named week; where a gap touches a frozen schema, it is a DECISIONS.md entry plus an Alembic migration, not an ad-hoc edit.

G1 — Attestation decision type. Week 5 (sign-off service). services/signoff.py supports two decision families: ApprovalDecision (existing: approved / requires_revision / rejected — a client-context owner approving a system) and AttestationDecision — Firemark attesting to an assessment. Required fields: engagement_id; initiative_ids (the assessed set); methodology_version; framework_versions (per framework, as served by MCP); engine_version; evidence_register_hash (stable hash over the engagement's evidence record set at signing time); scope_statement (the Section 2 limitation + scope text, stored verbatim); signer_name; signer_role; signed_at; packet_hash (hash of the exact record set attested, same mechanism as approvals). Attestation writes an audit entry; the Teardown report renderer refuses to build without a complete attestation record; tampering with any attested record after signing must be detectable by recomputation (same test pattern as the week-5 approval tamper test).

G2 — Triage classification depth. Week 1 (schema) + Week 2 (engine). initiatives.assessment_depth enum: full | triage. Triage mode: the classification engine runs on the minimal inventory fields (name, description, system type, user scope if known), all other material fields unknown; confidence hard-capped at 0.6; human_review_required always true; output tier labeled TRIAGE in risk_profiles and rendered only with the TRIAGE — NOT ASSESSED flag. A golden test asserts a triage result can never render in assessed-classification phrasing.

G3 — Interview evidence type. Week 1 (schema) + Week 3 (intake path). Add interview to evidence_records.source_type. Interview records carry: interviewer, interviewee_role (never interviewee name in fixtures), interview_date, structured notes, and the interview-guide version used. The interview guide lives at docs/interview_guide_v1.md as a versioned artifact (Renee authors content; the shadow-AI sweep block from Section 2 of this methodology is mandatory in every version). CLI entry path: glasswing evidence interview --engagement <id> ....

G4 — Forbidden-phrase lint. Week 6 (report renderer). Machine-readable copy of Section 8's forbidden list at reporting/forbidden_phrases.yaml (patterns + the two exception rules: regulation quotation, attributed client/vendor quotation). The renderer fails the report build on any match in narrative sections, same severity as an unresolvable citation. Test: a poisoned fixture narrative containing "is compliant" fails the build; the same string inside an attributed quotation passes.

G5 — Layered report templates + shareable summary. Week 6 (reporting). The spec's nine Teardown sections map to this methodology's Section 4 structure (executive summary / findings body / remediation appendix as layers of one docx). Add a second artifact type: shareable_summary (two pages, fixed template per Section 9's inclusion/exclusion list), generated in the same run, its own row in report_artifacts, its own forbidden-phrase lint pass.

G6 — Engagement metrics ledger. Week 1 (small table + CLI). Table engagement_metrics: engagement_id, stage, hours (decimal), role (founder | hire), logged_at, note; plus per-engagement fields for API cost snapshot and retainer_outcome (converted | declined | pending, set at day 60). CLI: glasswing metrics log and glasswing metrics report --engagement <id> printing the three unit-economics numbers per Section 7's formulas. No dashboard; the CLI report is enough for year one.

G7 — Standing-obligations derivation. Week 6 (reporting). Report section 8 auto-derives from prescribed controls of category monitoring (plus retention and review-cadence controls) across assessed initiatives: obligation, cadence, source citation, initiative. Renderer includes the section whenever at least one such control exists; test with the LendFast-class fixture.

Deliberately manual (no build): the document-request tracker (a checklist in the engagement data directory), interview scheduling, and the readout deck (assembled from report sections by hand in year one). Automate none of these until three engagements prove the manual cost.


11. Methodology change control

This document versions like a framework dataset: changes produce v1.1, never edits to v1.0. Every attestation names the version used, so every delivered Teardown remains auditable against the methodology that produced it. Proposed changes from a delivery hire route through the founder; changes touching Section 6 (attestation) or Section 8 (language rules) additionally get one hour of counsel review, because those two sections are the liability architecture and everything else is delivery mechanics.