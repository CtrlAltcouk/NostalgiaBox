"""FastAPI application assembly."""

from fastapi import FastAPI

from nostalgiabox.api.routes.health import router as health_router
from nostalgiabox.config.logging import configure_logging
from nostalgiabox.config.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build a configured API application without starting infrastructure."""
    resolved_settings = settings or Settings()
    configure_logging(resolved_settings.log_level)

    app = FastAPI(
        title="NostalgiaBox Core API",
        version="0.1.0",
        docs_url="/docs" if resolved_settings.environment == "development" else None,
        redoc_url=None,
    )
    app.state.settings = resolved_settings
    app.include_router(health_router)
    return app
