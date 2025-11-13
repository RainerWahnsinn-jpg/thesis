from fastapi.testclient import TestClient

# Import the FastAPI app directly
from backend.app import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in {"ok", "degraded"}
    assert "rules_version" in data


def test_credit_decision_and_get_application():
    payload = {
        "application_id": "test-123",
        "customer_id": "c-1",
        "income": 3500.0,
        "amount": 5000.0,
        "duration_months": 24,
        "credit_score": 650,
        "existing_loans": 1,
    }
    r = client.post("/credit/decision", json=payload)
    assert r.status_code == 200
    decision = r.json()
    assert set(["application_id", "approved", "reason", "risk_band", "recommended_rate", "policy_flags"]) <= set(decision.keys())

    # Read back from db
    r2 = client.get(f"/applications/{payload['application_id']}")
    assert r2.status_code == 200
    app_rec = r2.json()
    assert app_rec["application_id"] == payload["application_id"]
    assert "decision_approved" in app_rec
