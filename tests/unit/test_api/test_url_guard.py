"""Adversarial tests for the outbound URL guard + response byte cap (F-07).

The LitVar2 client follows redirects (``follow_redirects=True``). Without a guard
an upstream (or a MITM) 3xx can send the client to an attacker-controlled host,
downgrade to plaintext, or smuggle credentials via ``user:pass@`` userinfo; an
unbounded body can also exhaust memory. These tests prove every hop is validated
(scheme/host/userinfo/method) and the body is capped fail-closed, and that a guard
violation is NOT retried by the client's retry loop.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from litvar_link.api.client import LitVar2Client
from litvar_link.api.url_guard import (
    DisallowedURLError,
    ResponseTooLargeError,
    build_host_allowlist,
    make_response_cap,
    make_url_guard,
)
from litvar_link.config import APIConfig
from litvar_link.exceptions import LitVarAPIError

_ALLOWED = frozenset({"www.ncbi.nlm.nih.gov"})
_BASE = "https://www.ncbi.nlm.nih.gov"


async def _agen(chunk: bytes, times: int):
    for _ in range(times):
        yield chunk


def _client(handler, *, max_bytes: int = 25 * 1024 * 1024) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        follow_redirects=True,
        max_redirects=5,
        event_hooks={
            "request": [make_url_guard(_ALLOWED)],
            "response": [make_response_cap(max_bytes)],
        },
    )


# --------------------------------------------------------------------------- #
# build_host_allowlist                                                          #
# --------------------------------------------------------------------------- #


def test_build_host_allowlist_derives_from_base_url() -> None:
    allowed = build_host_allowlist("https://www.ncbi.nlm.nih.gov/research/litvar2-api/")
    assert allowed == frozenset({"www.ncbi.nlm.nih.gov"})


def test_build_host_allowlist_lowercases_and_dedupes() -> None:
    allowed = build_host_allowlist(
        "https://Www.NCBI.nlm.nih.GOV/x", "https://www.ncbi.nlm.nih.gov/y"
    )
    assert allowed == frozenset({"www.ncbi.nlm.nih.gov"})


def test_build_host_allowlist_skips_hostless_urls() -> None:
    assert build_host_allowlist("not-a-url", "") == frozenset()


# --------------------------------------------------------------------------- #
# request guard adversarial hops                                               #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_cross_host_redirect_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "https://evil.example.com/steal"})

    async with _client(handler) as client:
        with pytest.raises(DisallowedURLError):
            await client.request("GET", _BASE + "/x")


@pytest.mark.asyncio
async def test_non_https_redirect_downgrade_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "http://www.ncbi.nlm.nih.gov/x"})

    async with _client(handler) as client:
        with pytest.raises(DisallowedURLError):
            await client.request("GET", _BASE + "/x")


@pytest.mark.asyncio
async def test_userinfo_in_url_raises() -> None:
    async with _client(lambda r: httpx.Response(200, json={})) as client:
        with pytest.raises(DisallowedURLError):
            await client.request("GET", "https://user:pass@www.ncbi.nlm.nih.gov/x")


@pytest.mark.asyncio
async def test_non_get_method_raises() -> None:
    async with _client(lambda r: httpx.Response(200, json={})) as client:
        with pytest.raises(DisallowedURLError):
            await client.request("POST", _BASE + "/x")


@pytest.mark.asyncio
async def test_redirect_loop_bounded_by_max_redirects() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": _BASE + "/loop"})

    async with _client(handler) as client:
        with pytest.raises(httpx.TooManyRedirects):
            await client.request("GET", _BASE + "/loop")


# --------------------------------------------------------------------------- #
# response byte cap                                                            #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_over_cap_content_length_fast_path_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"Content-Length": "999999"}, content=b"x")

    async with _client(handler, max_bytes=1000) as client:
        with pytest.raises(ResponseTooLargeError):
            await client.request("GET", _BASE + "/big")


@pytest.mark.asyncio
async def test_over_cap_streamed_no_content_length_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # Chunked async body → no Content-Length, forces streamed enforcement.
        return httpx.Response(200, content=_agen(b"y" * 100, 50))

    async with _client(handler, max_bytes=1000) as client:
        with pytest.raises(ResponseTooLargeError):
            await client.request("GET", _BASE + "/stream")


@pytest.mark.asyncio
async def test_happy_path_unchanged() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": [{"_id": "ok"}]})

    async with _client(handler) as client:
        resp = await client.request("GET", _BASE + "/ok")
        assert resp.json() == {"results": [{"_id": "ok"}]}
        assert resp.text  # body materialized despite the streamed cap


@pytest.mark.asyncio
async def test_same_host_https_redirect_is_followed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/redir":
            return httpx.Response(302, headers={"Location": _BASE + "/ok"})
        return httpx.Response(200, json={"ok": True})

    async with _client(handler) as client:
        resp = await client.request("GET", _BASE + "/redir")
        assert resp.json() == {"ok": True}


# --------------------------------------------------------------------------- #
# guard exceptions are non-retryable in the client's retry loop                #
# --------------------------------------------------------------------------- #


@pytest.fixture
def api_config() -> APIConfig:
    return APIConfig(
        base_url="https://www.ncbi.nlm.nih.gov/research/litvar2-api/",
        timeout=10,
        rate_limit_per_second=10.0,
        burst_size=5,
        max_retries=2,
        retry_delay=0.1,
    )


def test_guard_exceptions_are_litvar_api_errors() -> None:
    # Subclassing LitVarAPIError is what makes them fall into the fail-fast
    # `except (LitVarAPIError, ...)` branch instead of the retried broad Exception.
    assert issubclass(DisallowedURLError, LitVarAPIError)
    assert issubclass(ResponseTooLargeError, LitVarAPIError)


@pytest.mark.asyncio
async def test_disallowed_url_error_is_not_retried(api_config: APIConfig) -> None:
    async with LitVar2Client(config=api_config) as client:
        with (
            patch.object(
                client.client,
                "request",
                AsyncMock(side_effect=DisallowedURLError("host not allowlisted")),
            ) as mock_request,
            pytest.raises(DisallowedURLError),
        ):
            await client.search_variants("test")
        assert mock_request.call_count == 1  # fail-fast, no retries


@pytest.mark.asyncio
async def test_response_too_large_error_is_not_retried(api_config: APIConfig) -> None:
    async with LitVar2Client(config=api_config) as client:
        with (
            patch.object(
                client.client,
                "request",
                AsyncMock(side_effect=ResponseTooLargeError("too big")),
            ) as mock_request,
            pytest.raises(ResponseTooLargeError),
        ):
            await client.search_variants("test")
        assert mock_request.call_count == 1


# --------------------------------------------------------------------------- #
# LitVar2Client wires the guard + cap into its httpx client                    #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_client_wires_guard_cap_and_max_redirects(api_config: APIConfig) -> None:
    async with LitVar2Client(config=api_config) as client:
        hooks = client.client.event_hooks
        assert hooks["request"], "request guard hook must be wired"
        assert hooks["response"], "response cap hook must be wired"
        assert client.client.max_redirects == 5


def test_default_config_response_cap_is_generous() -> None:
    # ~25 MB default: large genes (BRCA1/TP53) return a few MB — must NOT cap low.
    assert APIConfig().max_response_bytes >= 25 * 1024 * 1024


# --------------------------------------------------------------------------- #
# end-to-end: hooks actually fire through the production LitVar2Client          #
# (respx replaces only the transport, so httpx still runs the event hooks)      #
# --------------------------------------------------------------------------- #

_AUTOCOMPLETE = "https://www.ncbi.nlm.nih.gov/research/litvar2-api/variant/autocomplete/"


@pytest.mark.asyncio
@respx.mock
async def test_end_to_end_happy_path_through_client(api_config: APIConfig) -> None:
    respx.get(_AUTOCOMPLETE).mock(
        return_value=httpx.Response(200, json=[{"_id": "litvar@rs1##", "rsid": "rs1"}]),
    )
    async with LitVar2Client(config=api_config) as client:
        result = await client.search_variants("CFH")
    assert result == [{"_id": "litvar@rs1##", "rsid": "rs1"}]


@pytest.mark.asyncio
@respx.mock
async def test_end_to_end_cross_host_redirect_blocked_and_not_retried(
    api_config: APIConfig,
) -> None:
    route = respx.get(_AUTOCOMPLETE).mock(
        return_value=httpx.Response(302, headers={"Location": "https://evil.example.com/x"}),
    )
    async with LitVar2Client(config=api_config) as client:
        with pytest.raises(DisallowedURLError):
            await client.search_variants("CFH")
    assert route.call_count == 1  # blocked on the first hop, never retried
