# litvar-link Stack Modernization — Master Plan

> Historical record — this document records the plan as of its date. Current behavior is defined
> by implemented code, standards, release evidence, and tests.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement the phase plans task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring `litvar-link` to the sibling `*-link` house style — modern Python tooling (hatchling + uv + ruff + mypy + make), a fast CI/CD suite, LLM-oriented governance docs (AGENTS.md + minimal CLAUDE.md), enforced file/function size budgets, and a DRY/KISS/SOLID refactor with an explicit MCP facade.

**Architecture:** Four sequenced, independently-shippable phases. Each phase leaves `main`/the working branch green (`make ci-local` + `make test-cov` pass) and is reviewable on its own. Tooling lands first so every later phase is gated by the same checks.

**Tech Stack:** Python 3.12 (floor `>=3.12`), `hatchling`, `uv` (+ `uv.lock`), `ruff`, `mypy` (strict), `pytest`, `make`, GitHub Actions, FastAPI, `fastmcp`/`mcp`, `httpx`, `async-lru`, `structlog`.

**Spec:** `docs/superpowers/specs/2026-06-01-stack-modernization-design.md` (read it before executing any phase).

---

## Phase Map

| Phase | Plan | Depends on | Outcome |
|-------|------|-----------|---------|
| **P0 — Foundations** | `2026-06-01-p0-foundations.md` | — | hatchling+uv, ruff/mypy/pytest/coverage, Makefile, `check_file_size.py` + `.loc-allowlist`, pre-commit, `.editorconfig`, `uv.lock`. `make ci-local` runs green. |
| **P1 — Governance & docs** | `2026-06-01-p1-governance-docs.md` | P0 | `AGENTS.md` (SoT), minimal `CLAUDE.md`, `CHANGELOG.md`, `docs/{architecture,development,configuration}.md`, README refresh, PR template. |
| **P2 — CI/CD** | `2026-06-01-p2-cicd.md` | P0 | uv-based `docker/Dockerfile` (Task 0) + `ci`/`docker`/`release`/`security`/`container-security` workflows + `dependabot.yml`. CI delegates to `make`. |
| **P3 — Code modernization** | `2026-06-01-p3-refactor.md` | P0 (and reconciles P1 docs) | Split god files, kill 4 DRY clusters, explicit `mcp/` facade + response surface, fix 2 latent bugs, CLI→typer, switch on function-size guards. |

**Recommended sequence:** P0 → (P1 ‖ P2 in parallel) → P3. P3's final task reconciles the P1 `architecture.md`/`AGENTS.md` layout description with the realized module tree.

## Shared Conventions (apply to every phase)

- **Branch:** work on `chore/stack-modernization` (already created). One PR per phase is acceptable, or stack them.
- **Commits:** Conventional Commits (`feat:`/`refactor:`/`build:`/`ci:`/`docs:`/`test:`/`chore:`); commit after every task (each task is an atomic, green commit). End every commit message with:
  ```
  Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
  ```
- **The gate:** `make ci-local` (= `format-check lint-ci lint-loc typecheck-fast test-fast`) must pass before each commit once the Makefile exists (P0). `make test-cov` must keep coverage ≥ 90.
- **Reproducibility:** all commands run through `uv` (`uv run …`, `uv sync --group dev`); never `pip install` into the environment.
- **No unrelated refactors:** stay within the task's scope; defer drive-by changes.
- **House reference repos** (read for exact content, do not modify): `../gnomad-link`, `../autopvs1-link`, `../pubtator-link`, `../genereviews-link`.

## Phase Acceptance (summary — see each plan's "Done when")

- **P0:** clean `uv` checkout → `make ci-local` and `make test-cov` pass; no production file > 600 lines; `.flake8`/`mkdocs*` removed; `uv.lock` committed.
- **P1:** `AGENTS.md` is SoT; `CLAUDE.md` ~6 lines importing it; target P3 layout labelled "target"; `@AGENTS.md` resolves.
- **P2:** five workflows valid (actionlint-clean), SHA-pinned, CI runs `make ci-local` + `make test-cov` on a 3.12/3.13 matrix; dependabot enabled.
- **P3:** every production file < 600 (most < 400), no function over ~60 lines or tripping `C901`/`PLR0915`; 4 DRY clusters gone; 2 latent bugs fixed; explicit MCP facade with `compact`/`full` modes, limits/truncation, `get_server_capabilities`, `recommended_citation`, two-class errors; CLI parity snapshot passes; docs reconciled; coverage ≥ 90.

## Top Risks (from spec §6)

- Python 3.12 bump is a breaking change → documented in CHANGELOG/`1.0.0`.
- Splitting god files changes import paths → re-export public symbols from original paths; update tests in the same commit.
- Switching `C901`/`PLR0915` + function-line cap on too early blocks the refactor → enable only in P3's final task (red→green).
- Explicit MCP facade may change generated tool schemas vs `from_fastapi` → snapshot the 5 tool names/inputs first, assert parity.
- `env_nested_delimiter` change can silently break existing `.env` files → rewrite both example files, add a config smoke test.
