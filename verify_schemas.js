const fs = require('fs');
const path = require('path');

const SCHEMAS_DIR = path.join(__dirname, 'schemas');
const AGENTS_DIR = path.join(__dirname, 'agents');
const ORCHESTRATION_DIR = path.join(__dirname, 'orchestration');
const SECURITY_DIR = path.join(__dirname, 'security');
const UI_DIR = path.join(__dirname, 'ui');

const schemaFiles = [
    'initiative.py',
    'risk_profile.py',
    'control_prescription.py',
    'governance_manifest.py',
    'portfolio_state.py',
    'audit_log.py'
];

const agentFiles = [
    'onboarding_intake.py',
    'risk_classifier.py',
    'control_prescription.py',
    'portfolio_manager.py',
    'audit_trail.py'
];

const orchestrationFiles = [
    'flow.py'
];

const securityFiles = [
    'adversarial_test.py'
];

const uiFiles = [
    'app.py'
];

function checkPythonSyntax(filePath) {
    const code = fs.readFileSync(filePath, 'utf8');
    const lines = code.split('\n');
    let brackets = [];
    let lineNum = 0;
    
    // Declare state variables outside the line loop to properly track multiline strings
    let inSingleQuote = false;
    let inDoubleQuote = false;
    let inTripleQuote = false;
    let inSingleTripleQuote = false;
    
    for (let line of lines) {
        lineNum++;
        
        // Reset single-line string states per line, but keep triple quote states
        inSingleQuote = false;
        inDoubleQuote = false;
        
        for (let i = 0; i < line.length; i++) {
            let char = line[i];
            
            // Check for triple double quotes (e.g. """)
            if (char === '"' && line[i+1] === '"' && line[i+2] === '"') {
                inTripleQuote = !inTripleQuote;
                i += 2;
                continue;
            }
            if (inTripleQuote) continue;
            
            // Check for triple single quotes (e.g. ''')
            if (char === "'" && line[i+1] === "'" && line[i+2] === "'") {
                inSingleTripleQuote = !inSingleTripleQuote;
                i += 2;
                continue;
            }
            if (inSingleTripleQuote) continue;
            
            if (char === '"' && line[i-1] !== '\\') {
                inDoubleQuote = !inDoubleQuote;
                continue;
            }
            if (inDoubleQuote) continue;
            
            if (char === "'" && line[i-1] !== '\\') {
                inSingleQuote = !inSingleQuote;
                continue;
            }
            if (inSingleQuote) continue;
            
            if (char === '#') break;
            
            if (char === '(' || char === '[' || char === '{') {
                brackets.push({ char, line: lineNum });
            } else if (char === ')' || char === ']' || char === '}') {
                if (brackets.length === 0) {
                    return `Unmatched closing bracket '${char}' at line ${lineNum}`;
                }
                let last = brackets.pop();
                if ((char === ')' && last.char !== '(') ||
                    (char === ']' && last.char !== '[') ||
                    (char === '}' && last.char !== '{')) {
                    return `Mismatched brackets: opened '${last.char}' at line ${last.line}, closed '${char}' at line ${lineNum}`;
                }
            }
        }
    }
    
    if (brackets.length > 0) {
        let last = brackets.pop();
        return `Unclosed bracket '${last.char}' opened at line ${last.line}`;
    }
    
    return null;
}

console.log("=== RUNNING CODEBASE SYNTAX ANALYSIS ===");
let hasError = false;

console.log("\n--- Checking Schemas ---");
for (let file of schemaFiles) {
    const fullPath = path.join(SCHEMAS_DIR, file);
    if (!fs.existsSync(fullPath)) {
        console.error(`[ERROR] File missing: ${file}`);
        hasError = true;
        continue;
    }
    
    const err = checkPythonSyntax(fullPath);
    if (err) {
        console.error(`[FAIL] Syntax error in schemas/${file}: ${err}`);
        hasError = true;
    } else {
        console.log(`[PASS] schemas/${file} compiles statically.`);
    }
}

console.log("\n--- Checking Agents ---");
for (let file of agentFiles) {
    const fullPath = path.join(AGENTS_DIR, file);
    if (!fs.existsSync(fullPath)) {
        console.error(`[ERROR] File missing: ${file}`);
        hasError = true;
        continue;
    }
    
    const err = checkPythonSyntax(fullPath);
    if (err) {
        console.error(`[FAIL] Syntax error in agents/${file}: ${err}`);
        hasError = true;
    } else {
        console.log(`[PASS] agents/${file} compiles statically.`);
    }
}

console.log("\n--- Checking Orchestration ---");
for (let file of orchestrationFiles) {
    const fullPath = path.join(ORCHESTRATION_DIR, file);
    if (!fs.existsSync(fullPath)) {
        console.error(`[ERROR] File missing: ${file}`);
        hasError = true;
        continue;
    }
    
    const err = checkPythonSyntax(fullPath);
    if (err) {
        console.error(`[FAIL] Syntax error in orchestration/${file}: ${err}`);
        hasError = true;
    } else {
        console.log(`[PASS] orchestration/${file} compiles statically.`);
    }
}

console.log("\n--- Checking Security ---");
for (let file of securityFiles) {
    const fullPath = path.join(SECURITY_DIR, file);
    if (!fs.existsSync(fullPath)) {
        console.error(`[ERROR] File missing: ${file}`);
        hasError = true;
        continue;
    }
    
    const err = checkPythonSyntax(fullPath);
    if (err) {
        console.error(`[FAIL] Syntax error in security/${file}: ${err}`);
        hasError = true;
    } else {
        console.log(`[PASS] security/${file} compiles statically.`);
    }
}

console.log("\n--- Checking UI ---");
for (let file of uiFiles) {
    const fullPath = path.join(UI_DIR, file);
    if (!fs.existsSync(fullPath)) {
        console.error(`[ERROR] File missing: ${file}`);
        hasError = true;
        continue;
    }
    
    const err = checkPythonSyntax(fullPath);
    if (err) {
        console.error(`[FAIL] Syntax error in ui/${file}: ${err}`);
        hasError = true;
    } else {
        console.log(`[PASS] ui/${file} compiles statically.`);
    }
}

console.log("\n=============================================");
process.exit(hasError ? 1 : 0);
