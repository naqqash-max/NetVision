import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

def test_cors_configured_origin_allowed():
    client = TestClient(app)
    # Test with one of the default allowed origins
    origin = "http://localhost:3000"
    response = client.get("/", headers={"Origin": origin, "Access-Control-Request-Method": "GET"})
    # It should echo back the allowed origin
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.headers.get("access-control-allow-credentials") == "true"

def test_cors_unconfigured_origin_rejected():
    client = TestClient(app)
    # Try a disallowed/external origin
    origin = "http://malicious-external-domain.com"
    response = client.get("/", headers={"Origin": origin, "Access-Control-Request-Method": "GET"})
    # Disallowed origin should NOT have Access-Control-Allow-Origin set to the malicious domain
    assert response.headers.get("access-control-allow-origin") != origin

def test_cors_wildcard_rejected():
    client = TestClient(app)
    # Test wildcard origin request
    response = client.get("/", headers={"Origin": "*", "Access-Control-Request-Method": "GET"})
    assert response.headers.get("access-control-allow-origin") != "*"
