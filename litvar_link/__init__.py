"""LitVar-Link: High-performance MCP/API server for NCBI's LitVar2 genetic variant database."""

__version__ = "2.0.0"
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
