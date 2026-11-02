import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "Indian Legal" in data["app_name"]
    assert "version" in data


def test_chat_endpoint_schema():
    payload = {
        "question": "What is Section 302 of the Indian Penal Code?"
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "citations" in data
    assert "disclaimer" in data


def test_document_upload_validation():
    # Attempt upload with non-PDF
    files = {"file": ("test.txt", b"plain text content", "text/plain")}
    response = client.post("/api/documents/upload", files=files)
    assert response.status_code == 400
    assert "Only PDF documents are supported" in response.json()["detail"]
