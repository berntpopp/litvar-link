"""Dependency injection for FastAPI routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from structlog.typing import FilteringBoundLogger

from ...api.client import LitVar2Client
from ...config import get_api_config, get_cache_config
from ...logging_config import configure_logging
from ...services.variant_service import VariantService


def get_logger() -> FilteringBoundLogger:
    """Get configured logger instance."""
    return configure_logging()


async def get_litvar_client(
    logger: LoggerDep,
) -> LitVar2Client:
    """Get LitVar2 API client instance."""
    config = get_api_config()
    client = LitVar2Client(config=config, logger=logger)

    try:
        yield client
    finally:
        await client.close()


def get_variant_service(
    client: ClientDep,
    logger: LoggerDep,
) -> VariantService:
    """Get variant service instance."""
    cache_config = get_cache_config()
    return VariantService(
        client=client,
        cache_config=cache_config,
        logger=logger,
    )


# Type aliases for clean dependency injection
LoggerDep = Annotated[FilteringBoundLogger, Depends(get_logger)]
ClientDep = Annotated[LitVar2Client, Depends(get_litvar_client)]
ServiceDep = Annotated[VariantService, Depends(get_variant_service)]
