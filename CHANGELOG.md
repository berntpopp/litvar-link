# Changelog

All notable changes to litvar-link are documented in this file. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/litvar-link/litvar-link/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/litvar-link/litvar-link/releases/tag/v1.0.0
