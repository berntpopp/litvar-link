"""Configuration management for LitVar-Link server."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServerSettings(BaseSettings):
    """Server configuration settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_prefix="LITVAR_LINK_",
    )

    # Server settings
    host: str = Field(default="127.0.0.1", description="Server host")
    port: int = Field(default=8000, ge=1024, le=65535, description="Server port")
    reload: bool = Field(default=False, description="Enable auto-reload in development")

    # Transport modes
    transport_mode: Literal["stdio", "http", "unified"] = Field(
        default="unified",
        description="Server transport mode",
    )

    # MCP settings
    mcp_path: str = Field(default="/mcp", description="MCP endpoint path")

    # CORS settings
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        description="Allowed CORS origins",
    )
    cors_allow_credentials: bool = Field(
        default=True,
        description="Allow CORS credentials",
    )
    cors_allow_methods: list[str] = Field(
        default=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        description="Allowed CORS methods",
    )
    cors_allow_headers: list[str] = Field(
        default=["*"],
        description="Allowed CORS headers",
    )

    # Logging settings
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level",
    )
    log_format: Literal["json", "console"] = Field(
        default="console",
        description="Log format",
    )
    log_show_caller: bool = Field(default=False, description="Show caller info in logs")
    
    # Transport mode
    transport: Literal["unified", "http", "stdio"] = Field(
        default="unified",
        description="Transport mode for server",
    )

    @field_validator("mcp_path")
    @classmethod
    def validate_mcp_path(cls, v: str) -> str:
        """Ensure MCP path starts with forward slash."""
        if not v.startswith("/"):
            return f"/{v}"
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


@dataclass
class APIConfig:
    """LitVar2 API configuration."""

    base_url: str
    timeout: int
    rate_limit_per_second: float
    burst_size: int = 1
    max_retries: int = 3
    retry_delay: float = 1.0
    user_agent: str = "LitVar-Link/0.1.0"

    # API endpoints
    endpoints: dict[str, str] = field(
        default_factory=lambda: {
            "autocomplete": "variant/autocomplete/",
            "variant_details": "variant/get/{variant_id}",
            "variant_publications": "variant/get/{variant_id}/publications",
            "sensor": "sensor/{rsid}",
            "gene_variants": "variant/search/gene/{gene_name}",
        },
    )


@dataclass
class CacheConfig:
    """Cache configuration."""

    size: int = 1000
    ttl: int = 3600  # 1 hour
    stats_enabled: bool = True
    cleanup_interval: int = 300  # 5 minutes


# Default configurations
DEFAULT_API_CONFIG = APIConfig(
    base_url="https://www.ncbi.nlm.nih.gov/research/litvar2-api/",
    timeout=30,
    rate_limit_per_second=2.0,  # Conservative rate limiting
    burst_size=5,
    max_retries=3,
    retry_delay=1.0,
)

DEFAULT_CACHE_CONFIG = CacheConfig(
    size=1000,
    ttl=3600,
    stats_enabled=True,
    cleanup_interval=300,
)

# Global settings instance
settings = ServerSettings()


# Configuration factory
def get_api_config() -> APIConfig:
    """Get API configuration."""
    return DEFAULT_API_CONFIG


def get_cache_config() -> CacheConfig:
    """Get cache configuration."""
    return DEFAULT_CACHE_CONFIG
