import os
import json
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# Initialize the FastMCP server
mcp = FastMCP("RegulatoryFrameworks")

FRAMEWORKS_DIR = Path(__file__).parent / "frameworks"

# Synonym mapping to translate common use-case terms to regulatory taxonomy keywords
SYNONYM_MAP = {
    "loan": ["credit", "lending", "finance", "bank"],
    "loans": ["credit", "lending", "finance", "bank"],
    "decisioning": ["decision", "decisions", "assess", "assessment", "evaluation"],
    "decision": ["decisions", "assess", "assessment", "evaluation"],
    "hiring": ["employment", "recruitment", "resume", "cv", "worker", "promotion", "termination"],
    "screening": ["employment", "recruitment", "resume", "cv", "admission", "enrollment"],
    "proctoring": ["education", "admission", "evaluation", "assessment"]
}

# Stop words to ignore during query tokenization
STOP_WORDS = {
    "with", "without", "and", "or", "but", "the", "for", "in", "on", "at", "by", "from", 
    "to", "of", "a", "an", "this", "that", "these", "those", "is", "are", "was", "were", 
    "be", "been", "have", "has", "had", "do", "does", "did", "not", "no", "yes", "any", 
    "some", "all", "each", "both", "either", "neither", "can", "could", "shall", "should", 
    "will", "would", "may", "might", "must"
}

def _load_framework_json(name: str) -> dict:
    file_path = FRAMEWORKS_DIR / f"{name}.json"
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

@mcp.tool()
def get_framework(framework_id: str) -> str:
    """Retrieves framework metadata and structure by ID.
    Supported IDs: 'eu_ai_act', 'nist_ai_rmf', 'colorado_sb_205'.
    """
    data = _load_framework_json(framework_id)
    if not data:
        return f"Framework '{framework_id}' not found."
    return json.dumps({
        "framework_id": data.get("framework_id"),
        "name": data.get("name"),
        "description": data.get("description"),
        "version": data.get("version"),
        "source_url": data.get("source_url")
    }, indent=2)

@mcp.tool()
def get_tier_criteria(framework_id: str, tier: str) -> str:
    """Retrieves the criteria and details of a specific risk tier in a framework.
    Only applicable to tier-based frameworks (like 'eu_ai_act').
    """
    data = _load_framework_json(framework_id)
    if not data:
        return f"Framework '{framework_id}' not found."
    
    tiers = data.get("tiers", {})
    if not tiers:
        return f"Framework '{framework_id}' is not tier-based."
    
    tier_data = tiers.get(tier)
    if not tier_data:
        valid_tiers = ", ".join(tiers.keys())
        return f"Tier '{tier}' not found. Available tiers: {valid_tiers}"
        
    return json.dumps(tier_data, indent=2)

@mcp.tool()
def get_function_attention_triggers(framework_id: str, function_name: str) -> str:
    """Retrieves elevated and critical attention triggers for a specific NIST function.
    Only applicable to function-based frameworks (like 'nist_ai_rmf').
    """
    data = _load_framework_json(framework_id)
    if not data:
        return f"Framework '{framework_id}' not found."
        
    functions = data.get("functions", {})
    if not functions:
        return f"Framework '{framework_id}' is not function-based."
        
    func_data = functions.get(function_name.lower())
    if not func_data:
        valid_funcs = ", ".join(functions.keys())
        return f"Function '{function_name}' not found. Available functions: {valid_funcs}"
        
    return json.dumps({
        "name": func_data.get("name"),
        "description": func_data.get("description"),
        "elevated_attention_triggers": func_data.get("elevated_attention_triggers", []),
        "critical_attention_triggers": func_data.get("critical_attention_triggers", [])
    }, indent=2)

@mcp.tool()
def get_required_controls(framework_id: str, tier_or_function: str) -> str:
    """Retrieves the list of required compliance controls for a risk tier or function."""
    data = _load_framework_json(framework_id)
    if not data:
        return f"Framework '{framework_id}' not found."
        
    # Check tiers first (e.g. EU AI Act)
    if "tiers" in data:
        tier_data = data["tiers"].get(tier_or_function)
        if tier_data:
            return json.dumps({
                "tier": tier_or_function,
                "required_controls": tier_data.get("required_controls", [])
            }, indent=2)
            
    # Check functions next (e.g. NIST AI RMF)
    if "functions" in data:
        func_data = data["functions"].get(tier_or_function.lower())
        if func_data:
            # NIST categories serve as target control objectives
            return json.dumps({
                "function": tier_or_function,
                "target_control_objectives": func_data.get("categories", [])
            }, indent=2)
            
    return f"No controls found for '{tier_or_function}' in framework '{framework_id}'."

