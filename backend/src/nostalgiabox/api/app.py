"""FastAPI application assembly."""

from fastapi import FastAPI

from nostalgiabox.api.routes.health import router as health_router
from nostalgiabox.api.routes.runtime import create_runtime_router
from nostalgiabox.application.runtime import RuntimeStateProvider
from nostalgiabox.config.logging import configure_logging
from nostalgiabox.config.settings import Settings


def create_app(
    settings: Settings | None = None,
    runtime_state_provider: RuntimeStateProvider | None = None,
) -> FastAPI:
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
    app.state.runtime_state_provider = runtime_state_provider
    app.include_router(health_router)
    app.include_router(create_runtime_router(runtime_state_provider))
    return app
