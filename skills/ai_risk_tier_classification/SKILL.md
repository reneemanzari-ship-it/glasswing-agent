---
name: ai_risk_tier_classification
version: 1.0.0
description: Multi-framework AI regulatory risk classification (EU AI Act, NIST AI RMF, Colorado SB 205). Accepts a structured Initiative or a freeform description and returns a RiskProfile with per-framework tier, citations, confidence scores, and a human-review flag.
tags: [risk-classification, compliance, eu-ai-act, nist-ai-rmf, colorado-sb-205, governance, glasswing]
---

# AI Risk Tier Classification Skill

## What this skill does

Classifies a proposed AI initiative against three regulatory frameworks —
the EU AI Act, the NIST AI Risk Management Framework, and Colorado SB 205
— and returns a single structured `RiskProfile` covering all three. It is
the same classification logic the Glasswing Risk Classifier Agent uses in
production (`agents/risk_classifier.py`), packaged here so it can be
called directly by another agent, from a script, or from the command
line, without going through the full five-agent governance pipeline.

This skill is deterministic and runs entirely offline — no model call,
no network access, no API key required. It is not an LLM wrapper; it is
the rule engine an LLM-driven agent falls back to (and, in this
environment, the only classification path actually exercised, since no
`ANTHROPIC_API_KEY` is configured).

## Inputs

Two entry points, both exposed on `AIRiskTierClassificationSkill`:

1. **`classify(initiative: Initiative) -> RiskProfile`** — structured input.
   `Initiative` is the Pydantic schema defined in `schemas/initiative.py`
   (name, sponsor, description, `ai_system`, `data`, `impact`,
   `intake_metadata`, etc.). This is the expected path for another agent
   or any caller that already has a validated `Initiative` object.

2. **`classify_from_description(description: str) -> RiskProfile`** —
   freeform natural-language input. Runs a lightweight, deterministic
   extraction (data sensitivity and user-scope signals from keywords) to
   build a minimal `Initiative`, marking everything it can't determine
   from bare text as unknown and scoring `completeness_score` low
   accordingly. This is a genuine limitation, not a corner cut: fields
   like `hitl_planned` cannot be reliably inferred from a sentence or two,
   so `classify_from_description` will typically return a lower-confidence
   classification with `human_review_required: true` rather than assert
   false certainty. Call `classify()` directly with a properly-intake'd
   `Initiative` whenever one is available — that's the accurate path.

## Outputs

A `RiskProfile` (schema in `schemas/risk_profile.py`), containing:

- `classifications.eu_ai_act` — tier (`prohibited` / `high_risk` /
  `limited_risk` / `minimal_risk`), citations, rationale, confidence,
  applicable Annex III categories
- `classifications.nist_ai_rmf` — attention level (`routine` / `elevated`
  / `critical`) for each of Govern, Map, Measure, Manage, plus citations
  and confidence
- `classifications.colorado_sb_205` — whether the system makes a
  consequential decision, which category, citations, confidence
- `overall_risk_tier` — `low` / `moderate` / `high` / `critical`, derived
  from the EU AI Act tier assignment (not incidentally from NIST attention
  levels alone)
- `human_review_required` and `human_review_reasons` — set whenever
  confidence is capped due to ambiguous intake data, or a mandatory
  control the assigned tier requires (e.g., EU AI Act Article 14 Human
  Oversight, Colorado SB 205 Right to Appeal) appears absent from the
  initiative

## Frameworks covered

| Framework | What it checks |
|---|---|
| EU AI Act | Risk tier (Prohibited / High-Risk Annex III / Limited Risk Article 50 transparency / Minimal), citations to specific Annex III categories or Articles |
| NIST AI RMF | Attention level needed across Govern, Map, Measure, Manage |
| Colorado SB 205 | Whether the system makes or is a substantial factor in a consequential decision (education, employment, financial services, healthcare, housing, insurance, legal services), and which category |

## Example invocations

**1. Structured Initiative, called directly (the path another ADK agent should use):**
```python
from skills.ai_risk_tier_classification.scripts.classifier import AIRiskTierClassificationSkill
from schemas.initiative import Initiative

skill = AIRiskTierClassificationSkill()
initiative = Initiative(**{...})  # see examples/example_high_risk_loan.json
profile = skill.classify(initiative)

print(profile.classifications.eu_ai_act.tier)          # -> high_risk
print(profile.classifications.colorado_sb_205.high_risk_category)  # -> financial_lending
print(profile.overall_risk_tier)                       # -> high
print(profile.human_review_required)                   # -> True
```

**2. Freeform description:**
```python
profile = skill.classify_from_description(
    "Autonomous credit scoring system that approves consumer loans without human review."
)
print(profile.classifications.eu_ai_act.tier)  # -> high_risk
print(profile.human_review_required)           # -> True (autonomy/HITL unconfirmed from text alone)
```

**3. Command line (run from the repo root, since this is invoked as a module):**
```bash
python -m skills.ai_risk_tier_classification --input skills/ai_risk_tier_classification/examples/example_high_risk_loan.json
# or
python -m skills.ai_risk_tier_classification --description "AI chatbot answering customer product questions"
```
Both print the resulting `RiskProfile` as JSON to stdout.

## Files in this skill

- `scripts/classifier.py` — `local_classify()` (the original Day 1
  deterministic rule engine, unchanged — this is what
  `agents/risk_classifier.py` and `security/adversarial_test.py` import
  directly and must keep working) plus `AIRiskTierClassificationSkill`,
  the portable wrapper class described above.
- `__main__.py` — CLI entry point (`python -m skills.ai_risk_tier_classification`).
- `examples/` — four worked examples matching the Day 3 Session 1 test
  scenarios, each with an `input_initiative` and its `expected_risk_profile`:
  `example_high_risk_loan.json`, `example_low_risk_marketing.json`,
  `example_limited_risk_chatbot.json`, `example_ambiguous_hiring.json`.
- Tests live at the repo root, `tests/test_skill.py` — standalone
  invocation, all four examples, CLI invocation, and a regression check
  that the skill's output matches the full Risk Classifier Agent's output
  on the same input.

## Usability

- **Another agent** imports `AIRiskTierClassificationSkill` directly (see
  example 1) — no orchestrator or MCP server required.
- **A human** runs it from the CLI (see example 3).

## Out of scope for this session

**A2A protocol integration is deferred to Day 5 polish.** Wrapping this
skill as an A2A-compatible service (Agent Card, `TaskRequest`/`TaskResponse`
schemas) is a separate, larger piece of work than packaging it for direct
import and CLI use, and is not part of this Day 3 deliverable.