@mcp.tool()
def search_frameworks(use_case_description: str) -> str:
    """Searches across all loaded frameworks (scans tiers, functions, examples, and attention triggers)
    to find matches for a given use-case description.
    """
    frameworks = ["eu_ai_act", "nist_ai_rmf", "colorado_sb_205"]
    matches = []
    
    # Preprocess description and expand query with synonyms
    raw_words = [w.strip(".,;:?!()\"'").lower() for w in use_case_description.split()]
    search_keywords = set()
    for w in raw_words:
        if len(w) > 2 and w not in STOP_WORDS:
            search_keywords.add(w)
            if w in SYNONYM_MAP:
                search_keywords.update(SYNONYM_MAP[w])

    for fw in frameworks:
        data = _load_framework_json(fw)
        if not data:
            continue
            
        fw_name = data.get("name", fw)
        fw_matches = []
        
        # Search tier-based frameworks (like EU AI Act)
        if "tiers" in data:
            for tier_id, tier_data in data["tiers"].items():
                tier_str = json.dumps(tier_data).lower()
                matched_for_tier = []
                for kw in search_keywords:
                    if kw in tier_str:
                        # Find specific category details. Different frameworks
                        # name their category-breakdown dict differently (EU
                        # AI Act uses "annex_iii_categories", Colorado SB 205
                        # uses "consequential_decision_categories") — check
                        # every known shape rather than hardcoding just one,
                        # or frameworks other than EU AI Act never match here.
                        annex_matches = []
                        criteria = tier_data.get("criteria", {})
                        for category_dict_key in ("annex_iii_categories", "consequential_decision_categories"):
                            categories = criteria.get(category_dict_key, {})
                            for cat_key, cat_val in categories.items():
                                if kw in cat_val.lower():
                                    annex_matches.append(f"{category_dict_key} '{cat_key}': {cat_val}")

                        examples_matched = [ex for ex in tier_data.get("criteria", {}).get("examples", []) if kw in ex.lower()]
                        
                        if annex_matches or examples_matched:
                            detail = ""
                            if annex_matches:
                                detail += "; ".join(annex_matches)
                            if examples_matched:
                                if detail:
                                    detail += " | "
                                detail += "Examples: " + ", ".join(examples_matched)
                            matched_for_tier.append(f"Matched keyword '{kw}' -> {detail}")
                        
                if matched_for_tier:
                    match_desc = f"Risk Tier: {tier_data.get('name')}\n" + "\n".join([f"      * {m}" for m in matched_for_tier])
                    fw_matches.append(match_desc)
                        
        # Search function-based frameworks (like NIST AI RMF)
        if "functions" in data:
            for func_id, func_data in data["functions"].items():
                func_str = json.dumps(func_data).lower()
                matched_for_func = []
                for kw in search_keywords:
                    if kw in func_str:
                        triggered_elevated = [t for t in func_data.get("elevated_attention_triggers", []) if kw in t.lower()]
                        triggered_critical = [t for t in func_data.get("critical_attention_triggers", []) if kw in t.lower()]
                        
                        if triggered_critical or triggered_elevated:
                            detail = ""
                            if triggered_critical:
                                detail += "[CRITICAL] " + "; ".join(triggered_critical)
                            if triggered_elevated:
                                if detail:
                                    detail += " | "
                                detail += "[ELEVATED] " + "; ".join(triggered_elevated)
                            matched_for_func.append(f"Matched keyword '{kw}' -> {detail}")
                            
                if matched_for_func:
                    match_desc = f"Function: {func_data.get('name')}\n" + "\n".join([f"      * {m}" for m in matched_for_func])
                    fw_matches.append(match_desc)
                        
        if fw_matches:
            matches.append(f"## Matches in {fw_name}:")
            for m in fw_matches:
                matches.append(f"  * {m}")
                
    if not matches:
        return f"No specific regulatory matches found for description: '{use_case_description}'"
        
    return "\n".join(matches)

if __name__ == "__main__":
    import sys
    # If run with a testing argument, print outputs directly
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print("Running verification tests...")
        print("\n--- get_framework(nist_ai_rmf) ---")
        print(get_framework("nist_ai_rmf"))
        print("\n--- get_function_attention_triggers(nist_ai_rmf, manage) ---")
        print(get_function_attention_triggers("nist_ai_rmf", "manage"))
        print("\n--- search_frameworks('consumer loan approval with autonomous decisioning') ---")
        print(search_frameworks("consumer loan approval with autonomous decisioning"))
    else:
        mcp.run()
