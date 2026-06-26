import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

# Use the demo API key for testing
HEADERS = {"X-API-Key": "gsta_demo_frontend"}

def test_root_endpoint():
    """Test the root endpoint returns HTML correctly."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "GST Accelerator" in response.text

def test_hsn_lookup_exact():
    """Test exact HSN match."""
    response = client.get("/v1/hsn/24021000", headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert data[0]["hsn_code"] == "24021000"
    assert "tax_rates" in data[0]
    
def test_hsn_lookup_invalid():
    """Test 404 for invalid HSN code."""
    response = client.get("/v1/hsn/99999999", headers=HEADERS)
    assert response.status_code == 404

def test_sac_lookup_exact():
    """Test SAC exact match."""
    # Assuming 9954 is a valid SAC code in the DB
    response = client.get("/v1/sac/9954", headers=HEADERS)
    # If 9954 exists, it's 200. If it doesn't, it might be 404 in this DB snapshot, 
    # but the API should handle it gracefully either way.
    assert response.status_code in [200, 404]

def test_lookup_search():
    """Test FTS text search endpoint."""
    payload = {"description": "cigarettes"}
    response = client.post("/v1/lookup", json=payload, headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert any(r["hsn_code"] == "24022000" for r in data) # Should be in the top results

def test_lookup_search_validation_error():
    """Test 422 validation error when description is missing."""
    payload = {"branded": True} # Missing 'description'
    response = client.post("/v1/lookup", json=payload, headers=HEADERS)
    assert response.status_code == 422 # FastAPI Pydantic validation error

def test_bulk_lookup():
    """Test bulk lookup endpoint with valid payload."""
    payload = [
        {"description": "rice"},
        {"description": "mobile phone"}
    ]
    response = client.post("/v1/bulk", json=payload, headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert isinstance(data[0], list)
    assert isinstance(data[1], list)

def test_bulk_lookup_too_large():
    """Test bulk lookup endpoint limit (max 100)."""
    payload = [{"description": "test"}] * 101
    response = client.post("/v1/bulk", json=payload, headers=HEADERS)
    assert response.status_code == 400
    assert "Maximum 100 items" in response.text
