# CLAUDE.md — Glasswing Governance OS builder instructions

**This file is canonical.** If any other instruction file in this repo (AGENTS.md, README.md, older prompts) conflicts with this file or with GLASSWING_SPEC.md, the precedence order is:

1. GLASSWING_SPEC.md (scope, architecture, acceptance criteria)
2. CLAUDE.md (this file — working rules)
3. AGENTS.md (v0.1 legacy runtime rules, valid only for code not yet migrated)

Read GLASSWING_SPEC.md before any work. The current phase and week are stated in the task you were given. If no phase/week is stated, stop and ask — do not infer one.

## Invariants

Tests enforce these. Do not weaken the tests. If a task appears to require violating one, it doesn't — log the conflict in DECISIONS.md and implement the compliant interpretation.

1. **No LLM calls in `glasswing/engines/` or `glasswing/services/`. Ever.** Classification, control prescription, monitoring evaluation, state transitions, and audit logging are deterministic. If you need language work (extraction, narrative, summarization), it belongs in `glasswing/agents/` behind `agents/base.py`.
2. **Every cross-component handoff validates a Pydantic v2 schema.** Validation failure routes the initiative to human review with a `HUMAN_REVIEW_REQUESTED` audit event. It never crashes the pipeline and never silently continues.
3. **Every state mutation writes an audit entry to the engagement's hash chain before the mutation is considered committed.** No entry, no mutation.
4. **Every generated artifact records the versions that produced it:** engine version, framework dataset versions, prompt version, model ID — in the run ledger and in the artifact's inputs snapshot.
5. **Collector scope is fixed:** PSI input drift, confidence statistics, latency percentiles. A fourth metric family is a rejected feature, not a nice-to-have. New client monitoring needs are met with a new ingest adapter for *their* tool.
6. **Hash stability rule** (carried from v0.1 and it still applies): models carrying auto-generated IDs or timestamps must be hashed through a stable-hash function that excludes volatile fields, never through raw `model_dump_json()`. In v0.1 this is `_stable_hash()` in `orchestration/flow.py` for `RiskProfile`, `ControlPrescription`, and `GovernanceManifest`. When you port hashing into `services/audit.py`, port this rule with it and add a test that a re-serialized object with a new timestamp produces the same content hash.

## Conventions

- Python 3.11, Pydantic v2, SQLAlchemy 2.x, Alembic, Typer, structlog, FastMCP.
- `mypy --strict` clean on `glasswing/`. `ruff check` clean. No `# type: ignore` without a DECISIONS.md entry explaining why.
- Tests run offline: `GLASSWING_OFFLINE=1`, pytest-socket active. Any test that needs the network is wrong; fix the test, not the flag.
- Live LLM runs are manual only, operator-initiated, and logged in `docs/live_runs.md` with date, purpose, prompt version, model ID, and approximate token count.
- Agent prompts live in `prompts/<agent>/<version>.md`, loaded at runtime. Editing behavior means a new version file, not an edit to the old one.
- Framework datasets in `glasswing/mcp/data/frameworks/` are versioned JSON. Never edit a published version in place — regulatory content changes are new version files with `effective_from` dates. A classification pinned to a framework version must replay identically forever.
- Never commit: secrets, `.env`, API keys, client names, client data. All fixtures are fictional. If a real engagement teaches you something, the lesson enters the fixture set as a synthetic equivalent, never as the client's data.

## Working process

**Ambiguity rule.** When the spec is ambiguous, choose the most conservative interpretation, record it in DECISIONS.md, and continue. Do not stop to ask mid-task. DECISIONS.md entry format:

```
## D-014 — 2026-07-21 — Does completeness_score count declined fields as unknown?
Question: Intake schema distinguishes unknown from declined; spec formula says "fields not unknown."
Choice: Declined counts as unknown for scoring (conservative: lowers completeness).
Why: Overstating completeness risks classification on missing data; understating only costs a follow-up.
Status: OPEN for Renee review.
```

**Out-of-scope bugs.** Flag them in the PR description under a "Found, not fixed" heading with file path and one-line description. Do not fix without approval.

**PR cadence.** One PR per week of spec work. PR description must contain: (1) spec section implemented, (2) each acceptance criterion with the exact command that demonstrates it and its result, (3) DECISIONS.md entries added this week, (4) "Found, not fixed" list. A PR whose description doesn't map to acceptance criteria is not done.

**Session workflow.** Start: read the spec section for the current week, read DECISIONS.md entries marked OPEN. End: run the week's acceptance commands, run the full test suite, commit. Do not skip the commit at the end of a clean session.

## Do not

- Do not build ahead of the current phase/week. Stubs required by current-week code are allowed; implementations are not.
- Do not rebuild components that exist unless the spec's disposition table (section 5) says they change.
- Do not add features beyond scoped work, including "obvious improvements."
- Do not create background tasks, sidecar sessions, or parallel work streams.
- Do not weaken, skip, or mark-xfail an invariant test to make a PR pass.
- Do not paraphrase regulatory text when authoring framework datasets — quote or cite, and record the source and verification date in the dataset's `verification_note`.
