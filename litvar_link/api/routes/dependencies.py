"""Dependency injection for FastAPI routes."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from structlog.typing import FilteringBoundLogger

from litvar_link.api.client import LitVar2Client
from litvar_link.config import get_api_config, get_cache_config
from litvar_link.logging_config import configure_logging
from litvar_link.services.variant_service import VariantService


def get_logger() -> FilteringBoundLogger:
    """Get configured logger instance."""
    return configure_logging()


async def get_litvar_client(
    logger: Annotated[FilteringBoundLogger, Depends(get_logger)],
) -> AsyncGenerator[LitVar2Client, None]:
    """Get LitVar2 API client instance."""
    config = get_api_config()
    client = LitVar2Client(config=config, logger=logger)

    try:
        yield client
    finally:
        await client.close()


def get_variant_service(
    client: Annotated[LitVar2Client, Depends(get_litvar_client)],
    logger: Annotated[FilteringBoundLogger, Depends(get_logger)],
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
