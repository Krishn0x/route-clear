from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
import pytest

def test_health_endpoint_no_auth():
    # client without default headers
    clean_client = TestClient(app)
    response = clean_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_missing_demo_token():
    clean_client = TestClient(app)
    response = clean_client.get("/api/documents/transfers")
    assert response.status_code == 401
    assert "Invalid or missing" in response.json()["detail"]

def test_incorrect_demo_token():
    clean_client = TestClient(app, headers={"x-demo-token": "wrong_token"})
    response = clean_client.get("/api/documents/transfers")
    assert response.status_code == 401
    assert "Invalid or missing" in response.json()["detail"]

def test_correct_demo_token():
    clean_client = TestClient(app, headers={"x-demo-token": settings.DEMO_ACCESS_TOKEN})
    response = clean_client.get("/api/documents/transfers")
    assert response.status_code == 200

def test_cors_allowed_origin():
    clean_client = TestClient(app)
    response = clean_client.options("/api/documents/transfers", headers={
        "Origin": settings.FRONTEND_ORIGIN,
        "Access-Control-Request-Method": "GET"
    })
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == settings.FRONTEND_ORIGIN

def test_cors_disallowed_origin():
    clean_client = TestClient(app)
    response = clean_client.options("/api/documents/transfers", headers={
        "Origin": "http://malicious.com",
        "Access-Control-Request-Method": "GET"
    })
    assert response.status_code == 400
    
def test_missing_config_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "DEMO_ACCESS_TOKEN", "")
    clean_client = TestClient(app, headers={"x-demo-token": "some_token"})
    response = clean_client.get("/api/documents/transfers")
    assert response.status_code == 500
    assert "Server misconfiguration" in response.json()["detail"]
