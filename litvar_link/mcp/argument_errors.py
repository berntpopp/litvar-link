"""Actionable `invalid_input` envelopes for argument-validation failures.

A bad argument is a bad ARGUMENT. Answering it with `not_found` / "The requested
tool is not available" tells the model the TOOL does not exist, so it strikes the
tool from its list and never calls it again -- from a typo. That is the single
most destructive thing a server can say to an agent, and litvar-link said it on
all six tools for every argument error (issue #66 D4).

MCP 2025-11-25 (SEP-1303) moved input-validation failures out of protocol errors
and into tool-execution errors precisely so a model can recover: *"Tool Execution
Errors contain actionable feedback that language models can use to self-correct
and retry with adjusted parameters."* This module builds that feedback.

THE SAFETY CONSTRAINT, AND WHY IT SHAPES THE MESSAGE
----------------------------------------------------
"Actionable" must not become "reflect the caller's payload back at them". The
fleet's error-sanitation sweep established that stripping forbidden code points
does NOT neutralize instruction-shaped prose, so a caller-visible structured
field must be built only from **fixed strings, closed enums, or grammar-validated
identifiers** (Response-Envelope v1.1).

So this module NEVER echoes a caller-supplied VALUE. It reports:

* the tool's OWN parameter names and enum values -- fixed strings from our schema;
* a rejected argument NAME, and only when it matches :data:`SAFE_IDENTIFIER`
  (ASCII letters/digits/underscore, <=64 chars). That grammar cannot express a
  control/zero-width/bidi/NUL code point, cannot contain whitespace or
  punctuation, and is length-capped -- so it cannot carry an injection payload.
  It is exactly the "grammar-validated identifier" carve-out.

Echoing the name matters: a zero-argument tool (`get_server_capabilities`) has no
parameters of its own to name, so naming the *rejected* argument is the only way
its error can be actionable at all.
"""

from __future__ import annotations

import re
from typing import Any

from fastmcp.tools.tool import ToolResult
from pydantic import ValidationError as PydanticValidationError

from litvar_link.mcp.envelope import error_envelope

#: A rejected argument NAME may be echoed only if it matches this grammar.
#: ASCII identifier characters only -- no code points to strip, no prose to inject.
SAFE_IDENTIFIER = re.compile(r"\A[A-Za-z_][A-Za-z0-9_]{0,63}\Z")

#: Bound the message: never let a caller inflate it by sending 500 bogus arguments.
_MAX_NAMES = 8
_OMITTED = "(name omitted: not a valid identifier)"

_RECOVERY = (
    "Fix the named argument(s) and retry. The tool EXISTS -- this is an argument "
    "error, not a missing tool. Call get_server_capabilities for the full schema."
)

# pydantic error types that mean "you passed an argument that is not in the schema".
_UNEXPECTED_TYPES = frozenset({"unexpected_keyword_argument", "extra_forbidden"})
_MISSING_TYPES = frozenset({"missing", "missing_argument"})


def _safe_name(name: str) -> str:
    """Echo an argument name only if it passes the identifier grammar."""
    return name if SAFE_IDENTIFIER.match(name) else _OMITTED


def _dedupe(names: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for name in names:
        seen.setdefault(name, None)
    return list(seen)[:_MAX_NAMES]


def _enum_of(prop: dict[str, Any]) -> list[Any] | None:
    """The declared enum, whether it sits on the property or inside an anyOf branch."""
    values = prop.get("enum")
    if isinstance(values, list):
        return values
    for branch in prop.get("anyOf") or []:
        if isinstance(branch, dict) and isinstance(branch.get("enum"), list):
            return list(branch["enum"])
    return None


def _expected(prop: dict[str, Any]) -> str:
    """Describe what a property WILL accept, using ONLY our own schema.

    Report the tightest constraint we declared, not merely the JSON type: telling
    a model that `variant_id` "must be of type string" when it already sent a
    string is a non-answer. It needs the enum, the pattern, or the bounds.
    """
    values = _enum_of(prop)
    if values:
        return "must be one of: " + ", ".join(str(v) for v in values[:_MAX_NAMES])

    pattern = prop.get("pattern")
    if isinstance(pattern, str):
        return f"must match the pattern {pattern}"

    low, high = prop.get("minimum"), prop.get("maximum")
    if isinstance(low, int | float) and isinstance(high, int | float):
        return f"must be between {low} and {high}"
    if isinstance(low, int | float):
        return f"must be >= {low}"
    if isinstance(high, int | float):
        return f"must be <= {high}"

    max_len = prop.get("maxLength")
    if isinstance(max_len, int):
        return f"must be at most {max_len} characters"

    declared = prop.get("type")
    if isinstance(declared, str):
        return f"must be of type {declared}"
    return "is invalid"


def _pydantic_errors(exc: Exception) -> list[Any]:
    """Walk __cause__ for the pydantic error carrying the structured details."""
    seen = 0
    current: BaseException | None = exc
    while current is not None and seen < 5:
        if isinstance(current, PydanticValidationError):
            return list(current.errors())
        current = current.__cause__
        seen += 1
    return []


def describe_argument_error(tool_name: str, schema: dict[str, Any], exc: Exception) -> str:
    """Build the caller-visible message. Contains NO caller-supplied value."""
    properties: dict[str, Any] = dict(schema.get("properties") or {})
    missing: list[str] = []
    unexpected: list[str] = []
    invalid: list[str] = []

    for error in _pydantic_errors(exc):
        location = error.get("loc") or ()
        name = str(location[0]) if location else ""
        kind = str(error.get("type") or "")
        if not name:
            continue
        if kind in _MISSING_TYPES:
            # The name is one of OUR required parameters: a fixed string.
            missing.append(name)
        elif kind in _UNEXPECTED_TYPES or name not in properties:
            # CALLER-SUPPLIED name -- grammar-gated before it is echoed.
            unexpected.append(_safe_name(name))
        else:
            invalid.append(f"{name} {_expected(properties[name])}")

    parts: list[str] = []
    if missing:
        parts.append("missing required argument(s): " + ", ".join(_dedupe(missing)))
    if unexpected:
        parts.append("unexpected argument(s): " + ", ".join(_dedupe(unexpected)))
    if invalid:
        parts.append("; ".join(_dedupe(invalid)))
    if not parts:
        parts.append("one or more arguments are invalid")

    valid = ", ".join(sorted(properties)) if properties else "(this tool takes no arguments)"
    return f"Invalid arguments for {tool_name}: {'; '.join(parts)}. Valid arguments: {valid}."


def argument_error_envelope(
    tool_name: str,
    schema: dict[str, Any],
    exc: Exception,
    *,
    request_id: str,
) -> dict[str, Any]:
    """The flat `invalid_input` frame for an argument-validation failure."""
    return error_envelope(
        tool_name=tool_name,
        request_id=request_id,
        elapsed_ms=0,
        error_code="invalid_input",
        message=describe_argument_error(tool_name, schema, exc),
        retryable=False,
        recovery_action=_RECOVERY,
    )


def argument_error_result(
    tool_name: str,
    schema: dict[str, Any],
    exc: Exception,
    *,
    request_id: str,
) -> ToolResult:
    """`ToolResult` carrying the `invalid_input` envelope with wire `isError: true`.

    `is_error=True` is required by Response-Envelope v1 so the client surfaces the
    failure to the model for self-correction -- which is the entire point here.
    """
    return ToolResult(
        structured_content=argument_error_envelope(tool_name, schema, exc, request_id=request_id),
        is_error=True,
    )
