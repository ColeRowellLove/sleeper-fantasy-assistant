from fastapi.testclient import TestClient

from sleeper_assistant.api import app


def test_health() -> None:
    resp = TestClient(app).get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
