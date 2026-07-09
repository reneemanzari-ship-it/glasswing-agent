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
