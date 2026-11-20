"""Custom exceptions for LitVar-Link."""

from typing import Any


class LitVarAPIError(Exception):
    """Base exception for LitVar2 API errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_data: dict[str, Any] | None = None,
    ) -> None:
        """Initialize LitVar API error.

        Args:
            message: Error message
            status_code: HTTP status code if applicable
            response_data: Raw response data if available
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_data = response_data or {}

    def __str__(self) -> str:
        """Return string representation of error."""
        if self.status_code:
            return f"LitVar2 API Error {self.status_code}: {self.message}"
        return f"LitVar2 API Error: {self.message}"


class ValidationError(LitVarAPIError):
    """Exception raised for input validation errors."""

    def __init__(self, message: str, field: str | None = None) -> None:
        """Initialize validation error.

        Args:
            message: Error message
            field: Field name that failed validation
        """
        super().__init__(message)
        self.field = field

    def __str__(self) -> str:
        """Return string representation of validation error."""
        return self.message


class VariantNotFoundError(ValidationError):
    """The input is well-formed but LitVar2 has no matching variant (maps to ``not_found``)."""

    def __init__(self, message: str, field: str | None = None) -> None:
        """Initialize with HTTP 404 so the MCP error mapping answers ``not_found``."""
        super().__init__(message, field=field)
        self.status_code = 404


class ForeignIdentifierError(ValidationError):
    """A well-formed identifier in a namespace the tool does not take (router #343).

    Maps to ``invalid_input`` and carries the fleet's structured recovery fields.
    ``message`` and ``hint`` are fixed, server-authored strings; ``next_commands``
    holds ready-to-send converter calls whose arguments are grammar-validated.
    """

    def __init__(
        self,
        message: str,
        *,
        field: str,
        allowed_values: list[str],
        hint: str,
        next_commands: list[dict[str, Any]],
    ) -> None:
        """Initialize with the structured recovery fields."""
        super().__init__(message, field=field)
        self.allowed_values = allowed_values
        self.hint = hint
        self.next_commands = next_commands


class RateLimitError(LitVarAPIError):
    """Exception raised when rate limit is exceeded."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        """Initialize rate limit error.

        Args:
            message: Error message
            retry_after: Seconds to wait before retrying
        """
        super().__init__(message, status_code=429)
        self.retry_after = retry_after


class ConfigurationError(LitVarAPIError):
    """Exception raised for configuration errors."""

    def __init__(self, message: str, config_key: str | None = None) -> None:
        """Initialize configuration error.

        Args:
            message: Error message
            config_key: Configuration key that caused the error
        """
        super().__init__(message)
        self.config_key = config_key


class CacheError(LitVarAPIError):
    """Exception raised for cache-related errors."""


class UpstreamPolicyError(LitVarAPIError):
    """A response/redirect violated an outbound URL/size policy (F-07).

    DETERMINISTIC and NON-RETRYABLE: a disallowed redirect (cross-host,
    http-downgrade, userinfo) or an oversized response body recurs identically
    on retry. It is a dedicated ``LitVarAPIError`` subclass so the MCP error
    mapping classifies it ``retryable=False`` -- unlike a bare, status-less
    ``LitVarAPIError``, which that mapping treats as a transient (retryable)
    upstream fault.

    The message MUST stay FIXED and host-free: the offending redirect host is
    caller-influenced and must never reach a log record or the caller response.
    """


class ServiceUnavailableError(LitVarAPIError):
    """Exception raised when the LitVar2 service is unavailable."""

    def __init__(
        self,
        message: str = "LitVar2 service is temporarily unavailable",
    ) -> None:
        """Initialize service unavailable error.

        Args:
            message: Error message
        """
        super().__init__(message, status_code=503)
