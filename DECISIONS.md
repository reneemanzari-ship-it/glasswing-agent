# Decisions Log

Ambiguity-resolution entries per CLAUDE.md's working process. Renee reviews
entries marked OPEN weekly; entries with no status line are resolved by the
choice recorded and don't require review unless something changes.

## D-001 — 2026-07-08 — Does "restructure the package per section 2.2" mean moving all existing top-level code now, or building the new skeleton alongside it?

Question: GLASSWING_SPEC.md Appendix B says to restructure per section 2.2
as the first Week 1 action. Section 2.2's target layout is the full,
end-state layout across all three phases. Section 3's disposition table
(and section 5) assign specific migrations — repointing skills/, retiring
agents/, moving mcp_server/ — to specific later weeks (2, 4, etc.), some
of which depend on code that doesn't exist yet in Week 1 (e.g. Week 2's
"repoint skills/ to import glasswing.engines.classification" requires
glasswing/engines/classification.py, which is Week 2 scope).

Choice: Create the full glasswing/ package skeleton (core, storage,
services, engines, agents, intake, monitoring, reporting, mcp, cli,
console — all with __init__.py) now, but only populate core, storage,
services, and cli with real Week 1 content. The v0.1 top-level packages
(agents/, schemas/, orchestration/, mcp_server/, security/, skills/, ui/)
stay in place, untouched, until their disposition-table-assigned week.

