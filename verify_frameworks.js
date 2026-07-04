const fs = require('fs');
const path = require('path');

const FRAMEWORKS_DIR = path.join(__dirname, 'mcp_server', 'frameworks');

const SYNONYM_MAP = {
    "loan": ["credit", "lending", "finance", "bank"],
    "loans": ["credit", "lending", "finance", "bank"],
    "decisioning": ["decision", "decisions", "assess", "assessment", "evaluation"],
    "decision": ["decisions", "assess", "assessment", "evaluation"],
    "hiring": ["employment", "recruitment", "resume", "cv", "worker", "promotion", "termination"],
    "screening": ["employment", "recruitment", "resume", "cv", "admission", "enrollment"],
    "proctoring": ["education", "admission", "evaluation", "assessment"]
};

const STOP_WORDS = new Set([
    "with", "without", "and", "or", "but", "the", "for", "in", "on", "at", "by", "from", 
    "to", "of", "a", "an", "this", "that", "these", "those", "is", "are", "was", "were", 
    "be", "been", "have", "has", "had", "do", "does", "did", "not", "no", "yes", "any", 
    "some", "all", "each", "both", "either", "neither", "can", "could", "shall", "should", 
    "will", "would", "may", "might", "must"
]);

function _load_framework_json(name) {
    const filePath = path.join(FRAMEWORKS_DIR, `${name}.json`);
    if (fs.existsSync(filePath)) {
        return JSON.parse(fs.readFileSync(filePath, 'utf8'));
    }
    return null;
}

function get_framework(framework_id) {
    const data = _load_framework_json(framework_id);
    if (!data) return `Framework '${framework_id}' not found.`;
    return JSON.stringify({
        framework_id: data.framework_id,
        name: data.name,
        description: data.description,
        version: data.version,
        source_url: data.source_url
    }, null, 2);
}

function get_tier_criteria(framework_id, tier) {
    const data = _load_framework_json(framework_id);
    if (!data) return `Framework '${framework_id}' not found.`;
    const tiers = data.tiers || {};
    if (Object.keys(tiers).length === 0) return `Framework '${framework_id}' is not tier-based.`;
    const tier_data = tiers[tier];
    if (!tier_data) {
        return `Tier '${tier}' not found. Available tiers: ${Object.keys(tiers).join(', ')}`;
    }
    return JSON.stringify(tier_data, null, 2);
}

function get_function_attention_triggers(framework_id, function_name) {
    const data = _load_framework_json(framework_id);
    if (!data) return `Framework '${framework_id}' not found.`;
    const functions = data.functions || {};
    if (Object.keys(functions).length === 0) return `Framework '${framework_id}' is not function-based.`;
    const func_data = functions[function_name.toLowerCase()];
    if (!func_data) {
        return `Function '${function_name}' not found. Available functions: ${Object.keys(functions).join(', ')}`;
    }
    return JSON.stringify({
        name: func_data.name,
        description: func_data.description,
        elevated_attention_triggers: func_data.elevated_attention_triggers || [],
        critical_attention_triggers: func_data.critical_attention_triggers || []
    }, null, 2);
}

function get_required_controls(framework_id, tier_or_function) {
    const data = _load_framework_json(framework_id);
    if (!data) return `Framework '${framework_id}' not found.`;
    if (data.tiers && data.tiers[tier_or_function]) {
        return JSON.stringify({
            tier: tier_or_function,
            required_controls: data.tiers[tier_or_function].required_controls || []
        }, null, 2);
    }
    if (data.functions && data.functions[tier_or_function.toLowerCase()]) {
        const func_data = data.functions[tier_or_function.toLowerCase()];
        return JSON.stringify({
            function: tier_or_function,
            target_control_objectives: func_data.categories || []
        }, null, 2);
    }
    return `No controls found for '${tier_or_function}' in framework '${framework_id}'.`;
}

