import io
import json
import pytest
from fastapi.testclient import TestClient

from jnaara.api.dependencies import get_belief_manager, get_conflict_resolver, get_db
from jnaara.api.main import app
from jnaara.api.security import limiter
from jnaara.belief.manager import BeliefManager
from jnaara.conflict.detector import ConflictDetector
from jnaara.conflict.resolver import ConflictResolver
from jnaara.db.repository import Repository
from jnaara.models.domain import Fact


from jnaara.db.engine import get_session_factory


@pytest.fixture
def client(db_engine, analyzer, detector, resolver):
    """Test client with overridden dependencies pointing to in-memory test database."""
    session_factory = get_session_factory(db_engine)

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    def override_get_conflict_resolver():
        return resolver

    def override_get_belief_manager():
        session = session_factory()
        repo = Repository(session)
        test_manager = BeliefManager(repo, analyzer, detector, resolver)
        try:
            yield repo, test_manager, resolver, session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_conflict_resolver] = override_get_conflict_resolver
    app.dependency_overrides[get_belief_manager] = override_get_belief_manager

    # Reset limiter storage for clean tests
    limiter.reset()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "jnaara-api"}


def test_security_headers_present(client):
    response = client.get("/health")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("X-XSS-Protection") == "1; mode=block"


def test_submit_fact_success(client):
    payload = {
        "content": "NovaTech reported Q4 2024 revenue of $480M.",
        "source": "Earnings Release",
        "source_reliability": "high",
    }
    response = client.post("/api/facts", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["fact_id"].startswith("fact_")
    assert data["skipped"] is False
    assert len(data["claims"]) >= 1
    assert "NovaTech" in data["claims"][0]["entity"]


def test_submit_fact_schema_validation_failure(client):
    # Missing required field 'content'
    response = client.post("/api/facts", json={"source": "test"})
    assert response.status_code == 422
    data = response.json()
    assert data["error_code"] == "SCHEMA_VALIDATION_ERROR"

    # Extra forbidden field
    response = client.post(
        "/api/facts",
        json={
            "content": "Valid content",
            "malicious_unauthorized_field": "injected",
        },
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error_code"] == "SCHEMA_VALIDATION_ERROR"


def test_bulk_facts_processing(client):
    payload = {
        "facts": [
            {
                "content": "Solaris Energy acquired WindCo for $2.1B in cash.",
                "source": "PR Newswire",
                "source_reliability": "high",
            },
            {
                "content": "Solaris Energy completed the WindCo acquisition.",
                "source": "Regulatory Filing",
                "source_reliability": "high",
            },
        ]
    }
    response = client.post("/api/facts/bulk", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["total_submitted"] == 2
    assert data["total_processed"] == 2
    assert len(data["results"]) == 2


def test_upload_facts_json_file(client):
    file_content = json.dumps([
        {
            "id": "upload_1",
            "content": "Apex Robotics opened a new factory in Austin.",
            "source": "TechCrunch",
            "source_reliability": "medium",
            "timestamp": "2025-02-01T10:00:00Z",
        }
    ]).encode("utf-8")

    files = {"file": ("facts.json", io.BytesIO(file_content), "application/json")}
    response = client.post("/api/facts/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["total_submitted"] == 1
    assert data["total_processed"] == 1


def test_get_beliefs_and_stats(client):
    # Ingest a fact first
    client.post(
        "/api/facts",
        json={
            "content": "QuantumCorp announced a partnership with BigCloud.",
            "source": "Press",
            "source_reliability": "high",
        },
    )

    # Get beliefs
    res_beliefs = client.get("/api/beliefs")
    assert res_beliefs.status_code == 200
    beliefs_data = res_beliefs.json()
    assert beliefs_data["total"] >= 1

    belief_id = beliefs_data["beliefs"][0]["id"]

    # Get single belief
    res_single = client.get(f"/api/beliefs/{belief_id}")
    assert res_single.status_code == 200
    assert res_single.json()["id"] == belief_id

    # Get provenance
    res_prov = client.get(f"/api/beliefs/{belief_id}/provenance")
    assert res_prov.status_code == 200
    assert "history" in res_prov.json()

    # Get stats
    res_stats = client.get("/api/stats")
    assert res_stats.status_code == 200
    stats = res_stats.json()
    assert stats["total_facts"] >= 1
    assert stats["active_beliefs"] >= 1
    assert "recency" in stats["available_strategies"]


def test_switch_strategy(client):
    res = client.post("/api/strategy", json={"strategy": "corroboration"})
    assert res.status_code == 200
    assert "corroboration" in res.json()["message"]

    stats = client.get("/api/stats").json()
    assert stats["active_strategy"] == "corroboration"


def test_reset_database(client):
    client.post(
        "/api/facts",
        json={"content": "Temporary fact to be cleared.", "source": "test"},
    )
    res = client.post("/api/reset")
    assert res.status_code == 200
    stats = client.get("/api/stats").json()
    assert stats["total_facts"] == 0
    assert stats["active_beliefs"] == 0
