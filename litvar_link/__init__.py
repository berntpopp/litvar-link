"""LitVar-Link: High-performance MCP/API server for NCBI's LitVar2 genetic variant database."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("litvar-link")
except PackageNotFoundError:  # pragma: no cover - source checkout without install
    __version__ = "0.0.0"

__author__ = "LitVar-Link Development Team"
__email__ = "dev@litvar-link.org"
__description__ = "High-performance MCP/API server for NCBI's LitVar2 genetic variant database"

# Package level imports for convenience
from .exceptions import LitVarAPIError

__all__ = [
    "LitVarAPIError",
    "__author__",
    "__description__",
    "__email__",
    "__version__",
]
