#!/usr/bin/env python3
"""MCP server wrapper with proper environment setup for Claude Desktop."""

import os
import subprocess
import sys

def main():
    """Setup environment and launch MCP server."""
    # Set environment variables for clean STDIO operation
    env = os.environ.copy()
    env.update({
        "PYTHONUNBUFFERED": "1",      # Critical for STDIO communication
        "TRANSPORT": "stdio",         # Set transport mode
        "LOG_LEVEL": "WARNING",       # Reduce noise in STDIO mode
        "FASTMCP_QUIET": "1",         # Attempt to quiet FastMCP
        "FASTMCP_NO_BANNER": "1",     # Attempt to disable banner
    })
    
    # Execute the actual MCP server with clean environment
    script_path = os.path.join(os.path.dirname(__file__), "mcp_server.py")
    
    try:
        subprocess.run([sys.executable, script_path], env=env, check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except KeyboardInterrupt:
        sys.exit(0)

if __name__ == "__main__":
    main()