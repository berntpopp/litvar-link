"""Shared MCP ``ToolAnnotations`` for LitVar-Link (F-12).

Every LitVar-Link tool is a read-only lookup: it never mutates upstream state,
is safe to repeat, and performs only additive work. Advertising that explicitly
lets hosts avoid treating a lookup as a mutating/destructive call and lets the
router's drift baseline capture a complete fingerprint.

``openWorldHint`` is the only axis that varies: the five LitVar2-backed tools
reach an external API (open world); ``get_server_capabilities`` is static/local
(closed world).
"""

from __future__ import annotations

from mcp.types import ToolAnnotations


def read_only_annotations(*, open_world: bool = True) -> ToolAnnotations:
    """Return a complete read-only / non-destructive / idempotent annotation."""
    return ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=open_world,
    )


# The common case: a LitVar2-backed read-only lookup against the external API.
READ_ONLY_OPEN_WORLD = read_only_annotations(open_world=True)

# A static, local-only discovery tool (no external I/O).
READ_ONLY_CLOSED_WORLD = read_only_annotations(open_world=False)
