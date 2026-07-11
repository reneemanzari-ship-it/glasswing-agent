"""Structural enforcement of CLAUDE.md invariant #1 and the Week 4
boundary invariant (GLASSWING_SPEC.md section 3): the LLM extracts,
the deterministic engine classifies. Both checks are structural (parsed
from the actual code / schema), not behavioral conventions that could
silently erode.
"""

from __future__ import annotations

import ast
from pathlib import Path

from glasswing.core.extracted_evidence import (
    FORBIDDEN_FIELD_NAMES,
    ExtractedEvidence,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
GLASSWING_ROOT = REPO_ROOT / "glasswing"

# Any of these appearing in an import inside engines/ or services/ means
# that code could make a model call -- forbidden regardless of whether
# it's actually invoked (CLAUDE.md invariant #1: "No LLM calls in
# glasswing/engines/ or glasswing/services/. Ever.").
FORBIDDEN_IMPORT_PREFIXES = (
    "glasswing.agents",
    "anthropic",
    "claude_agent_sdk",
    "google.adk",
    "google_adk",
)


def _imported_module_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _all_python_files(directory: Path) -> list[Path]:
    return sorted(directory.rglob("*.py"))


def test_extracted_evidence_has_no_classification_fields() -> None:
    """Structural, not behavioral: the extraction agent's own output
    TYPE cannot carry a tier, a classification, or a control -- checked
    against the model's actual field names, not against what the agent
    happens to populate today."""
    field_names = set(ExtractedEvidence.model_fields.keys())
    overlap = field_names & FORBIDDEN_FIELD_NAMES
    assert not overlap, (
        f"ExtractedEvidence must never define a classification/control "
        f"field; found: {overlap}"
    )


def _is_forbidden(name: str) -> bool:
    return any(
        name == prefix or name.startswith(prefix + ".")
        for prefix in FORBIDDEN_IMPORT_PREFIXES
    )


def _find_model_capable_imports(package_dir: Path) -> dict[str, set[str]]:
    offenders: dict[str, set[str]] = {}
    for path in _all_python_files(package_dir):
        hits = {name for name in _imported_module_names(path) if _is_forbidden(name)}
        if hits:
            offenders[str(path.relative_to(REPO_ROOT))] = hits
    return offenders


def test_engines_package_imports_nothing_that_can_call_a_model() -> None:
    offenders = _find_model_capable_imports(GLASSWING_ROOT / "engines")
    assert not offenders, f"glasswing/engines/ imports model-capable: {offenders}"


def test_services_package_imports_nothing_that_can_call_a_model() -> None:
    offenders = _find_model_capable_imports(GLASSWING_ROOT / "services")
    assert not offenders, f"glasswing/services/ imports model-capable: {offenders}"


def test_forbidden_import_prefixes_are_not_vacuous() -> None:
    """If glasswing/agents/base.py stopped importing `anthropic` (e.g. an
    SDK swap), this test's premise -- that "anthropic" is genuinely a
    model-capable import worth banning elsewhere -- would go untested.
    Confirms the boundary check above is exercised against a real
    model-capable module, not a name nobody imports."""
    agents_dir = GLASSWING_ROOT / "agents"
    all_imports: set[str] = set()
    for path in _all_python_files(agents_dir):
        all_imports |= _imported_module_names(path)
    assert "anthropic" in all_imports
