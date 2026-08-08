"""API application smoke tests."""

from fastapi.testclient import TestClient

from nostalgiabox.api import create_app
from nostalgiabox.config.settings import Settings


def test_application_factory_creates_expected_routes() -> None:
    settings = Settings(environment="test", database_url="sqlite+pysqlite:///:memory:")
    app = create_app(settings)

    assert app.title == "NostalgiaBox Core API"
    assert app.state.settings is settings


def test_health_endpoint_returns_stable_response() -> None:
    app = create_app(Settings(environment="test", database_url="sqlite+pysqlite:///:memory:"))

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"service": "nostalgiabox", "status": "ok"}
