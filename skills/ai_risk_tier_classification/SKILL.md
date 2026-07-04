---
name: ai_risk_tier_classification
description: Classifies AI systems into regulatory risk categories for the EU AI Act, NIST AI RMF, and Colorado SB 205.
---

# AI Risk Tier Classification Skill

This skill implements modular risk classification logic to run deterministic and heuristic analyses of proposed AI initiatives against major frameworks.

## Integration Pattern
Rather than hardcoding compliance taxonomy mapping inside system prompts, this skill uses a structured assessment schema and a standalone python rule engine.

## Inputs
The skill expects a payload matching the `Initiative` schema containing:
- `intended_use` (string)
- `description` (string)
- `data_sources` (list of strings)
- `user_impact` (string)

## Core Classifications
1. **EU AI Act Risk Tiers**:
   - **Unacceptable**: Prohibited applications (e.g. social scoring, dark pattern exploitation).
   - **High**: Applications in employment, finance, education, healthcare, migration, law enforcement.
   - **Limited**: Chatbots, deepfakes, emotion recognition.
   - **Minimal/None**: Games, spam filters, general utility systems.
2. **Colorado SB 205 High-Risk Decisions**:
   - Classifies as high-risk if it determines critical life-outcomes like employment, education eligibility, finance/lending, healthcare, housing, insurance, or legal routing.
3. **NIST AI RMF Core Objectives**:
   - Prescribes context-specific activities for **Govern**, **Map**, **Measure**, and **Manage**.

## Scripts & Tools
- `scripts/classifier.py`: Evaluates an `Initiative` dictionary and outputs a standard `RiskProfile` payload.

## Usage Example
```python
from skills.ai_risk_tier_classification.scripts.classifier import local_classify
from schemas.initiative import Initiative

init = Initiative(
    id="123",
    name="Exam Proctoring AI",
    description="Proctoring app using facial detection for students taking remote examinations.",
    intended_use="Education performance and identity verification.",
    data_sources=["Video feed", "Student profiles"],
    user_impact="High - identifies cheating behavior and reports to administrator."
)

risk_profile = local_classify(init)
print(risk_profile.eu_ai_act_tier) # Outputs: High Risk
```
