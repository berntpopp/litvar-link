# Stack Modernization & Repo Update — Design Spec

- **Date:** 2026-06-01
- **Status:** Revised after Claude review (2026-06-01); plan pending

> Historical record — this document records the design as of its date. Current behavior is defined
> by implemented code, standards, release evidence, and tests.

- **Author:** Bernt Popp (with Claude Code)
- **Topic:** Bring `litvar-link` to the sibling "house style" (`gnomad-link`, `autopvs1-link`, `pubtator-link`, `genereviews-link`) — modern Python tooling, LLM-oriented governance docs, file/function size discipline, and a DRY/KISS/SOLID code refactor.

---

## 1. Context

`litvar-link` is a FastAPI + FastMCP server wrapping NCBI's LitVar2 biomedical literature/variant API. It predates the conventions the four sibling `*-link` repos converged on. The four references share a deliberate, near-identical house style; `litvar-link` does not yet follow it.

### Current state (evidence)

| Area | litvar-link today | Sibling house style |
|------|-------------------|---------------------|
| Build backend | `setuptools` | `hatchling` |
| Python floor | `>=3.9` | `>=3.12` |
| Dep manager | pip + `pyproject` optional-deps; **no lockfile** | `uv` + committed `uv.lock`, PEP 735 `[dependency-groups]` |
| Linter | `.flake8` (max-line 120) **and** ruff (100) — conflicting | ruff only (100) |
| Type checker | mypy strict (py39) | mypy strict (py312) |
| Task runner | none | `Makefile` (`ci-local` gate) |
| CI/CD | **none** (no `.github/`) | ci / docker / release / security / container-security |
| Agent docs | **none** | `AGENTS.md` (SoT) + minimal `CLAUDE.md` |
| File-size enforcement | none (complexity rules disabled) | 600-line cap via `scripts/check_file_size.py` + `.loc-allowlist` |
| Pre-commit | dep declared, **no config** | `.pre-commit-config.yaml` |
| Docs / CHANGELOG | inline README only | `docs/` + `CHANGELOG.md` (Keep a Changelog) |
| MCP wiring | `FastMCP.from_fastapi` (auto) | explicit `mcp/` facade + `tools/` (gnomad/autopvs1/pubtator) |

### Concrete code findings driving the refactor

- **Two near-god files:** `api/client.py` (558 lines), `services/variant_service.py` (552) — both over the ~500-line "plan a split" guideline, with two more approaching it (`api/routes/variants.py` 395, `cli.py` 349).
- **Seven functions > 100 lines**, headed by `api/client.py::_make_request` (167 lines, real retry/rate-limit/parse logic). The route handlers (100–155 lines) are inflated mostly by inline OpenAPI `responses={...}` example dicts, not branching logic.
- **Four DRY clusters:** (1) input validation duplicated across `client.py` and `variant_service.py` (raising different exception types); (2) ~12-line cache-hit-detection block copied into all 5 service methods; (3) identical `except ValidationError/LitVarAPIError/Exception` block in all 5 route handlers; (4) response-shape normalization repeated in `client.py`.
- **Two latent bugs:** (a) `app.py` `mcp_custom_names` keys don't all match FastAPI `operation_id`s (e.g. `lookup_rsid`/`search_variants` map to nothing; the sensor's real `check_rsid_availability` is not remapped); (b) documented env vars (`LITVAR_LINK_RATE_LIMIT`, `_CACHE_TTL`, `_API_BASE_URL`) don't map to the nested `api.*`/`cache.*` pydantic-settings fields.
- **Dead declarations:** `typer[rich]` (CLI uses argparse), `mkdocs*` toolchain (no `mkdocs.yml`), `pre-commit` (no config), missing `py.typed` on disk, `.flake8` referencing a non-existent `scripts/`.
- **Async stack (good, keep):** `httpx.AsyncClient`, custom `TokenBucketRateLimiter` (2.0 req/s, burst 5), exponential-backoff retry, `async-lru` caching with per-method TTLs. Tests: pytest, ~308 tests, ~94% coverage.

