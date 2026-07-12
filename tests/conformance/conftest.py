"""LitVar binding for the vendored GeneFoundry HTTP-policy v1 suite."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable

import httpx
import pytest

from litvar_link.api.url_guard import (
    DisallowedURLError,
    ResponseTooLargeError,
    build_allowed_origins,
    make_response_cap,
    make_url_guard,
)


class _HttpPolicyAdapter:
    def __init__(self) -> None:
        self._guard = make_url_guard(build_allowed_origins("https://allowed.example/"))

    def allow(self, url: str) -> object:
        return asyncio.run(self._guard(httpx.Request("GET", url)))

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

            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler),
                follow_redirects=True,
                max_redirects=max_redirects,
                event_hooks={"request": [self._guard]},
            ) as client:
                try:
                    await client.get(url)
                except httpx.TooManyRedirects as exc:
                    raise DisallowedURLError() from exc

        asyncio.run(send())

    def read_decoded(self, chunks: Iterable[bytes], cap: int) -> None:
        async def read() -> None:
            response = httpx.Response(200, content=b"".join(chunks))
            await make_response_cap(cap)(response)

        asyncio.run(read())

    def is_non_retryable(self, error: Exception) -> bool:
        return isinstance(error, (DisallowedURLError, ResponseTooLargeError))

    def public_message(self, error: Exception) -> str:
        return str(error)


@pytest.fixture
def http_policy_adapter() -> _HttpPolicyAdapter:
    return _HttpPolicyAdapter()
