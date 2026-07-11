# Changelog

All notable changes to litvar-link are documented in this file. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [5.0.0] - 2026-07-11

Adopts **Response-Envelope Standard v1.1 untrusted-content fencing**
(`genefoundry-router` `docs/RESPONSE-ENVELOPE-STANDARD-v1.1.md`). Defense in
depth: upstream free text is now typed as data at the MCP boundary so hosts
never confuse retrieved content with instructions. Research use only; not
clinical decision support.

### BREAKING

- **`search_genetic_variants` full-mode `/results/*/match` is now a typed
  `untrusted_text` object**, not a bare string. LitVar2's autocomplete
  `match` field carries an HTML-highlighted search snippet built from
  upstream free text (`AutocompleteVariantItem.match`,
  `litvar_link/models/endpoint_specific.py:55`); it was previously passed
  through unfenced in `response_mode="full"` (`existing_sanitization:
  compact allowlist drops it; full-mode HTML snippet unstripped`). Every
  populated `match` is now normalized (NFC), stripped of control/zero-width/
  bidi-override code points, and wrapped as `{kind: "untrusted_text", text,
  provenance: {source, record_id, retrieved_at}, raw_sha256}` via the new
  `litvar_link/mcp/untrusted_content.py` (copied verbatim from the released
  PubTator reference fence). `provenance.source` is `"litvar"`;
  `provenance.record_id` is the LitVar variant id (`_id`/`id`, falling back
  to `rsid`). `raw_sha256` is the SHA-256 of the pre-normalization raw UTF-8
  bytes. The fence does **not** strip HTML markup -- that is a presentation
  concern, not a security boundary; only control/zero-width/bidi code
  points are removed. `response_mode="compact"` is unaffected -- it already
  dropped `match` and continues to.
- **`get_variant_summary` full-mode `/result/match` is now fenced the same
  way** (a missed-surface fix beyond the original inventory pointer):
  `VariantDetails` (the model this tool actually returns; `record.match`
  reaches it via inheritance from `Variant`,
  `litvar_link/models/variants.py:98`) permits the same upstream `match`
  field, even though the "variant details" endpoint does not normally
  populate it. Fenced defensively so an unexpected non-null value can never
  pass through unfenced.
- **`kind` is now declared in the array-ITEM output schema**, not only
  advertised structurally: `search_genetic_variants`'s `output_schema`
  documents `results[].match` as the `untrusted_text` object (`kind` const)
  via a new `SEARCH_GENETIC_VARIANTS_OUTPUT_SCHEMA`; `get_variant_summary`
  documents `result.match` likewise. `additionalProperties: true` is
  preserved throughout so `full` mode's raw-upstream-passthrough contract for
  every other field is unaffected.
- A response-level object-count ceiling is now enforced by aggregating
  **every** fenced object across the **whole** response (not per-record)
  into one `enforce_untrusted_text_limits` call:
  `search_genetic_variants` passes `max_objects=100` (its own `limit`
  maximum, not the generic 128 default); `get_variant_summary` uses the
  128 default (single-record tool). Exceeding either ceiling raises a typed
  `UntrustedTextLimitError`, per the standard's explicit-error requirement --
  expected to never fire in practice since `apply_limit` already truncates
  `search_genetic_variants` output to 100 rows before this check runs.
- **New closed `error_code` value `response_limit_exceeded`** (in addition to
  the existing `invalid_input` / `not_found` / `ambiguous_query` /
  `upstream_unavailable` / `rate_limited` / `internal` set): a
  `UntrustedTextLimitError` reaching the MCP boundary is now classified to
  this typed, non-masked code (verbatim diagnostic message, e.g. `untrusted
  object count N exceeds ceiling M`) instead of the generic, masked
  `internal` code.

## [4.0.0] - 2026-07-10

### Security

- Enforce exact configurable Host and Origin allowlists across every HTTP
  route, with safe loopback defaults, wildcard rejection, explicit production
  proxy hosts and browser origins, and native FastMCP protection in depth.
  FastMCP is upgraded to 3.4.4.

### Changed (BREAKING)

- Host and Origin admission is now default-deny outside the configured
  loopback values. Non-loopback and reverse-proxy deployments must list their
  exact public names in `LITVAR_LINK_ALLOWED_HOSTS`; browser deployments must
  couple `LITVAR_LINK_ALLOWED_ORIGINS` with the matching CORS origins.

## [3.0.3] - 2026-07-07

Release-merge of the 3.0.2 security hardening (see below) with the consolidated
Dependabot dependency sweep. Supersedes the two colliding 3.0.2 tags.

### Changed

