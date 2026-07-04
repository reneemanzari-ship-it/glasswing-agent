"""
CLI entry point for the AI Risk Tier Classification skill.

Usage:
    python -m skills.ai_risk_tier_classification --input examples/example_high_risk_loan.json
    python -m skills.ai_risk_tier_classification --description "Freeform text describing an AI initiative"

--input accepts either a raw Initiative JSON payload, or one of the
examples/*.json files in this skill (which wrap the Initiative under an
"input_initiative" key alongside a scenario label and expected output).
"""
import argparse
import json

from schemas.initiative import Initiative
from skills.ai_risk_tier_classification.scripts.classifier import AIRiskTierClassificationSkill


def main():
    parser = argparse.ArgumentParser(
        prog="python -m skills.ai_risk_tier_classification",
        description="Classify an AI initiative's regulatory risk tier (EU AI Act, NIST AI RMF, Colorado SB 205).",
    )
    parser.add_argument("--input", help="Path to a JSON file with an Initiative payload (or an examples/*.json file).")
    parser.add_argument("--description", help="Freeform natural-language description to classify instead of a structured Initiative.")
    args = parser.parse_args()

    skill = AIRiskTierClassificationSkill()

    if args.description:
        risk_profile = skill.classify_from_description(args.description)
    elif args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            payload = json.load(f)
        initiative_data = payload.get("input_initiative", payload)
        risk_profile = skill.classify(Initiative(**initiative_data))
    else:
        parser.error("Provide either --input <initiative.json> or --description <text>.")
        return

    print(risk_profile.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
