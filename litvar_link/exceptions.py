"""Custom exceptions for LitVar-Link."""

from typing import Any, Optional


class LitVarAPIError(Exception):
    """Base exception for LitVar2 API errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_data: Optional[dict[str, Any]] = None,
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

    def __init__(self, message: str, field: Optional[str] = None) -> None:
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


class RateLimitError(LitVarAPIError):
    """Exception raised when rate limit is exceeded."""

    def __init__(self, message: str, retry_after: Optional[float] = None) -> None:
        """Initialize rate limit error.

        Args:
            message: Error message
            retry_after: Seconds to wait before retrying
        """
        super().__init__(message, status_code=429)
        self.retry_after = retry_after


class ConfigurationError(LitVarAPIError):
    """Exception raised for configuration errors."""

    def __init__(self, message: str, config_key: Optional[str] = None) -> None:
        """Initialize configuration error.

        Args:
            message: Error message
            config_key: Configuration key that caused the error
        """
        super().__init__(message)
        self.config_key = config_key


class CacheError(LitVarAPIError):
    """Exception raised for cache-related errors."""


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
