# Glasswing Project Rules

## Project overview

Glasswing is a multi-agent AI governance system: three planes, five agents, a custom MCP server, a publishable Agent Skill, and three security features. It takes a proposed AI initiative, classifies its regulatory risk against three frameworks, prescribes the controls that risk tier requires, tracks the initiative's lifecycle in a portfolio, and logs every action to a tamper-evident audit chain.

## Architecture

See README.md's Architecture section for the diagram and full description. Do not duplicate it here.

## Code conventions

- Python 3.11+ with Pydantic v2
- All agent prompts in `prompts/` as versioned markdown, loaded at runtime
- Framework taxonomies in `mcp_server/frameworks/` as JSON, queried via MCP tools
- Every agent handoff validates against Pydantic schemas
- Every audit log entry's hash uses `_stable_hash()` (`orchestration/flow.py`), not raw `model_dump_json()`, for `RiskProfile`, `ControlPrescription`, and `GovernanceManifest` — these carry auto-generated IDs/timestamps that would break replay reproducibility if hashed directly. Plain one-shot logging models without volatile fields (`OnboardingInput`, `TransitionInput`, etc.) use `model_dump_json()` directly.

## Testing rules

- All changes must run pytest without new failures
- 2:47am loan scenario is the canonical integration test
- Adversarial defense must halt before Risk Classifier
- Hash chain integrity must be verifiable after any change

## Security rules

- Never commit .env or API keys
- Never hardcode credentials in code
- All PII must go through the audit log validator
- Adversarial input detection runs before any downstream processing

## Do not

- Do not create background task chips or sidecar sessions
- Do not rebuild agents that exist unless explicitly asked
- Do not add features beyond scoped work
- Do not skip commit at end of clean sessions

## When you find bugs out of scope

Flag them in response text. Do not fix without approval.
