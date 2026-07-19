"""Read-only Model Context Protocol adapter for QuantOps."""

from .server import create_server, mcp

__all__ = ["create_server", "mcp"]

__version__ = "0.1.0"
