"""Response parsing + shape normalization for the LitVar2 API (DRY cluster #4).

LitVar2 sometimes returns NDJSON, sometimes Python-style single-quoted dicts,
and list-vs-dict-wrapped payloads. This module centralizes all of that so the
client stays a thin orchestrator.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from structlog.typing import FilteringBoundLogger

_LOG_LINE_PREVIEW = 100


def parse_ndjson(
    text: str,
    logger: FilteringBoundLogger | None = None,
) -> list[dict[str, Any]]:
    """Parse newline-delimited JSON, tolerating single-quoted Python dicts.

    Each line is tried as strict JSON first; on failure single quotes are
    swapped for double quotes (the LitVar2 quirk) and retried. Unparseable
    lines are skipped (logged at WARNING when a logger is supplied).
    """
    results: list[dict[str, Any]] = []
    for raw_line in text.strip().split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        try:
            results.append(json.loads(line))
        except json.JSONDecodeError:
            try:
                results.append(json.loads(line.replace("'", '"')))
            except json.JSONDecodeError as exc:
                if logger:
                    logger.warning(
                        "Failed to parse NDJSON line",
                        line=line[:_LOG_LINE_PREVIEW],
                        error=str(exc),
                    )
                continue
    return results


def parse_response_body(
    *,
    content_type: str,
    response_text: str,
    json_loader: Any,
    logger: FilteringBoundLogger | None = None,
) -> Any:
    """Parse an HTTP body as a single JSON object, NDJSON, or raw text.

    ``json_loader`` is ``response.json`` (httpx) so we reuse its decoder for the
    happy path, falling back to NDJSON when the body is newline-delimited.
    """
    text = response_text.strip()
    looks_json = "application/json" in content_type or (text and text.startswith("{"))
    if looks_json:
        try:
            return json_loader()
        except (ValueError, json.JSONDecodeError):
            if "\n" in text:
                return parse_ndjson(text, logger)
            raise
    return {"content": text, "content_type": content_type}


def extract_list(response: Any, *, key: str) -> list[Any]:
    """Normalize a list-or-dict-wrapped payload into a plain list.

    Returns ``response`` if it is already a list, ``response[key]`` if it is a
    dict carrying that key, otherwise an empty list.
    """
    if isinstance(response, list):
        return response
    if isinstance(response, dict) and key in response:
        return cast("list[Any]", response[key])
    return []
