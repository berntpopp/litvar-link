"""App-level exception handlers (DRY cluster #3).

Replaces the identical try/except in all five route handlers with a single
mapping: ValidationError -> 400, LitVarAPIError -> 502, Exception -> 500.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request
from fastapi.responses import JSONResponse

from litvar_link.exceptions import LitVarAPIError, ValidationError
from litvar_link.logging_config import configure_logging

if TYPE_CHECKING:
    from fastapi import FastAPI


async def _validation_handler(_request: Request, exc: Exception) -> JSONResponse:
    configure_logging().warning("Validation error", error=str(exc))
    return JSONResponse(status_code=400, content={"detail": str(exc)})


async def _api_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    configure_logging().exception("LitVar2 API error", error=str(exc))
    return JSONResponse(status_code=502, content={"detail": "LitVar2 API error"})


async def _unexpected_handler(_request: Request, exc: Exception) -> JSONResponse:
    configure_logging().error("Unexpected error", error=str(exc), exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


def register_exception_handlers(app: FastAPI) -> None:
    """Register the domain exception handlers on a FastAPI app."""
    app.add_exception_handler(ValidationError, _validation_handler)
    app.add_exception_handler(LitVarAPIError, _api_error_handler)
    app.add_exception_handler(Exception, _unexpected_handler)
