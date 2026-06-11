# Development

LitVar-Link uses `uv` for dependency management and a `Makefile` as the task
runner. Do not use `pip` directly; `uv.lock` is the lock source of truth.

## Prerequisites

- Python **3.12** (the project floor; see `.python-version`).
- [`uv`](https://docs.astral.sh/uv/) installed.
- GNU Make.

## Setup

```bash
# Install the project plus the dev dependency group into a managed venv
make install        # uv sync --group dev

# Copy the environment template
cp .env.example .env
```

`make install` (or `make sync`) creates `.venv` and installs from `uv.lock`.
Every Make target runs tools through `uv run`, so you never need to activate
the venv manually.

## The required gate

Before claiming any change complete, run:

```bash
make ci-local
```

`ci-local` runs `format-check`, `lint-ci`, `lint-loc` (the file/function size
budget), `typecheck-fast`, and `test-fast`. CI runs the same target, so a
green `make ci-local` locally means a green CI.

When coverage-relevant code changed, also run:

```bash
make test-cov       # coverage with fail_under=90
```

## Make targets

### Dependencies

| Target | Purpose |
|--------|---------|
| `make install` | Sync project + dev group from `uv.lock`. |
| `make sync` | Alias for the dev sync. |
| `make lock` | Regenerate `uv.lock`. |
| `make upgrade` | Upgrade locked dependencies. |

### Quality

| Target | Purpose |
|--------|---------|
| `make format` | Apply Ruff formatting. |
| `make format-check` | Check formatting without writing. |
| `make lint` | Run Ruff lint. |
| `make lint-fix` | Run Ruff lint with `--fix`. |
| `make lint-ci` | Ruff lint in CI mode. |
| `make lint-loc` | Enforce the 600-line file cap + ~60-line function cap. |
| `make typecheck` | Run mypy (strict, py3.12). |
| `make typecheck-fast` | Run mypy via the daemon, falling back to a fresh run. |

### Tests

| Target | Purpose |
|--------|---------|
| `make test` | Fast default test run. |
| `make test-fast` | Tests with `-n auto` (xdist). |
| `make test-unit` | Only `tests/unit/`. |
| `make test-integration` | Live LitVar2 tests (may rate-limit). |
| `make test-cov` | Coverage run with `fail_under=90`. |

### Aggregate / serve / docker

| Target | Purpose |
|--------|---------|
| `make check` | Lint + typecheck + tests (no coverage). |
| `make ci-local` | The required gate (see above). |
| `make precommit` | Run the `ci-local` gate as the pre-commit guard. |
| `make clean` | Remove caches and build artifacts. |
| `make dev` | Run the dev server with reload. |
| `make mcp-serve` | Run the MCP server over stdio. |
| `make mcp-serve-http` | Run the unified server with MCP over HTTP. |
| `make docker-build` | Build the Docker image. |
| `make docker-up` / `make docker-down` | Start / stop the Compose stack. |
| `make docker-prod-config` / `make docker-npm-config` | Render Compose configs. |

Run `make help` for the self-documenting list.

## Running tests directly

Most workflows should go through Make, but you can run pytest under `uv`:

```bash
uv run pytest                       # all tests
uv run pytest tests/unit            # unit tests only
uv run pytest -m "not integration"  # exclude live LitVar2 tests
uv run pytest -m integration        # only live LitVar2 tests
uv run pytest tests/unit/test_<x>.py::test_<y>   # single test
```

Markers: `slow` and `integration` are registered; `--strict-markers` is on,
so unknown markers fail.

## Pre-commit

Install the hooks once per clone:

```bash
uv run pre-commit install
```

The configured hooks run Ruff (`--fix` + format), mypy, and the file/function
size budget. The pre-commit ruff `rev` may drift from the `uv.lock` ruff
version; that is expected - CI uses `uv` and is authoritative.

Run all hooks against the whole tree on demand:

```bash
uv run pre-commit run --all-files
```

## Code style

- Modern typing: `list[str]`, `dict[str, int]`, `str | None`.
- Ruff is the single linter/formatter (line length 100).
- mypy strict, targeting Python 3.12.
- Keep modules under 600 lines and functions under ~60 lines (see
  `AGENTS.md`).
