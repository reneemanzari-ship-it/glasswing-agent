import pytest
import json
from mcp_server.server import (
    get_framework, 
    get_tier_criteria, 
    get_function_attention_triggers, 
    get_required_controls, 
    search_frameworks
)

def test_get_framework():
    output = get_framework("eu_ai_act")
    assert "EU Artificial Intelligence Act" in output
    
    output_nist = get_framework("nist_ai_rmf")
    assert "NIST AI Risk Management Framework 1.0" in output_nist
    
    missing = get_framework("invalid_fw")
    assert "not found" in missing

def test_get_tier_criteria():
    output = get_tier_criteria("eu_ai_act", "high_risk")
    assert "High-Risk AI Systems (Annex III)" in output
    assert "5_essential_services" in output
    
    missing = get_tier_criteria("eu_ai_act", "invalid_tier")
    assert "not found" in missing

def test_get_function_attention_triggers():
    output = get_function_attention_triggers("nist_ai_rmf", "manage")
    assert "MANAGE" in output
    assert "High-risk AI deployed without HITL" in output
    
    missing = get_function_attention_triggers("nist_ai_rmf", "invalid_func")
    assert "not found" in missing

def test_get_required_controls():
    output_eu = get_required_controls("eu_ai_act", "high_risk")
    assert "RISK_MANAGEMENT_SYSTEM" in output_eu
    
    output_nist = get_required_controls("nist_ai_rmf", "govern")
    assert "GV-1: Policies" in output_nist

def test_search_frameworks():
    output = search_frameworks("consumer loan approval")
    # Must search and route correctly across frameworks
    assert "EU Artificial Intelligence Act" in output
    assert "Colorado SB 24-205" in output
    assert "NIST" in output
    assert "credit" in output.lower() or "loan" in output.lower()
