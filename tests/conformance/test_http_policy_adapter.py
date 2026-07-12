"""Tests for the LitVar binding of the canonical HTTP-policy suite."""

from __future__ import annotations

import asyncio

from tests.conformance.conftest import _HttpPolicyAdapter


def test_adapter_uses_production_client_session() -> None:
    async def verify() -> None:
        adapter = _HttpPolicyAdapter()
        session, close = await adapter._production_session()
        try:
            assert session.follow_redirects is True
            assert session.max_redirects == 5
            assert session.event_hooks["request"]
        finally:
            await close()

    asyncio.run(verify())