Why: Building ahead of scope (moving code before its dependencies exist,
or before the week that's supposed to do the migration) would violate
"Do not build ahead" and risks breaking still-in-use v0.1 code before its
replacement is ready. This keeps both the new and old systems independently
working during the transition.

## D-002 — 2026-07-08 — How much of v0.1's Initiative schema belongs in Week 1's core.Initiative model?

Question: GLASSWING_SPEC.md section 2.6 gives an abbreviated field list for
the `initiatives` table (id, engagement_id, name, description, modality,
autonomy_level, data_categories[], jurisdictions[], deployment_date,
hitl_planned, lifecycle_state, created_at). v0.1's schemas/initiative.py has
a much richer model (ai_system/data/impact characteristics, sponsor, etc.).

Choice: glasswing/core/initiative.py carries only the abbreviated Week 1
field set. The richer intake fields arrive as additions when the
questionnaire engine (Week 3) needs somewhere to write them, not as a
Week 1 rewrite of the richer v0.1 shape.

Why: Section 2.6's field list is explicit and Week 1 scoped; inventing the
richer shape now would be building ahead of Week 3, which is what actually
defines how those fields get populated.

## D-003 — 2026-07-08 — What happens after REQUIRES_REVISION or REJECTED?

Question: GLASSWING_SPEC.md section 2.6 defines PENDING_SIGNOFF -> {APPROVED
| REQUIRES_REVISION | REJECTED} but never states what edges leave
REQUIRES_REVISION or REJECTED.

Choice: No outgoing edges are implemented for REQUIRES_REVISION or REJECTED
this week. Attempting to transition out of either raises
InvalidTransitionError (not NotImplementedError — they aren't Phase 2+
states, they're just states with no legal exits defined yet).

Why: Inventing a return-to-pipeline edge (e.g. REQUIRES_REVISION ->
EVIDENCE_COMPLETE) isn't in the spec and would be a scope guess with real
product consequences (what re-enters, what re-runs). Safer to leave it
unimplemented and revisit when a week's scope actually specifies it.

## D-004 — 2026-07-08 — How deep should the APPROVED-transition precondition check go in Week 1?

Question: Section 2.6 says "PENDING_SIGNOFF -> APPROVED requires an
ApprovalDecision row whose packet_hash matches current records." The
packet-hash computation is services/signoff.py, which is Week 5 scope.

Choice: Week 1's precondition checks only for the *existence* of an
ApprovalDecision row with a matching `decision` value for the initiative.
packet_hash cross-validation against current records is deferred to
services/signoff.py in Week 5.

Why: Building packet-hash validation now would mean inventing
services/signoff.py's hashing scheme ahead of its scheduled week. The
existence check is still a real, enforced precondition — it just isn't the
full one yet.

## D-005 — 2026-07-08 — Python version mismatch

Question: GLASSWING_SPEC.md pins Python 3.11. The available sandboxed dev
environment's virtualenv provides Python 3.14.

Choice: Wrote all Week 1 code to be 3.11-compatible (no 3.12+-only syntax),
kept `requires-python = ">=3.11"` in pyproject.toml, and ran the full
verification suite (pytest, ruff, mypy --strict) against the available
3.14 interpreter since a 3.11 interpreter isn't available in this
environment.

Why: Blocking Week 1 delivery on interpreter provisioning isn't the
conservative choice when the code itself doesn't depend on anything
3.11-specific. Flagging so a 3.11 run happens before this is trusted as
CI's actual runtime.

Update — 2026-07-09: Ratified by Renee. Python 3.14 is now the project's
target version, not a logged deviation. GLASSWING_SPEC.md section 2.1's
runtime stack table and Appendix A's CLAUDE.md seed block, the live
CLAUDE.md, pyproject.toml (`requires-python`, `[tool.ruff] target-version`,
`[tool.mypy] python_version`), and .github/workflows/ci.yml's
`setup-python` step all now say 3.14 explicitly. Re-ran the full offline
suite (`GLASSWING_OFFLINE=1 pytest tests/glasswing`), `ruff check`, and
`mypy --strict glasswing/` against 3.14 after the edits — all still pass
(see PR follow-up report). No 3.11 interpreter run is needed going
forward, since 3.11 is no longer the target.
Status: RESOLVED — no longer open.

## D-006 — 2026-07-08 — What does the ported stable-hash rule apply to, given there's no GovernanceManifest table in the new schema?

Question: CLAUDE.md's hash stability rule says "When you port hashing into
services/audit.py, port this rule with it" — referring to v0.1's
_stable_hash() volatile-field exclusion for RiskProfile, ControlPrescription,
and GovernanceManifest. GLASSWING_SPEC.md section 2.6 has no
GovernanceManifest-equivalent table.

Choice: Ported `stable_hash()` into glasswing/services/audit.py with a
volatile-field registry keyed to the new core.risk.RiskProfile (excludes
`id`, `created_at`) and core.controls.ControlPrescription (excludes `id`,
`created_at`, `risk_profile_id`) models. No entry for a manifest-equivalent
model since none exists yet in this schema. Added a test
(test_stable_hash_ignores_id_and_created_at) proving a re-serialized
RiskProfile with a fresh id/timestamp hashes identically, per CLAUDE.md's
explicit instruction.

Why: The rule's purpose (replay-comparable content hashes) transfers
directly to the models that inherit the same volatility pattern; inventing
a manifest model to satisfy the letter of "port to these three types" would
be building ahead of whatever Phase 1 later decides that artifact looks
like (if anything — approval_decisions + report_artifacts may cover the
same ground).

## D-007 — 2026-07-08 — Scope of "ruff check clean" and "CI green"

Question: CLAUDE.md says "mypy --strict clean on glasswing/. ruff check
clean." — mypy's scope is explicit, ruff's is not. Running `ruff check .`
across the whole repository surfaces ~5,100 pre-existing lint errors in
v0.1 code (agents/, orchestration/, mcp_server/, ui/, verify_schemas.py)
that predate this week and aren't part of Week 1's build.

Choice: "ruff check clean" and the Week 1 CI gate are scoped to the Week 1
deliverable: `glasswing/` and its tests (`tests/glasswing/`, `tests/tools/`,
`tests/conftest.py`). CI (.github/workflows/ci.yml) runs `ruff check
glasswing/ tests/glasswing tests/tools tests/conftest.py` and `mypy
glasswing/` as gating steps, and separately runs the full legacy `pytest`
suite as a non-blocking, visibility-only step.

Why: "Do not rebuild components that exist unless the spec's disposition
table says they change" and "do not add features beyond scoped work" both
argue against retroactively fixing ~5,100 lint findings in code this week
never touches. Keeping the full suite running (non-blocking) preserves
visibility into legacy state without making Week 1 hostage to it.

Update — 2026-07-09 (Week 2): scope extended to include the new
tests/golden/ suite (golden fixtures, v0.1 parity check, R5 regression
pin), same reasoning -- new glasswing-owned test code is gated, v0.1 code
stays visibility-only.

## D-008 — 2026-07-08 — Pre-existing test failures found, not fixed

Found during Week 1 baseline verification (confirmed present before any
Week 1 change, by re-running against a stashed pyproject.toml):

- `tests/test_flow.py::test_governance_pipeline_flow` and
  `::test_247am_loan_scenario_flow` — `PermissionError: [WinError 32]` when
  the test tries to unlink its temp SQLite file on Windows; a v0.1
  test-cleanup bug, platform-specific (Windows file-locking), unrelated to
  Week 1.
- `tests/test_schemas.py::test_risk_profile_schema_validation` — the test's
  own invalid-data fixture has a `rationale` string shorter than the
  schema's 20-character minimum, so pydantic raises on that field before
  ever reaching the `high_risk_category` validator the test is trying to
  exercise. Pre-existing test-data bug, unrelated to Week 1.

Not fixed per CLAUDE.md ("Out-of-scope bugs... Flag them... Do not fix
without approval"). Recorded in the Week 1 PR description's "Found, not
fixed" section.

## D-009 — 2026-07-09 — Does engines/classification.py consume the Week 1 abbreviated glasswing.core models, or the existing v0.1 schemas/ models?

Question: GLASSWING_SPEC.md section 3 Week 2 says "Move the v0.1 rule
engine into engines/classification.py." glasswing/core/risk.py's Week 1
docstring says the engine "lands Week 2," which could be read as implying
it should populate that abbreviated (per_framework_results dict,
overall_tier str) model instead of the rich schemas.risk_profile.RiskProfile
v0.1 uses.

Choice: engines/classification.py's classify_initiative() still takes
schemas.initiative.Initiative and returns schemas.risk_profile.RiskProfile
-- the same models v0.1's orchestration pipeline, agents, and tests
already depend on. glasswing.core.risk.RiskProfile (the Week 1 storage
placeholder) stays unpopulated; nothing writes rows into risk_profiles
this week.

Why: "migrate the engine" acceptance criteria are phrased in terms of the
rich schema's shape (Classifications.eu_ai_act/nist_ai_rmf/colorado_sb_205,
each with .tier/.citations/.confidence) -- see the 12-fixture acceptance
text itself. Threading the engine's real output into the Week 1 storage
schema is wiring/persistence work no Week 2 acceptance criterion asks
for; reconciling the two schemas is deferred to whichever week actually
connects the engine to the SQLAlchemy storage layer and CLI.

## D-010 — 2026-07-09 — Where does NYC LL144's classification result live?

Question: schemas.risk_profile.RiskProfile.Classifications is a required
triple (eu_ai_act, nist_ai_rmf, colorado_sb_205) constructed throughout
the still-live v0.1 pipeline. LL144 is a new, fourth framework the golden
fixture set needs classified.

Choice: LL144 gets its own model (glasswing/core/ll144.py::
NYCLL144Classification) and its own function
(engines/classification.py::classify_nyc_ll144()), called alongside
classify_initiative() rather than folded into RiskProfile.

Why: adding a required fourth field to Classifications breaks every
existing construction site across schemas/, agents/, orchestration/, and
tests/ that isn't scheduled to change until later (or ever, per the
disposition table). Making it optional still touches a shared schema
outside this week's scope for no real benefit -- a separate model has
zero blast radius on v0.1 and is just as testable.

Update — 2026-07-10 (Week 3 pre-work B): the stated rationale above didn't
survive scrutiny. `schemas.risk_profile.RiskProfile.Classifications` was
never the target that mattered -- `glasswing.core.risk.RiskProfile.
per_framework_results` is (a plain `dict[str, Any]`, per glasswing/core/
risk.py), and it was always able to hold a fourth `nyc_ll144` entry
without touching any schema at all. Keeping LL144 behind a separately-
discovered function meant the Phase 1 -> Phase 2 contract (GLASSWING_SPEC.md
section 4, which consumes `overall_tier` and per-framework results) and
the Week 6 report (which is supposed to carry every framework's
classification uniformly) would have had to special-case a fourth
framework rather than iterating uniformly.

Resolved: LL144 now folds into the uniform payload.
`engines/classification.py::build_per_framework_results(initiative)`
returns `{"eu_ai_act": {...}, "nist_ai_rmf": {...}, "colorado_sb_205":
{...}, "nyc_ll144": {...}}` -- every entry a same-shaped dict keyed by
framework_id, which is exactly the `per_framework_results` shape. This is
now the function the Phase 1 -> Phase 2 contract and the Week 6 report
should call. `classify_nyc_ll144()` and `NYCLL144Classification` remain
(a low-level building block `build_per_framework_results()` composes,
still independently testable), but they are no longer the primary
interface -- the original "separate model, separate function" design
for LL144 itself is superseded by this update; only the low-level
classifier function/model survive, now as an implementation detail.

`overall_risk_tier`/`human_review_required` are deliberately NOT in
`per_framework_results` -- they still come from `classify_initiative()`'s
`RiskProfile` directly, driven solely by the EU AI Act tier per R5. LL144
applicability never raises or substitutes for the overall tier, exactly
the guarantee R5 already gives NIST attention; folding LL144 in per se
doesn't change that invariant.
Status: RESOLVED — no longer open. See
tests/golden/test_per_framework_results.py.

## D-011 — 2026-07-09 — Adding EU AI Act Article 5 (Prohibited) capability: new engine branch and a schema gap it exposed

Question: the 12-fixture golden set must span all four EU AI Act tiers,
but v0.1's local_classify() had no branch that ever assigned
EUAIActTier.PROHIBITED -- and separately, schemas.risk_profile.OverallRiskTier
had no value to represent R5's "UNACCEPTABLE -> prohibited" mapping at all
(only low/moderate/high/critical existed).

Choice: added a new is_prohibited_scenario branch to
engines/classification.py (checked first, per R2's evaluation order), and
added OverallRiskTier.PROHIBITED = "prohibited" as an additive enum value
in schemas/risk_profile.py. This fixture (05_prohibited_social_scoring) is
excluded from the v0.1 parity check -- there is no v0.1 baseline to match,
since v0.1's engine cannot represent this tier in the first place; running
it through v0.1 would only freeze an incorrect MINIMAL_RISK baseline.

Why: without the tier, "preserve R1-R9" (specifically R2's Article 5 halt
condition and R5's tier mapping) is impossible to satisfy for prohibited-
practice systems -- this is the minimal change required by the very rules
this week's migration is instructed to preserve, not a broader schema
rebuild. No existing enum value changed or removed.

## D-012 — 2026-07-09 — What does "parity-equal" mean for engine/model bookkeeping fields?

Question: v0.1's frozen output stamps `classifier_agent_version: "1.0.0"`
and `model_id: "claude-sonnet-4-5-20250115"` on every RiskProfile, even
though no LLM call ever happens in the offline path that produced it. A
literal full-object equality check against the frozen snapshot would fail
on these fields once the new engine correctly stops claiming an LLM
model_id it doesn't use.

Choice: the v0.1 parity test (tests/golden/test_v0_1_parity.py) compares
only classification-content fields (tier, citations, confidence, NIST
attentions, SB 205 applicability/category, overall_risk_tier,
human_review_required/reasons) -- not risk_profile_id, initiative_id,
created_at, classifier_agent_version, model_id, prompt_manifest_sha, or
mcp_server_version.

Why: CLAUDE.md invariant #1 requires honesty about what actually ran; the
new engine's `model_id: "deterministic-engine"` and
`classifier_agent_version: "2.0.0"` are more correct than what they
replace, not a regression. "Parity" means the classification logic wasn't
changed, not that engine identity metadata is frozen forever.

## D-013 — 2026-07-09 — SB 205 golden-set coverage limited to the two categories v0.1 already implements

Question: mcp_server/frameworks/colorado_sb_205.json lists 8 consequential-
decision categories, but v0.1's local_classify() only ever detects two
(financial_lending via the credit branch, employment via the recruitment
branch) -- there's no keyword logic for healthcare, housing, insurance,
education, etc.

Choice: the 12-fixture golden set's SB 205 coverage stays limited to
financial_lending and employment.

Why: adding keyword detection for the other six categories is new engine
capability, not part of "move the v0.1 rule engine" -- and per
GLASSWING_SPEC.md section 6, SB 24-205 is now a repealed statute (D-015)
anyway, making new category-detection investment against it low-value
this week specifically.

## D-014 — 2026-07-09 — LL144 applicability rule design

Choice: classify_nyc_ll144() gates on the same recruitment-scenario
keyword match classify_initiative() already uses, AND "US-NY" present in
initiative.data.jurisdictions. No live MCP tool query yet -- that's Week
5+ scope per the engine module's R1 docstring note.

Why: this is the narrowest rule that correctly distinguishes fixtures 06
and 07 (identical recruitment logic, only the jurisdiction differs) and
matches LL144's actual statutory trigger (a NYC nexus). Building full MCP-
query-driven classification now would be a bigger rearchitecture than
"migrate the engine" calls for.

## D-015 — 2026-07-09 — Colorado SB 205 dataset: repealed law, not rewritten to match its successor

Finding (verified via web search 2026-07-09, sources in
mcp_server/frameworks/colorado_sb_205.json's verification_note): SB 24-205
never took effect. It was delayed twice, then repealed outright by SB
26-189 (signed 2026-05-14), which replaces it with a narrower disclosure-
and-rights framework effective 2027-01-01.

Choice: colorado_sb_205.json's status is now "repealed" and its
verification_note states this plainly, flagged NEEDS_OWNER_REVIEW. The
file's tiers/categories/required_controls content is left describing the
(repealed) SB 24-205 framework -- it is NOT rewritten to model SB 26-189.
The golden fixture set and classification engine still classify against
this framework version as-is (DECISIONS.md D-013 covers scope there).

Why: authoring SB 26-189's actual framework requires the enacted bill
text, not secondary summaries -- inventing that structure from commentary
would risk asserting unverified regulatory content (CLAUDE.md: "Do not
paraphrase regulatory text... quote or cite"). The engine's classification
mechanics (does this initiative make a consequential decision in a listed
category) are orthogonal to whether that category list is currently good
law; both are now honestly labeled rather than silently conflated.
Status: OPEN for Renee review -- a new colorado_sb_205 dataset version
modeling SB 26-189 is needed before this framework backs a live
engagement, and must be authored from the primary bill text.

## D-016 — 2026-07-09 — ISO 42001 dataset shape

Choice: iso_42001.json uses new top-level keys ("clauses",
"annex_a_controls") rather than the "tiers" or "functions" shapes the
other four frameworks use, and is not wired into
engines/classification.py or the golden fixture set this week.

Why: ISO 42001 is a certifiable management-system standard, not a per-
initiative risk-tier or function-attention framework -- forcing it into
"tiers" or "functions" would misrepresent what it actually is. No Week 2
acceptance criterion requires an ISO 42001 classification case, and it's
explicitly named as a future controls-engine input (GLASSWING_SPEC.md
Week 5), not a Week 2 one.
Status: OPEN for Renee review -- entire file is NEEDS_OWNER_REVIEW; see
its verification_note (copyrighted primary text was not available to
verify exact clause/control wording against).

## D-017 — 2026-07-09 — get_required_controls did not receive the version/as_of_date parameter

Question: mcp_server/server.py has five @mcp.tool() functions, but
GLASSWING_SPEC.md section 3 Week 2 names only four ("get_framework,
get_tier_criteria, get_function_attention_triggers, search_frameworks")
as gaining the new optional parameter. get_required_controls exists in
the v0.1 server (predates this spec) but isn't in that named list.

Choice: left get_required_controls unchanged this week.

Why: matches the literal scope of "the four existing MCP tools." It also
isn't used by anything R1-R9 or the golden fixture set exercises this
week; new MCP tools (get_controls_for_tier, get_monitoring_template) are
explicitly Week 5 scope, and expanding get_required_controls now would be
scope volunteered rather than requested.

## D-018 — 2026-07-10 — GDPR is Phase 3 scope, not a Week 2 gap

Note (Week 3 pre-work D): GDPR does not appear among Glasswing's
frameworks and this is deliberate, not an oversight. GLASSWING_SPEC.md
section 2.7 names the framework set explicitly (EU AI Act, NIST AI RMF,
Colorado SB 205, plus ISO/IEC 42001 and NYC LL144 added Week 2) --
GDPR was never in that set. docs/framework_authoring_guide.md section 8
uses GDPR as a worked example for *how* to add a new framework when the
time comes; it is a methodology illustration, not a scheduling
commitment.

Choice: GDPR is tracked as intended Phase 3 scope, alongside data
governance (GLASSWING_SPEC.md section 3, weeks 12-13), where
data_classification (PII) already drives control prescription per the
Phase 1 -> Phase 3 interface (section 4). Adding GDPR now, ahead of that
week, would be building ahead of scope for a framework with no golden
fixture requirement and no consuming engine logic yet.

Why: recording this explicitly closes the question the same way D-013
closes SB 205's category-coverage question -- so a future session (or
Renee, reviewing scope) doesn't mistake an intentional sequencing
decision for a dropped requirement.
Status: RESOLVED -- tracked for Phase 3, weeks 12-13.

## D-019 — 2026-07-10 — governance_intake_v1.yaml content is out of scope for Sonnet

Question: GLASSWING_SPEC.md section 3 Week 3 item 2 says to author
questionnaires/governance_intake_v1.yaml as a structural generalization of
Renee's Voyager 47-question framework. That framework's actual questions
were never supplied in this session or found anywhere in the repo
(checked Fable/GLASSWING_HANDOFF.md, which references it but contains no
question content).

Choice (per Renee's explicit direction this session): the structural
generalization of the real intake content is authored separately by
Renee and Opus, and is out of glasswing/engines/questionnaire.py's scope
entirely -- an IP-sensitive transformation, not an engineering task. This
week's deliverable is the engine and the YAML schema it consumes
(question id, text, type, options, branch, maps_to), proven against
tests/fixtures/questionnaires/sample_intake_v0.yaml -- a small, fictional,
clearly-labeled scaffold that exercises every engine capability (multiple
question types, a genuinely divergent branch, Initiative and
EvidenceRecord field mappings) without containing or approximating any
real client or methodology content.

Why: raw questionnaire content is never to be ingested or generated by
Sonnet this week; the real governance_intake_v1.yaml must drop into
engines/questionnaire.py as pure data, validating against the schema
above with zero engine changes -- this is what "engine consumes data, no
question content hardcoded" (the module's own docstring) actually buys.
Status: RESOLVED -- engine ships this week; real questionnaire content
follows in a separate delivery.

## D-020 — 2026-07-10 — Colorado SB 26-189: successor dataset authored as a new framework_id

Question: Week 2 (D-015) found SB 24-205 repealed and replaced by SB
26-189 but didn't author the successor, since the bill's actual content
wasn't verified. This week's parallel cleanup re-opened that with web
search (Colorado General Assembly's own SB26-189 bill page plus a law
firm client alert), confirming: signed 2026-05-14; "automated
decision-making technology" (ADMT) and "consequential decision" replace
"high-risk AI system"; deployer notice/disclosure/human-review-request
obligations and developer documentation obligations replace the prior
duty of care against algorithmic discrimination, risk-management
program, and annual impact assessment (none of which survive in any
form).

Choice: authored mcp_server/frameworks/colorado_admt.json as a new
framework_id (not a version bump of colorado_sb_205), with
supersedes: colorado_sb_205 and a matching superseded_by: colorado_admt
pointer added to colorado_sb_205.json's now-repealed record, per
docs/framework_authoring_guide.md section 7's repeal-and-replace test:
the statutory identity, defined terms, and substantive obligations all
changed, so this is two framework_ids, not one framework_id with two
versions.

Why: folding this into colorado_sb_205's existing tiers would silently
misrepresent obligations that no longer exist (risk-management program,
impact assessment) as still live, and would lose the "never edit a
published version in place" guarantee for any classification already
pinned to colorado_sb_205's content.

Not fully closed: the enrolled bill's full PDF text exceeded this
session's fetch size limit, so exact C.R.S. section citations are not
confirmed, and two sources disagree on the effective date (Colorado
General Assembly's own page suggests 2026-08-12 for the act generally
and 2027-01-01 specifically for developer documentation; a law firm
summary states a single 2027-01-01 date with no split) --
colorado_admt.json conservatively records 2027-01-01 and flags the
discrepancy in its verification_note. Either way, Colorado currently has
no AI/ADMT statute in force as of today (2026-07-10): SB 24-205 repealed
before ever taking effect, SB 26-189 not yet effective under either
candidate date. Neither colorado_sb_205 nor colorado_admt is wired into
glasswing/engines/classification.py this week (D-013's SB 205 scope
limit still applies); the golden suite was re-run after both file
changes and remains green.
Status: OPEN for Renee review -- confirm the effective-date discrepancy
and the exact statutory citations against the enrolled bill text before
Week 6, per the user's "must clear before Week 6" priority.

## D-021 — 2026-07-10 — NYC LL144 citation correction

Finding: Week 2's nyc_ll144.json had section 20-870 and 20-871 reversed.
Week 3 verification against the official NYC Administrative Code library
(codelibrary.amlegal.com, via a search-indexed snippet of that page's own
title and content -- direct fetch returned HTTP 403) confirms § 20-870 is
Definitions (including "bias audit" and "employment decision") and §
20-871 is the operative prohibition on using an AEDT without a bias
audit, public summary, and notice.

Choice: swapped the citations -- the "applicable_aedt" tier now cites §
20-871 (the actual prohibition/requirement), and "not_applicable" cites §
20-870 (definitions). needs_owner_review stays true: the precise
statutory definition of "substantially assist or replace discretionary
decision-making" and the exact carve-outs are still from secondary
sources, since the full primary text and the DCWP final rule weren't
fully readable this session (blocked or too large to fetch directly).
Status: RESOLVED (citation mapping) / OPEN (full-text carve-out
verification) -- see mcp_server/frameworks/nyc_ll144.json's
verification_note.

## D-022 — 2026-07-10 — EU AI Act Digital Omnibus: provisional flag resolved

Finding: Week 2 flagged the Annex III deadline deferral (to 2027-12-02)
as provisional, pending formal co-legislator adoption. Week 3 web search
confirms formal adoption completed: European Parliament endorsed the text
2026-06-16, Council of the EU gave final green light 2026-06-29, entering
into force three days after Official Journal publication. Confirmed dates
unchanged from Week 2's finding: 2027-12-02 for stand-alone Annex III
high-risk systems, 2028-08-02 for Annex I embedded high-risk AI. The
package also adds a new Article 5 prohibition (non-consensual intimate
imagery / CSAM generation), compliance required 2026-12-02.

Choice: updated eu_ai_act.json's effective_from to 2027-12-02 (previously
2026-08-02, the pre-deferral date) and rewrote verification_note to
record formal adoption, removing the "provisional" caveat. Did NOT add
the new CSAM/intimate-imagery prohibition ground to the "prohibited"
tier's criteria/examples this pass -- flagged needs_owner_review instead,
since adding it properly is a content change requiring the same care as
any other substantive dataset edit, not a side effect of a status-field
verification pass.
Status: RESOLVED (deferral adoption status) / OPEN (new CSAM prohibition
ground not yet added to tier content) -- golden suite re-run and green
after this change.