---

## 2. Goals & Non-Goals

### Goals
1. Adopt the sibling house style for tooling, packaging, CI/CD, and governance docs.
2. Set the repo up for modern LLM-based development: `AGENTS.md` as source of truth, minimal `CLAUDE.md`, explicit **file-size** and **function-size** constraints enforced in CI.
3. Apply DRY / KISS / SOLID / modularization to the concrete findings above — split the god files, kill the four DRY clusters, shrink oversized functions.
4. Move the MCP surface to an explicit, well-described `mcp/` facade + per-tool `register()` modules.
5. Fix the two latent bugs (MCP name mapping, env→config wiring) as part of the refactor.

### Non-Goals
- No change to the LitVar2 API contract, the set of 5 user-facing capabilities, or the REST endpoint paths.
- No new features or endpoints beyond what exists, **except MCP-surface affordances** (per D9: response modes, result limits/truncation, a `get_server_capabilities` discovery tool, and a `recommended_citation` field) that re-shape *existing* data without any new upstream LitVar2 calls.
- No automated agent-task evaluation of tool-description quality this round. The schema-parity snapshot (Open Item #2) is a regression guard, not a quality measure; description eval against realistic agent tasks is a named **follow-up** (§7).
- No rewrite of the async/caching/rate-limit strategy (it is sound — only re-housed).
- No database/persistence layer (litvar is stateless; unlike pubtator/genereviews it has no `db/`).
- Execution is **out of scope for this document** — this spec produces a phased implementation plan for separate review.

---

## 3. Decisions (locked)

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| D1 | Scope | **Stack + code refactor** | User wants DRY/KISS/SOLID + function-size limits, which require code changes. |
| D2 | Deliverable | **Spec + phased plan**, then review | No code lands this session. |
| D3 | Python floor | **`>=3.12`** | Match all four siblings; enable modern typing. Drops 3.9–3.11. |
| D4 | MCP wiring | **Explicit `mcp/` facade + `tools/`** | Match gnomad/autopvs1/pubtator; richer per-tool LLM guidance; fixes the name-mapping bug structurally. |
| D5 | Version | `0.1.0` → **`1.0.0`** | Marks the modernized, stabilized release (siblings are 1.x/2.x). |
| D6 | Coverage floor | **`fail_under = 90`** | Already at ~94%; keep the high bar. |
| D7 | CLI | **argparse → typer** | Resolves the `typer` dead-dep and matches house style; modularizes the 349-line `cli.py`. |
| D8 | Function-size enforcement | **AST per-function line cap (~60) in `check_file_size.py`** + **ruff `C901`≤10 / `PLR0915`≤50** | Ruff has *no* per-function line rule (`C901`=complexity, `PLR0915`=statements); the line-bloated route handlers are low-complexity, so only an AST line check catches them. The two guards are complementary. Deliberate enhancement *beyond* the references (which cap files only). |
| D9 | MCP response surface | **Fuller house parity**: `response_mode` (compact/full) + result `limit`/truncation, a `get_server_capabilities` tool, and a `recommended_citation` contract on literature results | Matches gnomad/pubtator/sysndd/genereviews and Anthropic tool-design guidance (configurable verbosity, truncation, discoverability). |

---

## 4. Target End-State

### 4.1 Build & dependency management
- Build backend `hatchling`; `[tool.hatch.build.targets.wheel] packages = ["litvar_link"]`, plus `include = ["server.py", "mcp_server.py"]`.
- `requires-python = ">=3.12"`; classifiers for **3.12/3.13** + Bio-Informatics (test-what-you-ship: no 3.14 classifier until CI tests it); add `.python-version = 3.12`.
- Generate and commit **`uv.lock`**; no `[tool.uv]` section. All workflows use `uv sync --group dev` / `uv run` / `uv sync --group dev --frozen` (CI).
- Dev deps → PEP 735 `[dependency-groups] dev`: `pytest`, `pytest-asyncio`, `pytest-cov`, `pytest-mock`, `pytest-xdist`, `respx`, `ruff>=0.8`, `mypy`, `pre-commit>=4`.
- Console scripts: `litvar-link = "litvar_link.cli:app"`, `litvar-link-mcp = "mcp_server:main"`.
- Runtime deps: keep `fastapi`, `uvicorn[standard]`, `pydantic>=2`, `pydantic-settings`, `httpx`, `async-lru`, `structlog`, `orjson`, `rich`, `typer`, `mcp[cli]`, `fastmcp`; **promote** `gunicorn`, `prometheus-client`, `asgi-correlation-id` into runtime deps; **all version-capped** (`>=x,<major`).
- Remove: `.flake8`, `mkdocs*` deps. **Verify** OpenTelemetry is actually wired in code before removing its optional group; if unused, drop it.

### 4.2 Tooling config (pyproject)
- **ruff:** `line-length=100`, `target-version="py312"`; `extend-select=["E","W","F","I","N","UP","B","C4","S","T20","SIM","RUF","C901","PLR0915"]`; `ignore=["S101","E501"]`; `[tool.ruff.lint.mccabe] max-complexity=10`; `[tool.ruff.lint.pylint] max-statements=50`; format `double`/`space`/`lf`; `per-file-ignores` `"tests/**/*"=["S101","T20","C901","PLR0915"]`.
- **mypy:** keep `strict=true`, retarget `python_version="3.12"`; per-module `ignore_missing_imports` overrides for untyped deps (uvicorn/fastmcp/mcp/async_lru/orjson/structlog/rich/typer); exclude venv/site-packages/htmlcov.
- **pytest:** `testpaths=["tests"]`, `asyncio_mode="auto"`, `asyncio_default_fixture_loop_scope="function"`, `addopts=["--strict-markers","-ra","--import-mode=importlib"]`; markers `slow`, `integration`. Coverage flags move **out** of `addopts` into `make test-cov`.
- **coverage:** `source=["litvar_link"]`, omit tests/`__main__`, `branch=true`, `fail_under=90`, `precision=2`, `show_missing=true`, `skip_empty=true`; html→`htmlcov`, xml→`coverage.xml`.

### 4.3 File & function size discipline
- **File cap: 600 lines** for `litvar_link/`, `server.py`, `mcp_server.py` (tests exempt). Enforced by `scripts/check_file_size.py` (ported from siblings; reads `.loc-allowlist`) via `make lint-loc`, wired into `ci-local` + pre-commit. `.loc-allowlist` starts effectively empty (no production file > 600 today). **Plan a cohesive split when a file approaches ~500 lines.**
- **Function size (new) — two complementary guards** (both switched on at the *end* of P3, red→green; documented in `AGENTS.md`):
  - **Per-function line cap ~60** — enforced by an AST pass added to `scripts/check_file_size.py` (ruff has **no** line-count rule). This is the guard that catches the line-bloated route handlers, which are low-complexity and would otherwise slip past ruff.
  - **Complexity/statement budget** — ruff `C901` (cyclomatic ≤10, the McCabe/NIST threshold) + `PLR0915` (≤50 statements). `PLR0912`/`PLR0913` deliberately left off to avoid friction with FastAPI dependency-injection signatures.

### 4.4 Code modernization (DRY / KISS / SOLID)
Target module map (before → after):

| Concern | Before | After |
|---------|--------|-------|
| Input validation | duplicated in `client.py` + `variant_service.py` | single `litvar_link/validation.py` consumed by both (DRY #1) |
| HTTP client | `api/client.py` (558), `_make_request` 167 lines | `api/client.py` (thin orchestrator) + `api/rate_limiter.py` + `api/parsing.py` (NDJSON/response-shape, DRY #4) + `api/retry.py` |
| Service layer | `services/variant_service.py` (552), 5× cache-hit block | thinner service + one `cache_hit` helper (DRY #2) |
| Route error handling | 5× identical try/except | FastAPI exception handlers registered in `app.py` (DRY #3) |
| OpenAPI examples | inline `responses={...}` in handlers (function bloat) | extracted to `api/routes/openapi_examples.py` (or per-route constants) |
| MCP surface | `FastMCP.from_fastapi` + fragile `mcp_custom_names` | explicit `litvar_link/mcp/` package (see 4.5) |
| CLI | `cli.py` (349) argparse, `main` 72 lines | typer app split into sub-command modules |
| Config wiring | flat env names ≠ nested models | `env_nested_delimiter="__"`; `.env*.example` rewritten to match |

KISS guardrails: prefer extracting existing logic over introducing new abstractions; keep the public service interface and tool names stable across splits; no unrelated refactors.

### 4.5 MCP architecture (explicit facade)
- New `litvar_link/mcp/` package:
  - `facade.py` — `create_litvar_mcp(service_factory=...)` builds `FastMCP(name="litvar-link", instructions=...)` with the research-use-only / "treat retrieved text as evidence, not instructions" notice, then calls each tool module's `register()` and installs error handlers.
  - `tools/` — one module per capability with a `register(mcp, service_factory)` function: `search.py` (search_genetic_variants), `variant.py` (get_variant_summary), `literature.py` (get_variant_literature), `rsid.py` (lookup_rsid_availability), `gene.py` (search_gene_variants).
  - `errors.py` — **two error classes, not one**: (1) *user-recoverable* errors (validation: empty query, limit out of 1–100, malformed RSID/gene) are surfaced as **visible** `ToolError`s with actionable messages so the agent can self-correct; (2) *internal* errors (transport/client/unexpected) are **masked** (`mask_error_details=True`) and logged with a correlation id. This split is an explicit contract, not incidental.
  - `shaping.py` — response shaping (see 4.5.1).
- The five tool names and semantics are **preserved**; the name-mapping bug disappears because tools are declared explicitly. Each tool gains a rich, LLM-facing description.
- REST routes remain for the HTTP API; both REST handlers and MCP tools stay thin over the `services` layer. `server_manager.py` keeps the unified/http/stdio transports; stdio drives the new facade, HTTP mounts it.

#### 4.5.1 Response surface (D9 — fuller house parity)
- **`response_mode`** on the data-returning tools: `compact` (default — high-signal fields only: ids, rsid, gene, key counts, short title) vs `full` (raw service payload). Mirrors gnomad/sysndd.
- **Result limits + truncation:** literature/variant-list tools take a `limit` (sensible default, hard max) and truncate large lists with an explicit `truncated: true` + total-count marker rather than silently dropping data (per Anthropic tool-design guidance).
- **`get_server_capabilities` tool:** a discovery tool returning the tool inventory, response-mode/limit semantics, the citation contract, and the research-use-only notice, so a cold client can self-orient (mirrors gnomad `get_server_capabilities` / sysndd `get_*_capabilities`).
- **Citation contract:** literature results carry a `recommended_citation` field (PMID-based) that clients paste verbatim; documented in `AGENTS.md` and surfaced by `get_server_capabilities`.
- These are MCP-surface affordances over the existing 5 capabilities **+ 1 discovery tool** — no new upstream LitVar2 calls or REST endpoints are added.

### 4.6 Governance & docs
- **`AGENTS.md`** (source of truth) — sections: Project, Source Of Truth, Working Rules, Commands (`make ci-local` = required gate), Coding Standards (uv not pip; modern typing; ruff; mypy strict py3.12), **File & Function Size Discipline**, Testing Notes. Litvar specifics: env prefix `LITVAR_LINK_`, transports `stdio|http|unified`, LitVar2 rate-limit etiquette, research-use-only.
- **`CLAUDE.md`** — minimal (~6 lines), first line `@AGENTS.md`, "Claude Code entrypoint only" + the `make ci-local` / size-budget reminder. No duplication.
- **`CHANGELOG.md`** — Keep a Changelog + SemVer; `1.0.0` entry summarizing this modernization.
- **`.editorconfig`** — utf-8/lf/final-newline, 4-space Python, 2-space yaml/toml/json/md, tab Makefile.
- **`docs/`** — `architecture.md`, `development.md`, `configuration.md`, generated `mcp-tool-catalog.md`; `docs/superpowers/{specs,plans}/` (this spec + the plan live here).
- **`README.md`** — refreshed for uv/make workflow and the explicit MCP tools.
- **`.github/pull_request_template.md`**.

### 4.7 Makefile
House spine, `.DEFAULT_GOAL := help`, awk `##` self-documentation, autodetected `DOCKER_COMPOSE`, every target via `uv run`. Targets: `install`/`sync`/`lock`/`upgrade`; `format`/`format-check`/`lint`/`lint-ci`/`lint-fix`/`lint-loc`; `typecheck`/`typecheck-fast`(dmypy+fallback)/`typecheck-stop`/`typecheck-fresh`; `test`/`test-fast`(`-n auto`)/`test-unit`/`test-integration`/`test-cov`; `check`; **`ci-local = format-check lint-ci lint-loc typecheck-fast test-fast`**; `precommit`→`ci-local`; `clean`; `dev`/`mcp-serve`/`mcp-serve-http`; `docker-build`/`up`/`down`/`logs`/`prod-config`/`npm-config`.

### 4.8 CI/CD
Ported from `autopvs1-link` (the CI reference). Universal conventions: `concurrency` group with `cancel-in-progress: true`; top-level `permissions: contents: read`; **all actions SHA-pinned with `# vX` comments**; `astral-sh/setup-uv` (`enable-cache: true`, pinned version) + `actions/setup-python@v6` pinned `3.12`; deps via `uv sync --group dev --frozen`.
- **`ci.yml`** — PR + push `main`; `quality` job on a **`python-version: ["3.12","3.13"]` matrix** (test-what-you-ship): checkout → setup-python → uv → `uv sync --group dev --frozen` → **`make ci-local`** → **`make test-cov`**.
- **`docker.yml`** — build `docker/Dockerfile`; validate compose configs.
- **`security.yml`** — CodeQL (python, build-mode none, public-repo gate) + dependency-review (PR-only, continue-on-error) + weekly cron.
- **`container-security.yml`** — Trivy vuln scan + SBOM, weekly cron, non-blocking.
- **`release.yml`** — on tag `v*`: `make ci-local` + `uv build` + upload `dist/` artifact.
- **`dependabot.yml`** — ecosystems `uv`, `github-actions`, `docker`, `docker-compose`; weekly; limit 5; `deps`/`ci` prefixes.
- **`.pre-commit-config.yaml`** — `pre-commit-hooks v5` + `ruff-pre-commit` (`ruff --fix --exit-non-zero-on-fix` + `ruff-format`) + local hooks `mypy` and `file-size-budget` (both `uv run`, `pass_filenames: false`).

### 4.9 Docker
- Update `docker/Dockerfile` to **uv-based multi-stage** on `python:3.13-slim` (inside the CI-tested matrix, so we test the runtime we ship): builder runs `uv sync --frozen --no-dev` into a venv; slim production stage; non-root `app` user; healthcheck on `/api/health/`; gunicorn + uvicorn workers.
- Keep the compose overlays; rename `.env.npm.example` → `.env.docker.example` to match house naming; keep the Nginx-Proxy-Manager deployment path.

---

## 5. Phase Breakdown

Each phase is independently reviewable and leaves the repo green.

### P0 — Foundations (tooling, no logic change)
- hatchling migration; `requires-python>=3.12`; `.python-version`; PEP 735 dev group; generate `uv.lock`.
- ruff/mypy/pytest/coverage config to house style (but **without** `C901`/`PLR0915` yet — those wait for P3).
- Remove `.flake8` + `mkdocs*`; verify/remove OpenTelemetry group.
- `Makefile`; `scripts/check_file_size.py` + `.loc-allowlist`; `.pre-commit-config.yaml`; `.editorconfig`.
- App code touched only mechanically to satisfy ruff/mypy.
- *Verified, no `S`-triage pass needed:* litvar's current ruff config already selects `S` and the tree passes it; the leaner house `S` set introduces no new failures (the only `0.0.0.0` literals are in `docker/`/compose outside lint scope, and the httpx client already sets a timeout).
- **Done when:** `make ci-local` and `make test-cov` pass locally on a clean checkout.

### P1 — Governance & docs
- `AGENTS.md`, `CLAUDE.md`, `CHANGELOG.md` (1.0.0 stub), `docs/{architecture,development,configuration}.md`, README refresh, PR template.
- `architecture.md` describes the **target** P3 layout and is explicitly labelled as the target (the refactor lands in P3); it is reconciled to reality in P3's exit task.
- **Done when:** docs accurately describe the P0 tooling, the target layout is marked as target (not present-tense), and `@AGENTS.md` import resolves.

### P2 — CI/CD
- Modernize `docker/Dockerfile` to a uv-based multi-stage build on `python:3.13-slim` (§4.9), then add the `ci`, `docker`, `release`, `security`, `container-security` workflows + `dependabot.yml`.
- **Done when:** the Dockerfile builds on 3.13; workflows are valid (actionlint clean) and `ci.yml` mirrors `make ci-local` + `make test-cov`.

### P3 — Code modernization (the refactor)
Ordered sub-steps (each its own atomic commit, suite green after each):
1. `validation.py` (DRY #1) + config-wiring fix (`env_nested_delimiter`) + `.env*.example` rewrite.
2. Split `api/client.py` → `rate_limiter.py` + `parsing.py` (DRY #4) + `retry.py`; decompose `_make_request`.
3. Split `services/variant_service.py`; single `cache_hit` helper (DRY #2).
4. Route error handlers in `app.py` (DRY #3) + extract OpenAPI examples.
5. Explicit `litvar_link/mcp/` facade + `tools/` + `errors.py` (two-class) + `shaping.py`; remove `FastMCP.from_fastapi` path + `mcp_custom_names`; fix tool-name bug; add rich descriptions/instructions; add `response_mode`/`limit`/truncation, the `get_server_capabilities` tool, and the `recommended_citation` field (D9). Snapshot the pre-change tool names/input schemas first and assert parity on the preserved 5.
6. CLI argparse → typer (`cli:app`), split into sub-command modules; **add a CLI golden-output parity test** (captured `--help`/exit-code/flag-surface snapshot) so the migration doesn't silently change the scripting contract.
7. Reorganize `tests/` → `tests/unit/` + `tests/integration/`; **switch on the per-function line cap (`check_file_size.py`) and ruff `C901` + `PLR0915`**; confirm coverage ≥ 90.
8. **Exit task — reconcile docs:** update `AGENTS.md` + `docs/architecture.md` so the described module layout matches the realized P3 layout (close the P1 target-vs-reality gap).
- **Done when:** every production file < 600 (most < 400) and no function exceeds the ~60-line cap or trips `C901`/`PLR0915`; all four DRY clusters removed; both latent bugs fixed; the 5 MCP tools resolve with correct names + `compact`/`full` modes + limits, the `get_server_capabilities` tool and `recommended_citation` field are present, and errors split recoverable-vs-masked; the CLI parity snapshot passes; docs reconciled to the realized layout; `make ci-local` + `make test-cov` green.

---

## 6. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Python 3.12 bump breaks a consumer on 3.9–3.11 | Documented breaking change in CHANGELOG/`1.0.0`; matches all siblings; verify no 3.9-only syntax remains. |
| Splitting god files changes import paths used by tests | Keep public symbols re-exported from the original module path where feasible; update tests in the same commit. |
| Switching `C901`/`PLR0915` on too early blocks the refactor | Enable them only in P3 step 7, after functions are already small. |
| Explicit MCP facade subtly changes generated tool schemas vs from_fastapi | Snapshot current tool names/inputs first; assert parity in tests; preserve the 5 names + semantics. |
| `env_nested_delimiter` change silently breaks existing `.env` files | Rewrite both example files; document the `API__`/`CACHE__` nesting prominently; add a config smoke test. |
| Coverage dips below 90 mid-refactor | Keep `fail_under` in `make test-cov` (not `addopts`) so intermediate commits aren't blocked; restore ≥90 by end of P3. |
| OpenTelemetry removal deletes a used feature | Grep for actual otel usage before removal; keep the group if wired. |
| `argparse → typer` silently changes `--help`/flags/exit codes (a scripting contract) | CLI golden-output parity snapshot test in P3.6, mirroring the MCP schema snapshot. |
| Test-vs-ship Python skew | CI matrix tests **3.12 and 3.13**; Docker ships 3.13 (inside the matrix); the 3.14 classifier is dropped until tested. |
| New MCP response affordances (D9) drift from the preserved tool contract | The 5 tool names/semantics stay fixed; new params are additive with defaults; capabilities tool documents them; parity snapshot covers the preserved 5. |

---

## 7. Open Verification Items (resolve during planning/P0)
1. Confirm whether OpenTelemetry instrumentation is actually wired (keep vs drop the optional group).
2. Snapshot the current `FastMCP.from_fastapi`-generated tool names + input schemas to assert parity after the explicit-facade rewrite.
3. Confirm the exact current env-var → nested-field mismatches to size the `.env*.example` rewrite.
4. Confirm `fastmcp`/`mcp` major versions to pin (siblings use `mcp[cli]>=1.27`, `fastmcp>=3.x`); litvar currently floors `mcp>=1.0`, `fastmcp>=0.2` — a major jump that may need code adjustments in the facade.
5. Confirm `get_variant_summary`/`get_variant_literature` read as **distinct from pubtator-link's** literature tools at agent tool-selection time (litvar and pubtator co-deploy in the same environment); adjust descriptions if they collide.
6. **Follow-up (not this milestone):** evaluate tool-description quality with realistic agent tasks (does the agent pick the right tool?), per Anthropic guidance — the parity snapshot is only a regression guard, not a quality signal.

---

## 8. Success Criteria
- `make ci-local` and `make test-cov` pass on a clean `uv` checkout; coverage ≥ 90.
- All five GitHub Actions workflows present, valid, and SHA-pinned; CI delegates to `make`.
- `AGENTS.md` is the source of truth; `CLAUDE.md` is ~6 lines importing it.
- No production Python file > 600 lines (most < 400); no function exceeds the ~60-line cap (AST check) or trips `C901`/`PLR0915`.
- The four DRY clusters are gone; both latent bugs are fixed; the five MCP tools resolve with correct names and rich descriptions.
- MCP tools expose `compact`/`full` response modes + result limits/truncation; the `get_server_capabilities` tool and `recommended_citation` contract are present; recoverable vs internal errors are distinguished.
- The CLI flag / `--help` / exit-code surface is covered by a parity snapshot across the argparse→typer migration.
- Tooling, packaging, CI, docs, and governance match the sibling house style; deliberate divergences (function line+complexity rules, coverage floor 90, the fuller MCP response surface) are documented in `AGENTS.md`.
