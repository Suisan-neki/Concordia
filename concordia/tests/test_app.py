from fastapi.testclient import TestClient

from concordia.app.main import app


def test_health_endpoint_exists():
    client = TestClient(app)
    response = client.get("/events/")
    assert response.status_code == 200
