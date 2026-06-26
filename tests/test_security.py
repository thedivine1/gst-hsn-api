import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_missing_api_key():
    """Test 422 (or 401) when API key header is missing."""
    response = client.get("/v1/hsn/24021000")
    # FastAPI raises 422 for missing required headers if defined with Header(...)
    assert response.status_code == 422

def test_invalid_api_key():
    """Test 401 when API key is invalid."""
    response = client.get("/v1/hsn/24021000", headers={"X-API-Key": "invalid_random_key"})
    assert response.status_code == 401
    assert "Invalid or inactive API key" in response.text

def test_sql_injection_sanitization():
    """
    Test that malicious payloads do not crash the application.
    FastAPI and Supabase Python client automatically parameterize and escape these.
    """
    payload = {"description": "'; DROP TABLE hsn_rates; --"}
    response = client.post("/v1/lookup", json=payload, headers={"X-API-Key": "gsta_demo_frontend"})
    # Should safely return 200 (with empty results) rather than crashing
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    
def test_nosql_injection_sanitization():
    """Test handling of weird payload structures."""
    payload = {"description": {"$gt": ""}} # Invalid type (dict instead of str)
    response = client.post("/v1/lookup", json=payload, headers={"X-API-Key": "gsta_demo_frontend"})
    # Pydantic should catch this and return 422 Validation Error
    assert response.status_code == 422
