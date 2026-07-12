"""LitVar binding for the vendored GeneFoundry HTTP-policy v1 suite."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable

import httpx
import pytest

from litvar_link.api.client import LitVar2Client
from litvar_link.api.url_guard import (
    DisallowedURLError,
    ResponseTooLargeError,
)
from litvar_link.config import APIConfig


class _HttpPolicyAdapter:
    async def _production_session(self) -> tuple[httpx.AsyncClient, object]:
        client = LitVar2Client(APIConfig(base_url="https://allowed.example/"))
        return client.client, client.close

    def allow(self, url: str) -> object:
        async def check() -> None:
            session, close = await self._production_session()
            try:
                await session.event_hooks["request"][0](httpx.Request("GET", url))
            finally:
                await close()

        return asyncio.run(check())

    def request(self, url: str, redirects: list[str], max_redirects: int) -> None:
        async def send() -> None:
            index = 0

            def handler(_: httpx.Request) -> httpx.Response:
                nonlocal index
                if index < len(redirects):
                    location = redirects[index]
                    index += 1
                    return httpx.Response(302, headers={"Location": location})
                return httpx.Response(200, json={})

            session, close = await self._production_session()
            try:
                if not session.follow_redirects or session.max_redirects != max_redirects:
                    raise DisallowedURLError()
                session._transport = httpx.MockTransport(handler)
                try:
                    await session.get(url)
                except httpx.TooManyRedirects as exc:
                    raise DisallowedURLError() from exc
            finally:
                await close()

        asyncio.run(send())

    def read_decoded(self, chunks: Iterable[bytes], cap: int) -> None:
        async def read() -> None:
            client = LitVar2Client(
                APIConfig(base_url="https://allowed.example/", max_response_bytes=cap)
            )
            response = httpx.Response(200, content=b"".join(chunks))
            try:
                await client.client.event_hooks["response"][0](response)
            finally:
                await client.close()

        asyncio.run(read())

    def is_non_retryable(self, error: Exception) -> bool:
        return isinstance(error, (DisallowedURLError, ResponseTooLargeError))

    def public_message(self, error: Exception) -> str:
        return str(error)


@pytest.fixture
def http_policy_adapter() -> _HttpPolicyAdapter:
    return _HttpPolicyAdapter()
