"""Explicit FastMCP facade for LitVar-Link.

The ``create_litvar_mcp`` re-export is added in task 3.5.5 once ``facade`` exists;
keeping this module free of eager submodule imports lets the errors/shaping/
capabilities modules be imported independently in the intervening tasks.
"""