function search_frameworks(use_case_description) {
    const frameworks = ["eu_ai_act", "nist_ai_rmf", "colorado_sb_205"]; 
    const matches = [];
    
    const raw_words = use_case_description.toLowerCase().split(/\s+/).map(w => w.replace(/[.,;:?!()"'`]/g, ''));
    const search_keywords = new Set();
    
    for (const w of raw_words) {
        if (w.length > 2 && !STOP_WORDS.has(w)) {
            search_keywords.add(w);
            if (SYNONYM_MAP[w]) {
                SYNONYM_MAP[w].forEach(syn => search_keywords.add(syn));
            }
        }
    }
    
    for (const fw of frameworks) {
        const data = _load_framework_json(fw);
        if (!data) continue;
        
        const fw_name = data.name || fw;
        const fw_matches = [];
        
        if (data.tiers) {
            for (const [tier_id, tier_data] of Object.entries(data.tiers)) {
                const tier_str = JSON.stringify(tier_data).toLowerCase();
                const matched_for_tier = [];
                
                for (const kw of search_keywords) {
                    if (tier_str.includes(kw)) {
                        const annex_matches = [];
                        const annex = (tier_data.criteria && tier_data.criteria.annex_iii_categories) || {};
                        const consequential = (tier_data.criteria && tier_data.criteria.consequential_decision_categories) || {};
                        
                        for (const [cat_key, cat_val] of Object.entries(annex)) {
                            if (cat_val.toLowerCase().includes(kw)) {
                                annex_matches.push(`Annex III category '${cat_key}': ${cat_val}`);
                            }
                        }
                        for (const [cat_key, cat_val] of Object.entries(consequential)) {
                            if (cat_val.toLowerCase().includes(kw)) {
                                annex_matches.push(`Consequential category '${cat_key}': ${cat_val}`);
                            }
                        }
                        
                        const examples = (tier_data.criteria && tier_data.criteria.examples) || [];
                        const examples_matched = examples.filter(ex => ex.toLowerCase().includes(kw));
                        
                        if (annex_matches.length > 0 || examples_matched.length > 0) {
                            let detail = "";
                            if (annex_matches.length > 0) {
                                detail += annex_matches.join('; ');
                            }
                            if (examples_matched.length > 0) {
                                if (detail) detail += " | ";
                                detail += "Examples: " + examples_matched.join(', ');
                            }
                            matched_for_tier.push(`Matched keyword '${kw}' -> {${detail}}`);
                        }
                    }
                }
                
                if (matched_for_tier.length > 0) {
                    fw_matches.push(`Risk Tier: ${tier_data.name}\n` + matched_for_tier.map(m => `      * {${m}}`).join('\n'));
                }
            }
        }
        
        if (data.functions) {
            for (const [func_id, func_data] of Object.entries(data.functions)) {
                const func_str = JSON.stringify(func_data).toLowerCase();
                const matched_for_func = [];
                
                for (const kw of search_keywords) {
                    if (func_str.includes(kw)) {
                        const triggered_elevated = (func_data.elevated_attention_triggers || []).filter(t => t.toLowerCase().includes(kw));
                        const triggered_critical = (func_data.critical_attention_triggers || []).filter(t => t.toLowerCase().includes(kw));
                        
                        if (triggered_critical.length > 0 || triggered_elevated.length > 0) {
                            let detail = "";
                            if (triggered_critical.length > 0) {
                                detail += "[CRITICAL] " + triggered_critical.join('; ');
                            }
                            if (triggered_elevated.length > 0) {
                                if (detail) detail += " | ";
                                detail += "[ELEVATED] " + triggered_elevated.join('; ');
                            }
                            matched_for_func.push(`Matched keyword '${kw}' -> {${detail}}`);
                        }
                    }
                }
                
                if (matched_for_func.length > 0) {
                    fw_matches.push(`Function: ${func_data.name}\n` + matched_for_func.map(m => `      * {${m}}`).join('\n'));
                }
            }
        }
        
        if (fw_matches.length > 0) {
            matches.push(`## Matches in ${fw_name}:`);
            fw_matches.forEach(m => matches.push(`  * ${m}`));
        }
    }
    
    if (matches.length === 0) {
        return `No specific regulatory matches found for description: '${use_case_description}'`;
    }
    
    return matches.join('\n');
}

// Running Verification Tests
console.log("=== RUNNING SCENARIO VERIFICATIONS (JS RUNNER) ===");

console.log("\n1. Verification Query: get_framework(framework_id=\"colorado_sb_205\")");
console.log(get_framework("colorado_sb_205"));

console.log("\n2. Verification Query: get_tier_criteria(framework_id=\"colorado_sb_205\", tier=\"high_risk_consequential\")");
console.log(get_tier_criteria("colorado_sb_205", "high_risk_consequential"));

console.log("\n3. Verification Query: search_frameworks(use_case_description=\"consumer loan approval\")");
console.log(search_frameworks("consumer loan approval"));

console.log("\n=================================================");
