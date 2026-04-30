import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# =========================
# 1. Health check
# =========================
def test_api_running():
    response = client.get("/")
    assert response.status_code == 200


# =========================
# 2. Negative review → complaint flow
# =========================
@patch("app.services.orchestrator.decision_agent", new_callable=AsyncMock)
@patch("app.services.orchestrator.complaint_agent", new_callable=AsyncMock)
@patch("app.services.orchestrator.reply_agent", new_callable=AsyncMock)
@patch("app.services.orchestrator.compliance_agent", new_callable=AsyncMock)
def test_negative_review_creates_complaint(mock_compliance, mock_reply, mock_complaint, mock_decision):
    mock_decision.return_value = {
        "classification": {"sentiment": "negative", "issue_type": "service", "rating": 1},
        "issues": ["Bad service"],
        "severity": "high",
        "action": "complaint",
        "create_ticket": True,
        "response": "We are sorry.",
        "reason": "low rating",
        "confidence": 0.9,
    }
    mock_complaint.return_value = {"status": "created", "ticket_id": "TICKET123"}
    mock_reply.return_value = "We are sorry for your experience. We will look into this."
    mock_compliance.return_value = {
        "status": "approved",
        "final_reply": "We are sorry for your experience. We will look into this.",
        "reason": "compliant",
    }

    payload = {
        "comment": "Very bad experience",
        "star_rating": 1,
        "reviewer": "Sam",
        "location_name": "K.K. Nagar",
        "review_date": "2024-01-01",
    }

    response = client.post("/process-review", json=payload)
    assert response.status_code == 200

    data = response.json()
    result = data["data"]

    assert data["status"] == "success"
    assert result["reply"] is not None
    assert result["complaint_link"] is not None
    assert result["decision"]["classification"]["sentiment"] == "negative"
    assert result["decision"]["create_ticket"] is True


# =========================
# 3. Positive review → no complaint
# =========================
@patch("app.services.orchestrator.decision_agent", new_callable=AsyncMock)
@patch("app.services.orchestrator.reply_agent", new_callable=AsyncMock)
@patch("app.services.orchestrator.compliance_agent", new_callable=AsyncMock)
def test_positive_review_no_complaint(mock_compliance, mock_reply, mock_decision):
    mock_decision.return_value = {
        "classification": {"sentiment": "positive", "issue_type": "other", "rating": 5},
        "issues": [],
        "severity": "low",
        "action": "reply",
        "create_ticket": False,
        "response": "Thank you!",
        "reason": "high rating",
        "confidence": 0.95,
    }
    mock_reply.return_value = "Thank you for the wonderful feedback!"
    mock_compliance.return_value = {
        "status": "approved",
        "final_reply": "Thank you for the wonderful feedback!",
        "reason": "compliant",
    }

    payload = {
        "comment": "Great service, very happy!",
        "star_rating": 5,
        "reviewer": "John",
        "location_name": "Anna Nagar",
        "review_date": "2024-01-01",
    }

    response = client.post("/process-review", json=payload)
    assert response.status_code == 200

    data = response.json()
    result = data["data"]

    assert result["complaint_link"] is None or result["complaint_link"] == ""
    assert result["reply"] is not None


# =========================
# 4. Sensitive review → blocked
# =========================
def test_sensitive_review_blocked():
    payload = {
        "comment": "This is fraud! I will call the police.",
        "star_rating": 1,
        "reviewer": "Angry",
        "location_name": "Anna Nagar",
        "review_date": "2024-01-01",
    }

    response = client.post("/process-review", json=payload)
    assert response.status_code == 200

    data = response.json()
    result = data["data"]
    assert result["type"] == "blocked"
    assert result["reply"] is not None


# =========================
# 5. Low confidence → needs_manual flag
# =========================
@patch("app.services.orchestrator.decision_agent", new_callable=AsyncMock)
@patch("app.services.orchestrator.reply_agent", new_callable=AsyncMock)
@patch("app.services.orchestrator.compliance_agent", new_callable=AsyncMock)
def test_low_confidence_flags_manual(mock_compliance, mock_reply, mock_decision):
    mock_decision.return_value = {
        "classification": {"sentiment": "negative", "issue_type": "other", "rating": 1},
        "issues": [],
        "severity": "high",
        "action": "complaint",
        "create_ticket": False,
        "response": "",
        "reason": "fallback",
        "confidence": 0.5,
    }
    mock_reply.return_value = "We are sorry for your experience."
    mock_compliance.return_value = {
        "status": "approved",
        "final_reply": "We are sorry for your experience.",
        "reason": "compliant",
    }

    payload = {
        "comment": "",
        "star_rating": 1,
        "reviewer": "Test",
        "location_name": "Anna Nagar",
        "review_date": "2024-01-01",
    }

    response = client.post("/process-review", json=payload)
    assert response.status_code == 200

    data = response.json()
    result = data["data"]
    assert result.get("needs_manual") is True


# =========================
# 6. Response structure
# =========================
@patch("app.services.orchestrator.decision_agent", new_callable=AsyncMock)
@patch("app.services.orchestrator.reply_agent", new_callable=AsyncMock)
@patch("app.services.orchestrator.compliance_agent", new_callable=AsyncMock)
def test_response_structure(mock_compliance, mock_reply, mock_decision):
    mock_decision.return_value = {
        "classification": {"sentiment": "neutral", "issue_type": "other", "rating": 3},
        "issues": [],
        "severity": "low",
        "action": "reply",
        "create_ticket": False,
        "response": "Thank you.",
        "reason": "neutral rating",
        "confidence": 0.9,
    }
    mock_reply.return_value = "Thank you for your average feedback."
    mock_compliance.return_value = {
        "status": "approved",
        "final_reply": "Thank you for your average feedback.",
        "reason": "compliant",
    }

    payload = {
        "comment": "Average service",
        "star_rating": 3,
        "reviewer": "Alex",
        "location_name": "Anna Nagar",
        "review_date": "2024-01-01",
    }

    response = client.post("/process-review", json=payload)
    data = response.json()

    assert "status" in data
    assert "data" in data

    result = data["data"]
    for field in ["job_id", "status", "reply", "decision", "logs", "history"]:
        assert field in result
