"""Run the local QuantOps MCP server over standard input/output."""

from .server import mcp


def main() -> None:
    """Run the deliberately local-only stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