- **Dependency bumps (Dependabot #46).** `fastapi>=0.139.0`, `uvicorn[standard]>=0.50.0`,
  `fastmcp>=3.4.3`, `typer>=0.26.8`, and `ruff>=0.15.20` (dev). Lockfile regenerated.
- **Ignore local docker secrets.** `.env.docker` (production secrets) is now
  git-ignored; the tracked `.env.docker.example` is unaffected.

## [3.0.2] - 2026-07-07

Inbound-boundary security hardening. The backend is unauthenticated by design
and reachable only through the router / reverse proxy; these changes remove
identifier leakage into logs and close two default-open network/CORS footguns.

### Security

- **No PII in logs (M3).** Route handlers and the shared logging helpers no
  longer emit variant/rsid/gene/query identifiers. `log_api_request` logs the
  upstream host only (never the identifier-bearing URL path); `log_mcp_tool_call`
  logs sorted param *key names* only; `log_error_with_context` logs the
  exception *type* and context *key names* only.
- **Cache logs.** Cache-operation logs now record the cache *namespace* only
  (`search_variants`, `variant_details`, …) instead of a key built from the raw
  call arguments (which embedded rsIDs/HGVS/queries).
- **Traceback leak.** `log_error_with_context` no longer passes `exc_info=True`;
  the production JSON renderer expanded it into a traceback whose `exc_value`
  re-embedded the exception message (e.g. `No LitVar2 variant found for
  '<rsid>'`), defeating the field-level redaction.
- **CORS credentials off by default.** `cors_allow_credentials` now defaults to
  `False` (this backend has no cookies/session). Startup fails closed if an
  operator pairs `cors_allow_credentials=True` with a wildcard `*` origin.
- **Loopback-bound dev compose.** `docker/docker-compose.yml` binds the host
  port to `127.0.0.1` so copying the file to a server never publishes the
  unauthenticated backend on the public IP. Production overlays keep
  `ports: !reset []` (expose-only behind the proxy).

## [3.0.1] - 2026-07-03

### Fixed

- MCP `initialize` now advertises the package version in `serverInfo.version`
  instead of leaking the FastMCP framework version. `create_litvar_mcp` passes
  `version=__version__` to the `FastMCP(...)` constructor.
- `__version__` is now single-sourced from installed package metadata
  (`importlib.metadata.version("litvar-link")`) instead of being hardcoded in
  `litvar_link/__init__.py`, so `pyproject.toml [project].version` is the sole
  source of truth across `serverInfo.version` and `/health`. A guard test
  (`tests/unit/test_version_single_source.py`) locks the invariant.

## [3.0.0] - 2026-07-03

Adopts the ratified **GeneFoundry Response-Envelope Standard v1** (flat banner;
`docs/RESPONSE-ENVELOPE-STANDARD-v1.md` in `genefoundry-router`, OQ4 -> Option
A). Every MCP tool now routes through a rewritten `litvar_link/mcp/errors.py`
boundary (`run_tool`) plus a new `litvar_link/mcp/envelope.py` shaping module.

### BREAKING

- Success responses are now banner-wrapped: `{"success": true, results|result,
  "_meta": {tool, request_id, elapsed_ms, source, unsafe_for_clinical_use}}`.
  `resolve_rsid` and `get_variant_summary` now nest their single-record payload
  under `result`; `get_server_capabilities` nests the discovery document under
  `result`. `search_genetic_variants`, `get_variant_literature`, and
  `search_gene_variants` already used the fleet-canon `results` key and are
  unchanged in shape (only the banner/`_meta` wrapping is new).
- Execution errors are no longer raised as `fastmcp.exceptions.ToolError`
  subclasses. They are classified into a closed `error_code` enum
  (`invalid_input` · `not_found` · `upstream_unavailable` · `rate_limited` ·
  `internal`) and RETURNED as a flat in-band envelope (`error_code`, `message`,
  `retryable`, `recovery_action`, `_meta`), wrapped in a
  `fastmcp.tools.tool.ToolResult(is_error=True)` so the wire `isError` flag is
  still set (verified against the installed fastmcp 3.4.2 API).
- `litvar_link.mcp.errors.ToolInternalError` is removed; internal failures are
  now the `error_code: "internal"` envelope branch instead of a raised class.

## [2.0.1] - 2026-06-29

Adopt the **GeneFoundry Container & Deployment Hardening Standard v1** (closes #28):
pin the base image by digest (`python:3.14-slim@sha256:b877e50…`), harden the prod
compose overlay (read-only rootfs + tmpfs scratch, `cap_drop: ALL`,
`no-new-privileges`, `init`, pids limit, `ports: !reset []`), disable the unused
gunicorn control socket so the read-only rootfs boots cleanly, and never send CORS
credentials with a wildcard origin.

## [2.0.0] - 2026-06-15

Adopts the **GeneFoundry Tool-Naming Standard v1** so the server composes
cleanly behind the `genefoundry-router` gateway (mounted under the `litvar`
namespace → tools surface as `litvar_<tool>`).

### Added

- Domain `tags` on every data tool (`variant`, `gene`, `literature`) so the
  gateway can filter/curate the surfaced toolset.
- `tests/unit/test_tool_names.py`: CI guard asserting every registered tool
  name matches `^[a-z0-9_]{1,50}$` and starts with a canonical verb
  (`get|search|list|resolve|find|compare|compute`), and is not self-prefixed
  with the `litvar` namespace token.
- README note documenting `serverInfo.name` and the `litvar` gateway namespace
  token.

### Changed

- `__version__` reconciled with `pyproject.toml` (was desynced at `0.1.0`).

### BREAKING

- **Tool renamed:** `lookup_rsid_availability` → `resolve_rsid` (`lookup` is a
  banned verb synonym under the standard; `resolve` fits the rsID-resolution
  semantics). No deprecation alias — update callers immediately.
- **Argument renamed:** `search_gene_variants` arg `gene_name` → `gene_symbol`
  (fleet-canon argument name).
- **Argument renamed:** the rsID tool (`resolve_rsid`) arg `rsid` →
  `variant_id` (fleet-canon `variant_id` covers CHROM-POS-REF-ALT or rsID,
  aligning with `get_variant_summary` / `get_variant_literature`).

## [1.0.0] - 2026-06-01

The stack-modernization release: litvar-link adopts the sibling `*-link`
house style for tooling, packaging, governance docs, file/function size
discipline, and an explicit MCP facade.

### Added

- `AGENTS.md` as the agent source of truth, with a minimal `CLAUDE.md`
  pointer.
- `docs/architecture.md`, `docs/development.md`, and `docs/configuration.md`.
- `Makefile` house spine with a `make ci-local` gate; `scripts/check_file_size.py`
  plus `.loc-allowlist` for the 600-line file budget and the ~60-line
  per-function cap.
- PEP 735 `[dependency-groups] dev`; a committed `uv.lock`.
- `.pre-commit-config.yaml` and `.editorconfig`.
- GitHub Actions workflows (ci, docker, release, security, container-security)
  and Dependabot.
- Explicit `litvar_link/mcp/` facade with one module per tool, plus a
  `get_server_capabilities` discovery tool.
- MCP response affordances over the existing capabilities: `response_mode`
  (`compact`/`full`), result `limit`/truncation, and a `recommended_citation`
  contract on literature results.
- `.github/pull_request_template.md`.

### Changed

- Build backend migrated from setuptools to hatchling; project managed with
  `uv`.
- Linting consolidated to Ruff (the conflicting `.flake8` config is removed);
  ruff rule set widened (E, W, F, I, N, UP, B, C4, S, T20, SIM, RUF) plus the
  `C901`/`PLR0915` function-size guards.
- mypy strict mode retargeted to Python 3.12.
- CLI ported from argparse to typer.
- MCP wiring moved from `FastMCP.from_fastapi` (auto-generated, with a fragile
  `mcp_custom_names` map) to an explicit hand-authored facade; the five tool
  names and semantics are preserved.
- Config now uses `env_nested_delimiter="__"`, so nested settings are
  addressed as `LITVAR_LINK_API__BASE_URL`, `LITVAR_LINK_CACHE__TTL`, etc.;
  the `.env*.example` files are rewritten to match.

### Fixed

- MCP tool-name mapping: tool names are now declared explicitly, eliminating
  the auto-mapping mismatch where some `mcp_custom_names` keys resolved to
  nothing.
- Environment-to-config wiring: documented env vars now map to the nested
  `api.*` / `cache.*` settings fields via the `__` delimiter.

### Removed

- `.flake8` (Ruff is the single linter).
- Dead `mkdocs*` toolchain declarations (no `mkdocs.yml` exists).

### BREAKING

- **Python floor raised to `>=3.12`.** Support for Python 3.9, 3.10, and 3.11
  is dropped to match the sibling `*-link` servers and enable modern typing.
- **Nested env-var addressing changed** to the `__` delimiter
  (`LITVAR_LINK_API__BASE_URL`, `LITVAR_LINK_CACHE__TTL`). Update `.env`
  files and deployment configs accordingly; see `docs/configuration.md`.

[Unreleased]: https://github.com/litvar-link/litvar-link/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/litvar-link/litvar-link/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/litvar-link/litvar-link/releases/tag/v1.0.0
