"""Entry point for IBM Bob's project-scoped stdio MCP server."""

from codetwin.bob_mcp import mcp


if __name__ == "__main__":
    mcp.run(transport="stdio")
