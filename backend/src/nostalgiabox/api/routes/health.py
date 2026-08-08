"""Service liveness endpoint."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["service"])


class HealthResponse(BaseModel):
    """Stable, non-sensitive liveness response."""

    service: Literal["nostalgiabox"] = "nostalgiabox"
    status: Literal["ok"] = "ok"


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Report that the core HTTP service is alive."""
    return HealthResponse()
