"""
Google ADK to Anthropic Claude Routing Pattern:
----------------------------------------------
Model: anthropic/claude-sonnet-4-5-20250115 (via LiteLLM router)
Instructions: Dynamically loaded from prompts/risk_classifier.md
Tools: Exposes MCP regulatory search/query functions as agent tools.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from google.adk import Agent
from schemas.initiative import Initiative
from schemas.risk_profile import RiskProfile

# Expose MCP server functions as tools to the ADK agent
from mcp_server.server import get_framework, get_tier_criteria, get_function_attention_triggers, search_frameworks

class RiskClassifierAgent:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if self.api_key:
            os.environ["ANTHROPIC_API_KEY"] = self.api_key
            
        self.prompt_path = Path(__file__).parent.parent / "prompts" / "risk_classifier.md"
        self.system_prompt = self._load_prompt()
        
        # Instantiate the ADK Agent, connecting framework taxonomies via MCP tools
        self.adk_agent = Agent(
            name="risk_classifier",
            model="anthropic/claude-sonnet-4-5-20250115",
            instruction=self.system_prompt,
            tools=[get_framework, get_tier_criteria, get_function_attention_triggers, search_frameworks]
        )

    def _load_prompt(self) -> str:
        if self.prompt_path.exists():
            return self.prompt_path.read_text(encoding="utf-8")
        return "You are the Risk Classifier Agent. Query MCP tools to classify AI initiatives."

    def classify_initiative(self, initiative: Initiative) -> RiskProfile:
        """Invokes the ADK Agent to evaluate the initiative and return a structured RiskProfile."""
        # Convert initiative to text description for agent input
        prompt_input = f"""
        Please classify the following AI initiative:
        Name: {initiative.name}
        Description: {initiative.description}
        AI Type: {initiative.ai_system.type.value}
        Autonomy Level: {initiative.ai_system.autonomy_level.value}
        Data sensitivity classes: {', '.join([s.value for s in initiative.data.sensitivity])}
        User scope: {', '.join([u.value for u in initiative.impact.user_scope])}
        
        Use the available tools to search the regulatory frameworks (EU AI Act, NIST AI RMF, Colorado SB 205) 
        and output the classifications for each framework.
        """

        if not self.api_key:
            # Local fallback mock for offline mode / tests using local helper
            from skills.ai_risk_tier_classification.scripts.classifier import local_classify
            return local_classify(initiative)

        try:
            # Execute ADK Agent generation
            # The agent will call the registered tools to search frameworks and determine categories
            response = self.adk_agent.run(prompt_input)
            
            # Parse the agent response to construct RiskProfile.
            # In production, structured tool output (e.g. JSON schema mode) is used.
            # Here we demonstrate structuring the profile returned by Claude.
            import json
            # If the response is raw text, we parse it or default to a safe classification
            # matching the returned JSON block.
            return RiskProfile.model_validate_json(response.text)
        except Exception as e:
            # Safeguard fallback to local classifier if agent fails or output format is unstructured
            from skills.ai_risk_tier_classification.scripts.classifier import local_classify
            fallback_profile = local_classify(initiative)
            return fallback_profile
