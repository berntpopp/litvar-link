# Phase 0 — Foundations Implementation Plan

> Historical record — this document records the plan as of its date. Current behavior is defined
> by implemented code, standards, release evidence, and tests.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring `litvar-link`'s build, dependency, lint, type, test, and task-runner tooling to the sibling "house style" (hatchling + uv + ruff + mypy strict + Makefile + size budget) with zero application-logic changes beyond mechanical lint/type fixes.

**Architecture:** P0 replaces the packaging and tooling skeleton only. The build backend moves setuptools → hatchling; dev deps move to PEP 735 `[dependency-groups]`; a committed `uv.lock` becomes the source of dependency truth; ruff/mypy/pytest/coverage configs are rewritten to the house spine; a `Makefile`, `scripts/check_file_size.py`, `.loc-allowlist`, `.pre-commit-config.yaml`, `.editorconfig`, and `.python-version` are added. The 600-line file-budget check is wired in, but the AST per-function check and ruff `C901`/`PLR0915` are deliberately deferred to P3. No `litvar_link/` runtime behavior changes.

**Tech Stack:** Python 3.12, hatchling, uv, ruff ≥0.8, mypy (strict), pytest + pytest-asyncio/-cov/-mock/-xdist + respx, pre-commit ≥4, GNU Make.

**Prerequisite:** None. **Unlocks:** P1, P2, P3.

---

## Environment facts (verified during planning — read before starting)

- `uv`, `ruff` (0.14.3), and a `mypy`/`pytest` venv-only install are present. **The bare `mypy` on `PATH` is a broken shim** (`ModuleNotFoundError: No module named 'mypy'`) — always run type checks via `uv run mypy`, never bare `mypy`.
- Python **3.12.9 and 3.13.7 are both available**; `uv python find 3.12` resolves. With no `.python-version`, `uv` defaulted a probe venv to 3.11 — so pinning `.python-version=3.12` and `requires-python=">=3.12"` matters and `uv` will pick a real 3.12 interpreter once they exist.
- **OpenTelemetry grep result:** `grep -rn "opentelemetry\|otel" litvar_link` → **0 matches (exit 1)**. The `production` optional group's `opentelemetry-*` deps are unused in code → **drop them** (keep only `gunicorn`/`prometheus-client`, promoted to runtime; add `asgi-correlation-id`).
- **Largest production Python file today: `litvar_link/api/client.py` = 558 lines** (next: `services/variant_service.py` 552, `api/routes/variants.py` 395, `cli.py` 349). **No production file exceeds 600** → `.loc-allowlist` stays comment-only.
- `litvar_link/py.typed` is **missing on disk** (declared in pyproject only) → must be created as a real file.
- Current `[project.scripts]` second entry is `litvar-mcp` → rename to `litvar-link-mcp` (house naming).
- The CLI invocation surface is `litvar-link serve {http,unified,mcp}` (argparse sub-subcommands), **not** `--transport`. `server.py`/`mcp_server.py` are thin entry points (`server.py` calls `uvicorn.run`; `mcp_server.py` runs stdio). The Makefile `dev`/`mcp-serve`/`mcp-serve-http` targets in this plan are adapted to litvar's **actual** entry points (see Task 9), not autopvs1's `--transport` flag.
- `.env.npm.example` exists; the spec renames it to `.env.docker.example` in **P3**, not P0 — leave it alone here.

### Pre-verified lint surface (the only mechanical code fixes P0 needs)

Running the target house ruff config (`--target-version py312 --select E,W,F,I,N,UP,B,C4,S,T20,SIM,RUF --ignore S101,E501`, tests ignoring `S101,T20`) over the current tree yields, after `ruff check --fix` (and `ruff format`):

| Rule | Count | Where | Fix |
|------|-------|-------|-----|
| `UP045` | 92 | production models/exceptions | `Optional[X]` → `X \| None` — **auto-fixed** by `ruff check --fix` |
| `UP035` | 2 | `api/client.py` (`Self`), `utils/caching.py` (`Callable`) | import from `typing`/`collections.abc` — **auto-fixed** |
| `RUF100` | 6 | redundant `# noqa: E501` | **auto-fixed** (removed) |
| `I001` | 5 | `api/routes/*` import blocks | **auto-fixed** |
| `B904` | 15 | `api/routes/{genes,publications,sensor,variants}.py` | **manual**: add `from e` to `raise HTTPException(...)` inside `except ... as e:` |
| `RUF012` | 30 | tests | **manual**: annotate mutable class attrs `ClassVar[...]` |
| `SIM117` | 26 | tests | **manual**: merge nested `with` into one statement (or `# noqa: SIM117`) |
| `S104` | 8 | tests (`"0.0.0.0"` literals) | **manual**: `# noqa: S104` (intentional test host) |
| `RUF043` | 2 | `tests/test_api/test_client.py` | **manual**: make `pytest.raises(match=...)` pattern a raw string |
| `F401` | 1 | `tests/test_logging.py:242` | **manual**: remove unused `orjson` import |

The spec (§5 P0) states the leaner house `S` set introduces no *new production* failures and needs no `S`-triage pass — confirmed: the only production-relevant `S104` (`0.0.0.0`) literals live in `docker/`/compose (outside lint scope) and `cli.py`/`server_manager.py` use `127.0.0.1`. The `S104` hits above are all in **test files**, which the old config blanket-ignored `S`; the house config only ignores `S101`, so they surface and get a targeted `# noqa: S104`.

mypy is already `strict=true` and currently clean; retargeting py39→py312 is not expected to add errors (3.12 is a superset of valid 3.9 typing). Run `uv run mypy litvar_link server.py mcp_server.py` to confirm in Task 11.

---

## File Map

| Path | Action | Responsibility |
|------|--------|----------------|
| `pyproject.toml` | Modify | hatchling backend; `requires-python>=3.12`; version `1.0.0`; 3.12/3.13 classifiers; runtime deps (promote gunicorn/prometheus-client/asgi-correlation-id, drop otel/mkdocs/python-multipart-as-needed); PEP 735 `[dependency-groups] dev`; console scripts; ruff/mypy/pytest/coverage house config |
| `litvar_link/py.typed` | Create | PEP 561 marker file (real, on disk) |
| `.flake8` | Delete | conflicting second linter — removed |
| `.python-version` | Create | pin `3.12` for uv |
| `Makefile` | Create | house task runner; `ci-local` gate |
| `scripts/check_file_size.py` | Create | 600-line per-file budget enforcement (file-size only; AST check added in P3) |
| `.loc-allowlist` | Create | grandfather list (comment-only; no file >600) |
| `.pre-commit-config.yaml` | Create | pre-commit-hooks v5 + ruff + local mypy + file-size hooks |
| `.editorconfig` | Create | editor normalization |
| `uv.lock` | Create (generated) | committed lockfile |
| `litvar_link/exceptions.py`, `models/*.py` | Modify (mechanical) | `Optional[X]`→`X \| None` autofix |
| `litvar_link/api/client.py`, `utils/caching.py` | Modify (mechanical) | `UP035` import autofix |
| `litvar_link/api/routes/*.py` | Modify (mechanical) | `B904` `raise ... from e`; `I001` import sort |
| `litvar_link/app.py`, `cli.py`, `models/responses.py` | Modify (mechanical) | drop redundant `# noqa: E501` |
| `tests/**` | Modify (mechanical) | `RUF012`/`SIM117`/`S104`/`RUF043`/`F401` fixes |

---

### Task 1: Migrate build backend and project metadata to hatchling

**Files:**
- Modify: `pyproject.toml`
- Create: `litvar_link/py.typed`

- [ ] **Step 1: Replace the `[build-system]` table.**
   Replace lines 1–3 (the setuptools build-system) with:
   ```toml
   [build-system]
   requires = ["hatchling"]
   build-backend = "hatchling.build"
   ```

- [ ] **Step 2: Bump version and Python floor in `[project]`.**
   In the `[project]` table set:
   ```toml
   version = "1.0.0"
   requires-python = ">=3.12"
   ```
   (was `version = "0.1.0"`, `requires-python = ">=3.9"`).

- [ ] **Step 3: Rewrite the `classifiers` list to 3.12/3.13 only (NOT 3.14).**
   Replace the existing `classifiers = [...]` block with:
   ```toml
   classifiers = [
       "Development Status :: 5 - Production/Stable",
       "Intended Audience :: Science/Research",
       "Intended Audience :: Developers",
       "License :: OSI Approved :: MIT License",
       "Operating System :: OS Independent",
       "Programming Language :: Python :: 3",
       "Programming Language :: Python :: 3.12",
       "Programming Language :: Python :: 3.13",
       "Topic :: Scientific/Engineering :: Bio-Informatics",
       "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
       "Topic :: Software Development :: Libraries :: Python Modules",
       "Typing :: Typed",
   ]
   ```
   (Drops the `3.9`/`3.10`/`3.11` classifiers; no `3.14` until CI tests it. `Beta` → `Production/Stable` to match the 1.0.0 bump.)

- [ ] **Step 4: Replace the setuptools packaging tables with a hatch wheel target.**
   Delete the three setuptools tables (`[tool.setuptools]`, `[tool.setuptools.packages.find]`, `[tool.setuptools.package-data]`) and add, immediately after the `[project.scripts]` block (created in Task 3) or after `[project.urls]`:
   ```toml
   [tool.hatch.build.targets.wheel]
   packages = ["litvar_link"]
   include = ["server.py", "mcp_server.py"]
   ```

- [ ] **Step 5: Create the real `py.typed` marker.**
   Create `litvar_link/py.typed` as an **empty** file (PEP 561 marker; content is intentionally zero bytes):
   ```bash
   : > litvar_link/py.typed
   ```

- [ ] **Step 6: Verify TOML parses.**
   ```bash
   uv run --no-project python -c "import tomllib,sys; tomllib.load(open('pyproject.toml','rb')); print('pyproject OK')"
   ```
   Expected output: `pyproject OK`
   (If `uv run --no-project` is unavailable, use any Python 3.11+: `python3.12 -c "import tomllib; tomllib.load(open('pyproject.toml','rb')); print('pyproject OK')"`.)

- [ ] **Final step: Commit**
   ```bash
   git add pyproject.toml litvar_link/py.typed
   git commit -m "build: migrate to hatchling, py3.12 floor, version 1.0.0

   Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
   ```

---

### Task 2: Restructure dependencies (runtime + PEP 735 dev group; drop otel/mkdocs)

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Rewrite the runtime `dependencies` list.**
   Replace the entire `dependencies = [...]` array with the version-capped house set (keeps the existing runtime stack; promotes `gunicorn`/`prometheus-client`/`asgi-correlation-id`; keeps `typer` — the CLI→typer swap is P3; argparse stays for now):
   ```toml
   dependencies = [
       # Web framework and API
       "fastapi>=0.110.0,<1.0.0",
       "uvicorn[standard]>=0.29.0,<1.0.0",
       "gunicorn>=22.0.0,<24.0.0",
       "pydantic>=2.7.0,<3.0.0",
       "pydantic-settings>=2.2.0,<3.0.0",
       # HTTP client and networking
       "httpx>=0.27.0,<1.0.0",
       # MCP integration
       "mcp[cli]>=1.0.0,<2.0.0",
       "fastmcp>=0.2.0,<4.0.0",
       # Caching and performance
       "async-lru>=2.0.4,<3.0.0",
       # Logging, correlation, and monitoring
       "structlog>=24.1.0,<26.0.0",
       "asgi-correlation-id>=4.3.0,<5.0.0",
       "prometheus-client>=0.20.0,<1.0.0",
       "orjson>=3.10.0,<4.0.0",
       # CLI interface
       "typer>=0.12.0,<1.0.0",
       "rich>=13.7.0,<16.0.0",
       # Utilities
       "python-multipart>=0.0.9,<1.0.0",
   ]
   ```
   Notes: `mcp` gains the `[cli]` extra to match siblings; `typer` loses the `[rich]` extra (rich is already a direct dep). The wide `fastmcp` cap (`<4.0.0`) tolerates the major-version jump the spec flags as Open Item #4 — the actual facade rewrite/pin happens in P3.

- [ ] **Step 2: Delete the `[project.optional-dependencies]` block entirely.**
   Remove the whole `[project.optional-dependencies]` table (the `dev`, `production`, `all` groups). The OpenTelemetry deps go away here (grep confirmed unused: `grep -rn "opentelemetry\|otel" litvar_link` → 0 matches), as do the `mkdocs*` docs deps (no `mkdocs.yml` exists).

- [ ] **Step 3: Add the PEP 735 `[dependency-groups]` dev group.**
   Add immediately after the `dependencies = [...]` array (before `[project.urls]`):
   ```toml
   [dependency-groups]
   dev = [
       "pytest>=8.0.0,<10.0.0",
       "pytest-asyncio>=0.23.0,<2.0.0",
       "pytest-cov>=4.0.0,<8.0.0",
       "pytest-mock>=3.12.0,<4.0.0",
       "pytest-xdist>=3.6.0,<4.0.0",
       "respx>=0.22.0,<1.0.0",
       "ruff>=0.8.0,<1.0.0",
       "mypy>=1.10.0,<3.0.0",
       "pre-commit>=4.0.0,<5.0.0",
   ]
   ```

- [ ] **Step 2.5 verification (re-confirm grep before deleting otel):** record the result in the commit body.
   ```bash
   grep -rn "opentelemetry\|otel" litvar_link; echo "exit=$?"
   ```
   Expected output: no lines, `exit=1`.

- [ ] **Step 4: Verify TOML still parses.**
   ```bash
   python3.12 -c "import tomllib; d=tomllib.load(open('pyproject.toml','rb')); print('deps', len(d['project']['dependencies']), 'dev', len(d['dependency-groups']['dev']))"
   ```
   Expected output: `deps 17 dev 9`

- [ ] **Final step: Commit**
   ```bash
   git add pyproject.toml
   git commit -m "build: move dev deps to PEP 735 group, drop unused OpenTelemetry/mkdocs

   OpenTelemetry optional group removed: grep -rn 'opentelemetry|otel' litvar_link
   returned 0 matches (exit 1), confirming it was never wired into code.
   Promoted gunicorn/prometheus-client/asgi-correlation-id to runtime deps.

   Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
   ```

---

### Task 3: Fix console-script entry points

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Rewrite `[project.scripts]`.**
   Replace the existing block:
   ```toml
   [project.scripts]
   litvar-link = "litvar_link.cli:main"
   litvar-mcp = "mcp_server:main"
   ```
   with:
   ```toml
   [project.scripts]
   litvar-link = "litvar_link.cli:main"
   litvar-link-mcp = "mcp_server:main"
   ```
   (`litvar-link` stays `:main` — the swap to `:app` happens in P3 with the typer migration. Only the second script is renamed `litvar-mcp` → `litvar-link-mcp` to match house naming.)

- [ ] **Step 2: Verify both targets are importable module paths.**
   ```bash
   test -f litvar_link/cli.py && grep -q "^def main" litvar_link/cli.py && echo "cli:main OK"
   test -f mcp_server.py && grep -q "^def main" mcp_server.py && echo "mcp_server:main OK"
   ```
   Expected output:
   ```
   cli:main OK
   mcp_server:main OK
   ```

- [ ] **Final step: Commit**
   ```bash
   git add pyproject.toml
   git commit -m "build: rename mcp console script to litvar-link-mcp

   Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
   ```

---

### Task 4: Rewrite ruff config to house style (no C901/PLR0915 yet)

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Replace the entire ruff block.**
   Delete everything from `# Ruff configuration ...`/`[tool.ruff]` through the end of `[tool.ruff.format]` (the old config selects ~50 rule groups including `D`, `ANN`, `C901`, `PLR0915`). Replace with the lean house config:
   ```toml
   [tool.ruff]
   line-length = 100
   target-version = "py312"

   [tool.ruff.lint]
   extend-select = ["E", "W", "F", "I", "N", "UP", "B", "C4", "S", "T20", "SIM", "RUF"]
   ignore = ["S101", "E501"]

   [tool.ruff.format]
   quote-style = "double"
   indent-style = "space"
   line-ending = "lf"

   [tool.ruff.lint.per-file-ignores]
   "tests/**/*" = ["S101", "T20"]
   ```
   **Do NOT add `C901` or `PLR0915`** (nor `[tool.ruff.lint.mccabe]`/`[tool.ruff.lint.pylint]`) — the spec defers them and the per-function line cap to P3. They would block the as-yet-unsplit god files.

- [ ] **Step 2: Verify ruff loads the config (config-only check, no findings yet).**
   ```bash
   uv run ruff check --show-settings litvar_link >/dev/null 2>&1 && echo "ruff config OK" || uv run ruff check litvar_link 2>&1 | head -3
   ```
   Expected: `ruff config OK` (or, if the venv isn't synced yet, a lint result — config parse errors would print a `ruff failed to parse` line instead, which must be absent). Findings are fixed in Task 10; this step only proves the TOML is valid ruff config.

- [ ] **Final step: Commit**
   ```bash
   git add pyproject.toml
   git commit -m "build: adopt house ruff config (line-length 100, py312, lean rule set)

   Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
   ```

---

### Task 5: Rewrite mypy, pytest, and coverage config

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Replace the `[tool.mypy]` block.**
   Replace the existing mypy config (currently `python_version = "3.9"`) with:
   ```toml
   [tool.mypy]
   python_version = "3.12"
   strict = true
   warn_unreachable = true
   warn_unused_ignores = true
   warn_redundant_casts = true
   show_error_codes = true
   show_column_numbers = true
   pretty = true
   exclude = [
       ".*site-packages.*",
       ".*/venv/.*",
       ".*/.venv/.*",
       "htmlcov/.*",
   ]

   [[tool.mypy.overrides]]
   module = [
       "uvicorn.*",
       "fastmcp.*",
       "mcp.*",
       "async_lru.*",
       "orjson.*",
       "structlog.*",
       "rich.*",
       "typer.*",
       "asgi_correlation_id.*",
       "prometheus_client.*",
   ]
   ignore_missing_imports = true
   ```
   (Ports the existing per-module `ignore_missing_imports` overrides; adds the two newly-promoted untyped runtime deps `asgi_correlation_id`/`prometheus_client`; keeps `strict=true`; adds the venv/site-packages/htmlcov excludes.)

- [ ] **Step 2: Replace the `[tool.pytest.ini_options]` block (lean addopts, coverage flags removed).**
   ```toml
   [tool.pytest.ini_options]
   testpaths = ["tests"]
   asyncio_mode = "auto"
   asyncio_default_fixture_loop_scope = "function"
   addopts = [
       "--strict-markers",
       "-ra",
       "--import-mode=importlib",
   ]
   markers = [
       "slow: marks tests as slow (deselect with '-m \"not slow\"')",
       "integration: marks tests as integration tests",
   ]
   ```
   Coverage flags (`--cov*`, `--cov-fail-under`) are intentionally **removed** from `addopts` — they live in `make test-cov` so intermediate refactor commits aren't blocked by the floor. `--strict-config` and the `filterwarnings`/`api`/`unit` markers from the old config are dropped to match the house spine.

- [ ] **Step 3: Replace the coverage configuration.**
   ```toml
   [tool.coverage.run]
   source = ["litvar_link"]
   branch = true
   omit = [
       "tests/*",
       "*/tests/*",
       "litvar_link/__main__.py",
   ]

   [tool.coverage.report]
   fail_under = 90
   precision = 2
   show_missing = true
   skip_empty = true
   exclude_also = [
       "pragma: no cover",
       "def __repr__",
       "if self.debug:",
       "if settings.DEBUG",
       "raise AssertionError",
       "raise NotImplementedError",
       "if 0:",
       "if __name__ == .__main__.:",
       "class .*\\bProtocol\\):",
       "@(abc\\.)?abstractmethod",
   ]

   [tool.coverage.html]
   directory = "htmlcov"

   [tool.coverage.xml]
   output = "coverage.xml"
   ```

- [ ] **Step 4: Verify TOML parses and the key knobs are set.**
   ```bash
   python3.12 -c "import tomllib; d=tomllib.load(open('pyproject.toml','rb')); m=d['tool']['mypy']; c=d['tool']['coverage']; print('mypy', m['python_version'], m['strict'], '| cov fail_under', c['report']['fail_under'], 'branch', c['run']['branch'])"
   ```
   Expected output: `mypy 3.12 True | cov fail_under 90 branch True`

- [ ] **Final step: Commit**
   ```bash
   git add pyproject.toml
   git commit -m "build: retarget mypy to py3.12, lean pytest addopts, branch coverage fail_under 90

   Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
   ```

---

### Task 6: Remove `.flake8` and add `.python-version`

**Files:**
- Delete: `.flake8`
- Create: `.python-version`

- [ ] **Step 1: Delete the conflicting flake8 config.**
   ```bash
   git rm .flake8
   ```
   (`.flake8` set `max-line-length = 120`, conflicting with ruff's 100, and referenced a non-existent `scripts/` per-file-ignore.)

- [ ] **Step 2: Create `.python-version` pinning 3.12.**
   File `.python-version` (exact content, single line plus trailing newline):
   ```
   3.12
   ```

- [ ] **Step 3: Verify uv resolves a real 3.12 interpreter.**
   ```bash
   uv python find 3.12
   ```
   Expected: a path to a CPython 3.12 (e.g. `/home/bernt-popp/miniforge3/bin/python3` or `.../cpython-3.12.*`). If it errors, run `uv python install 3.12` first.

- [ ] **Final step: Commit**
   ```bash
   git add .python-version
   git commit -m "build: drop .flake8, pin .python-version to 3.12

   Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
   ```

---

### Task 7: Add the file-size budget script and allowlist

**Files:**
- Create: `scripts/check_file_size.py`
- Create: `.loc-allowlist`

- [ ] **Step 1: Create `scripts/check_file_size.py`.**
   Ported verbatim from the siblings, retargeted to `litvar_link`. **P0 scope = file-size check only.** A NOTE for P3: this script will be EXTENDED in P3 with an AST per-function line check (~60-line cap, ruff has no line-count rule); P0 ships only the 600-line per-file check.
   ```python
   """Fail on Python source files exceeding the per-file line budget.

   Rationale: large modules concentrate complexity and slow LLM-assisted
   refactors. See AGENTS.md "File Size Discipline" for the policy.

   The default budget is 600 lines. Existing oversized files are grandfathered
   via `.loc-allowlist` (one path per line, repo-root-relative). Files in the
   allowlist must not grow beyond their listed ceiling.

   Usage:
       python scripts/check_file_size.py            # check all configured paths
       python scripts/check_file_size.py path/...   # check specific paths
   """

   from __future__ import annotations

   import argparse
   import sys
   from pathlib import Path

   DEFAULT_LIMIT = 600
   DEFAULT_TARGETS = (
       Path("litvar_link"),
       Path("server.py"),
       Path("mcp_server.py"),
   )
   ALLOWLIST_PATH = Path(".loc-allowlist")


   def _load_allowlist() -> dict[str, int]:
       """Return {relative_path: ceiling_loc} from `.loc-allowlist`.

       Each non-comment, non-empty line is `path[:ceiling]`. When the ceiling is
       omitted, the current file length at first run becomes the ceiling.
       """
       if not ALLOWLIST_PATH.exists():
           return {}
       entries: dict[str, int] = {}
       for raw in ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines():
           line = raw.split("#", 1)[0].strip()
           if not line:
               continue
           if ":" in line:
               path, ceiling = line.split(":", 1)
               entries[path.strip()] = int(ceiling.strip())
           else:
               entries[line] = -1
       return entries


   def _iter_python_files(targets: list[Path]) -> list[Path]:
       files: list[Path] = []
       for target in targets:
           if not target.exists():
               continue
           if target.is_file() and target.suffix == ".py":
               files.append(target)
               continue
           files.extend(sorted(target.rglob("*.py")))
       return files


   def _line_count(path: Path) -> int:
       with path.open("rb") as handle:
           return sum(1 for _ in handle)


   def main(argv: list[str]) -> int:
       parser = argparse.ArgumentParser(description=__doc__)
       parser.add_argument("paths", nargs="*", type=Path)
       parser.add_argument(
           "--limit",
           type=int,
           default=DEFAULT_LIMIT,
           help=f"max lines per file for unallowlisted modules (default: {DEFAULT_LIMIT})",
       )
       args = parser.parse_args(argv)

       targets = args.paths or list(DEFAULT_TARGETS)
       allowlist = _load_allowlist()
       violations: list[str] = []
       grew: list[str] = []

       for path in _iter_python_files(targets):
           rel = path.as_posix()
           loc = _line_count(path)
           if rel in allowlist:
               ceiling = allowlist[rel]
               if ceiling > 0 and loc > ceiling:
                   grew.append(
                       f"  {rel}: {loc} lines (grandfathered ceiling {ceiling}). "
                       f"Decompose or lower the entry in .loc-allowlist."
                   )
               continue
           if loc > args.limit:
               violations.append(
                   f"  {rel}: {loc} lines (limit {args.limit}). "
                   f"Split into smaller modules. See AGENTS.md 'File Size Discipline'."
               )

       if not violations and not grew:
           return 0

       if violations:
           sys.stderr.write("\nFiles exceeding the per-file line budget:\n")
           sys.stderr.write("\n".join(violations) + "\n")
       if grew:
           sys.stderr.write("\nGrandfathered files that have grown past their ceiling:\n")
           sys.stderr.write("\n".join(grew) + "\n")
       sys.stderr.write(
           "\nAdd new files to .loc-allowlist with an explicit ceiling only as a "
           "temporary exception with a tracked decomposition plan.\n"
       )
       return 1


   if __name__ == "__main__":
       raise SystemExit(main(sys.argv[1:]))
   ```

- [ ] **Step 2: Create `.loc-allowlist` (comment-only — nothing exceeds 600).**
   Verified max production file = `litvar_link/api/client.py` at **558 lines** < 600, so the allowlist is empty of entries:
   ```
   # Grandfathered Python modules exceeding the 600-LOC budget.
   #
   # Format: <repo-relative path>:<ceiling LOC>
   # - Ceiling is the file's current line count at allowlist time.
   # - Files may shrink freely; growing past the ceiling fails CI.
   # - Removing an entry after a successful split is the goal.
   #
   # No current production Python module exceeds the 600-line budget
   # (largest: litvar_link/api/client.py at 558 lines, verified 2026-06-01).
   ```

- [ ] **Step 3: Run the budget check — it must pass.**
   ```bash
   python3.12 scripts/check_file_size.py; echo "exit=$?"
   ```
   Expected output: `exit=0` (no violations, no stderr).

- [ ] **Final step: Commit**
   ```bash
   git add scripts/check_file_size.py .loc-allowlist
   git commit -m "build: add 600-line file-size budget check and allowlist

   Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
   ```

---

### Task 8: Add pre-commit config and editorconfig

**Files:**
- Create: `.pre-commit-config.yaml`
- Create: `.editorconfig`

- [ ] **Step 1: Create `.pre-commit-config.yaml`.**
   Ported from the siblings; local `mypy`/`file-size-budget` hooks run via `uv run`, scoped to `litvar_link`. The `files:` regex for the size hook matches litvar's targets.
   ```yaml
   repos:
     - repo: https://github.com/pre-commit/pre-commit-hooks
       rev: v5.0.0
       hooks:
         - id: trailing-whitespace
         - id: end-of-file-fixer
         - id: check-yaml
         - id: check-toml
         - id: check-json
         - id: check-added-large-files
         - id: check-merge-conflict
         - id: debug-statements

     - repo: https://github.com/astral-sh/ruff-pre-commit
       rev: v0.8.6
       hooks:
         - id: ruff
           args: [--fix, --exit-non-zero-on-fix]
         - id: ruff-format

     - repo: local
       hooks:
         - id: mypy
           name: mypy
           entry: uv run mypy litvar_link server.py mcp_server.py
           language: system
           pass_filenames: false

         - id: file-size-budget
           name: per-file line budget (see AGENTS.md "File Size Discipline")
           entry: uv run python scripts/check_file_size.py
           language: system
           pass_filenames: false
           files: ^(litvar_link/|server\.py$|mcp_server\.py$|\.loc-allowlist$)
   ```

- [ ] **Step 2: Create `.editorconfig`.**
   Ported verbatim from autopvs1-link:
   ```ini
   root = true

   [*]
   charset = utf-8
   end_of_line = lf
   insert_final_newline = true
   trim_trailing_whitespace = true
   indent_style = space
   indent_size = 4

   [*.{yml,yaml,toml,json,md}]
   indent_size = 2

   [Makefile]
   indent_style = tab
   ```

- [ ] **Step 3: Validate the pre-commit YAML parses.**
   ```bash
   python3.12 -c "import yaml,sys; yaml.safe_load(open('.pre-commit-config.yaml')); print('pre-commit YAML OK')"
   ```
   Expected output: `pre-commit YAML OK`
   (If PyYAML isn't importable outside the venv, run `uv run python -c "import yaml; yaml.safe_load(open('.pre-commit-config.yaml')); print('pre-commit YAML OK')"` after Task 10's sync.)

- [ ] **Final step: Commit**
   ```bash
   git add .pre-commit-config.yaml .editorconfig
   git commit -m "build: add pre-commit hooks and editorconfig

   Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
   ```

---

### Task 9: Add the Makefile

**Files:**
- Create: `Makefile`

- [ ] **Step 1: Create `Makefile`.**
   Ported from autopvs1-link, retargeted to `litvar_link`, with `dev`/`mcp-serve`/`mcp-serve-http` adapted to litvar's **actual** entry points. NOTE: litvar's `server.py` is a bare `uvicorn.run` (no CLI flags) and the unified/http/mcp transports live behind `litvar-link serve {unified,http,mcp}` (argparse). So `dev`/`mcp-serve-http` invoke `python -m litvar_link.cli serve unified ...` (the documented unified path), and `mcp-serve` runs `python mcp_server.py` (stdio), matching litvar's transports. `ci-local = format-check lint-ci lint-loc typecheck-fast test-fast`. **Tabs, not spaces, in recipe bodies.**
   ```makefile
   .PHONY: help install lock upgrade sync format format-check lint lint-ci lint-fix lint-loc typecheck typecheck-fast typecheck-stop typecheck-fresh test test-fast test-unit test-integration test-cov test-all check ci-local precommit clean dev mcp-serve mcp-serve-http docker-build docker-up docker-down docker-logs docker-prod-config docker-npm-config

   DOCKER_COMPOSE := $(shell if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then echo "docker compose"; elif command -v docker-compose >/dev/null 2>&1; then echo "docker-compose"; else echo "docker compose"; fi)

   .DEFAULT_GOAL := help

   help: ## Display this help message
   	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z0-9_-]+:.*?##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

   install: ## Install project and development dependencies with uv
   	uv sync --group dev

   sync: install ## Alias for install

   lock: ## Resolve and update uv.lock
   	uv lock

   upgrade: ## Upgrade locked dependencies
   	uv lock --upgrade

   format: ## Format Python code
   	uv run ruff format litvar_link tests server.py mcp_server.py

   format-check: ## Check formatting without writing
   	uv run ruff format --check litvar_link tests server.py mcp_server.py

   lint: ## Lint Python code
   	uv run ruff check litvar_link tests server.py mcp_server.py

   lint-ci: ## Lint Python code without modifying files
   	uv run ruff check litvar_link tests server.py mcp_server.py --output-format=github

   lint-fix: ## Lint and apply safe fixes
   	uv run ruff check litvar_link tests server.py mcp_server.py --fix

   lint-loc: ## Enforce per-file line budget (see AGENTS.md "File Size Discipline")
   	uv run python scripts/check_file_size.py

   typecheck: ## Type check package
   	uv run mypy litvar_link server.py mcp_server.py

   typecheck-fast: ## Type check with mypy daemon and fallback
   	@tmp_log=$$(mktemp); \
   	if uv run dmypy run -- litvar_link server.py mcp_server.py >$$tmp_log 2>&1; then \
   		cat $$tmp_log; \
   	elif grep -Eq "Daemon crashed!|INTERNAL ERROR" $$tmp_log; then \
   		echo "dmypy crashed; retrying with a fresh daemon..."; \
   		uv run dmypy stop >/dev/null 2>&1 || true; \
   		if uv run dmypy run -- litvar_link server.py mcp_server.py >$$tmp_log 2>&1; then \
   			cat $$tmp_log; \
   		else \
   			cat $$tmp_log; \
   			echo "Falling back to plain mypy..."; \
   			uv run dmypy stop >/dev/null 2>&1 || true; \
   			uv run mypy litvar_link server.py mcp_server.py; \
   		fi; \
   	else \
   		cat $$tmp_log; \
   		rm -f $$tmp_log; \
   		exit 1; \
   	fi; \
   	rm -f $$tmp_log

   typecheck-stop: ## Stop mypy daemon
   	uv run dmypy stop

   typecheck-fresh: ## Clear mypy cache and run typecheck
   	rm -rf .mypy_cache
   	uv run mypy litvar_link server.py mcp_server.py

   test: ## Run tests quickly
   	uv run pytest tests -q

   test-fast: ## Run tests in parallel with pytest-xdist
   	uv run pytest tests -q -n auto

   test-unit: ## Run unit tests in parallel
   	uv run pytest tests -q -n auto -m "not integration and not slow"

   test-integration: ## Run integration tests serially
   	uv run pytest tests -q -m "integration"

   test-cov: ## Run tests with coverage
   	uv run pytest tests --cov=litvar_link --cov-report=term-missing --cov-report=html --cov-report=xml --cov-fail-under=90

   test-all: test-cov ## Alias for full test run with coverage

   check: format lint ## Format and lint

   ci-local: format-check lint-ci lint-loc typecheck-fast test-fast ## Run fast local CI-equivalent checks

   precommit: ci-local ## Run checks expected before commit

   clean: ## Remove local caches and generated reports
   	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage coverage.xml

   dev: ## Start unified REST + MCP development server
   	uv run python -m litvar_link.cli serve unified --host 127.0.0.1 --port 8000

   mcp-serve: ## Start local stdio MCP server
   	uv run python mcp_server.py

   mcp-serve-http: ## Start hosted MCP endpoint with REST API
   	uv run python -m litvar_link.cli serve unified --host 127.0.0.1 --port 8000

   docker-build: ## Build Docker image
   	$(DOCKER_COMPOSE) -f docker/docker-compose.yml build

   docker-up: ## Start Docker development stack
   	$(DOCKER_COMPOSE) -f docker/docker-compose.yml up -d

   docker-down: ## Stop Docker development stack
   	$(DOCKER_COMPOSE) -f docker/docker-compose.yml down

   docker-logs: ## Follow Docker logs
   	$(DOCKER_COMPOSE) -f docker/docker-compose.yml logs -f

   docker-prod-config: ## Render production Compose configuration
   	$(DOCKER_COMPOSE) -f docker/docker-compose.yml -f docker/docker-compose.prod.yml config

   docker-npm-config: ## Render NPM Compose configuration
   	$(DOCKER_COMPOSE) -f docker/docker-compose.yml -f docker/docker-compose.prod.yml -f docker/docker-compose.npm.yml --env-file .env.npm.example config
   ```
   NOTE on `docker-npm-config`: litvar still ships `.env.npm.example` (the rename to `.env.docker.example` is a P3 task), so the `--env-file` here references `.env.npm.example`. P3 must update this line when the file is renamed.

- [ ] **Step 2: Verify the recipe bodies are tab-indented (Make requires tabs).**
   ```bash
   grep -nP '^    [^ ]' Makefile && echo "ERROR: space-indented recipe lines found" || echo "tab-indentation OK"
   ```
   Expected output: `tab-indentation OK`

- [ ] **Step 3: Verify `make help` renders the target list.**
   ```bash
   make help | head -5
   ```
   Expected: a `Usage:` banner followed by colorized `make <target>` rows (e.g. `install`, `lock`). No `Makefile:NN: *** missing separator` error.

- [ ] **Final step: Commit**
   ```bash
   git add Makefile
   git commit -m "build: add house Makefile with ci-local gate

   Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
   ```

---

### Task 10: Generate and commit the lockfile

**Files:**
- Create (generated): `uv.lock`
- Modify: `.gitignore` (only if it currently excludes `uv.lock` — the current `.gitignore` has `#uv.lock` commented out, so no change needed; verify in Step 1)

- [ ] **Step 1: Confirm `uv.lock` is NOT gitignored.**
   ```bash
   grep -nE '^\s*uv\.lock' .gitignore && echo "WARNING: uv.lock is ignored — un-ignore it" || echo "uv.lock not ignored (OK)"
   ```
   Expected output: `uv.lock not ignored (OK)` (the entry in `.gitignore` is the commented `#uv.lock`).

- [ ] **Step 2: Generate the lockfile.**
   `uv` is installed (verified at `/home/bernt-popp/.local/bin/uv`). Run:
   ```bash
   uv lock
   ```
   Expected: `Resolved N packages in ...`; a `uv.lock` file appears at repo root.
   **If `uv` is NOT available** on a given machine, document the fallback in the commit and use one of:
   ```bash
   pipx run uv lock            # ephemeral
   # or install uv first:
   curl -LsSf https://astral.sh/uv/install.sh | sh && uv lock
   ```

- [ ] **Step 3: Sync the dev environment so subsequent `uv run` calls work.**
   ```bash
   uv sync --group dev
   uv run python -c "import sys; print('venv python', sys.version.split()[0])"
   ```
   Expected: a `Resolved/Installed` summary, then `venv python 3.12.x` (uv picks 3.12 because of `.python-version` + `requires-python>=3.12`).

- [ ] **Step 4: Sanity-check the package imports under the new env.**
   ```bash
   uv run python -c "import litvar_link; import mcp_server; import server; print('imports OK')"
   ```
   Expected output: `imports OK`

- [ ] **Final step: Commit**
   ```bash
   git add uv.lock
   git commit -m "build: generate and commit uv.lock

   Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
   ```

---

### Task 11: Apply mechanical lint/type fixes and make `ci-local` + `test-cov` green

**Files:**
- Modify (mechanical, autofix): `litvar_link/exceptions.py`, `litvar_link/models/{variants,responses,requests,endpoint_specific}.py`, `litvar_link/api/client.py`, `litvar_link/utils/caching.py`, `litvar_link/app.py`, `litvar_link/cli.py`
- Modify (mechanical, manual): `litvar_link/api/routes/{genes,publications,sensor,variants}.py`
- Modify (mechanical): `tests/**`

This task ends ONLY when `make ci-local` AND `make test-cov` both exit 0 and coverage ≥ 90.

- [ ] **Step 1: Apply ruff autofixes (formatting + safe lint fixes).**
   ```bash
   uv run ruff format litvar_link tests server.py mcp_server.py
   uv run ruff check litvar_link tests server.py mcp_server.py --fix
   ```
   This auto-resolves (verified counts): **UP045 ×92** (`Optional[X]`→`X | None` across the `models/` + `exceptions.py`), **UP035 ×2** (`Self` from `typing` in `api/client.py`, `Callable` from `collections.abc` in `utils/caching.py`), **RUF100 ×6** (redundant `# noqa: E501` in `api/client.py`, `app.py`, `cli.py`, `models/responses.py`), and **I001 ×5** (import sorting in `api/routes/*`).

- [ ] **Step 2: Manually fix the 15 `B904` findings in route handlers.**
   In each `except ... as e:` block that does `raise HTTPException(...)`, chain the cause. Locations (verified): `api/routes/genes.py` (×3), `api/routes/publications.py` (×3), `api/routes/sensor.py` (×3), `api/routes/variants.py` (×6). Pattern — change:
   ```python
   except ValidationError as e:
       logger.warning(...)
       raise HTTPException(status_code=400, detail=str(e))
   except LitVarAPIError as e:
       logger.exception("API error ...", error=str(e))
       raise HTTPException(status_code=502, detail="LitVar2 API error")
   except Exception as e:
       logger.exception(...)
       raise HTTPException(status_code=500, detail="Internal server error")
   ```
   to append `from e` to each `raise`:
   ```python
   except ValidationError as e:
       logger.warning(...)
       raise HTTPException(status_code=400, detail=str(e)) from e
   except LitVarAPIError as e:
       logger.exception("API error ...", error=str(e))
       raise HTTPException(status_code=502, detail="LitVar2 API error") from e
   except Exception as e:
       logger.exception(...)
       raise HTTPException(status_code=500, detail="Internal server error") from e
   ```
   This is purely additive (`from e` preserves the existing behavior and the existing exception type) and is the same fix the route handlers will keep through the P3 error-handler refactor.

- [ ] **Step 3: Fix the remaining manual test-file findings.**
   These surface because the house config narrows the old blanket `S`/`PLR`/`ANN`/`D` test ignores to just `S101`/`T20`:
   - **`F401` ×1** — `tests/test_logging.py:242`: remove the unused `import orjson` (or, if it is a deliberate availability probe, rewrite as `importlib.util.find_spec("orjson")`).
   - **`S104` ×8** — test files binding to `"0.0.0.0"` (in `tests/test_cli.py` and `tests/test_server_manager.py`): append `  # noqa: S104` to each offending line (intentional all-interfaces host in a test fixture).
   - **`RUF043` ×2** — `tests/test_api/test_client.py:683,704`: the `pytest.raises(..., match="...")` pattern contains regex metacharacters; prefix the pattern string with `r` (make it a raw string) or `re.escape(...)` it.
   - **`RUF012` ×30** — mutable class attributes in test fixture/data classes (e.g. `tests/fixtures/test_data.py:264`): annotate with `typing.ClassVar`, e.g. `FOO: ClassVar[dict[str, int]] = {...}` (add `from typing import ClassVar`).
   - **`SIM117` ×26** — nested `with` statements in `tests/test_cli.py` and `tests/test_server_manager.py`: combine into a single `with a, b:` statement. If a combination hurts readability for a long mock stack, `# noqa: SIM117` on the outer `with` is acceptable for test code.

- [ ] **Step 4: Iterate ruff to zero findings.**
   ```bash
   uv run ruff check litvar_link tests server.py mcp_server.py
   uv run ruff format --check litvar_link tests server.py mcp_server.py
   ```
   Expected: `All checks passed!` and `NN files already formatted`. Re-run Steps 2–3 until clean.

- [ ] **Step 5: Run mypy (strict, py312) and fix any retarget findings.**
   ```bash
   uv run mypy litvar_link server.py mcp_server.py
   ```
   Expected: `Success: no issues found in NN source files`. The codebase is already `strict`-clean on py39; the py39→py312 retarget is not expected to add errors. If any appear, they will be narrow modern-typing nits (e.g. an `X | None` annotation now needing the value-side default, or a redundant cast flagged by `warn_redundant_casts`) — fix them in-place; do **not** add `# type: ignore` blanket suppressions or per-module override relaxations (those are a P3 concern if ever needed).

- [ ] **Step 6: Run the full local CI gate.**
   ```bash
   make ci-local
   ```
   Expected: `format-check`, `lint-ci`, `lint-loc`, `typecheck-fast`, and `test-fast` all pass; final exit 0. (`typecheck-fast` uses the dmypy daemon with a plain-mypy fallback — a first-run daemon spin-up is normal.)

- [ ] **Step 7: Run coverage and confirm ≥ 90.**
   ```bash
   make test-cov
   ```
   Expected: pytest summary with `Required test coverage of 90% reached. Total coverage: NN.NN%` (baseline ~94%), exit 0, `htmlcov/` and `coverage.xml` written.

- [ ] **Final step: Commit**
   ```bash
   git add litvar_link tests
   git commit -m "build: apply mechanical ruff/mypy fixes for py3.12 house config

   - UP045/UP035/RUF100/I001 via ruff --fix (Optional->X|None, modern imports,
     redundant noqa removal, import sorting)
   - B904: chain HTTPException raises with 'from e' in route handlers
   - test-only RUF012/SIM117/S104/RUF043/F401 fixes surfaced by the lean S/RUF set
   make ci-local and make test-cov both green; coverage >= 90.

   Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
   ```

---

## Done criteria (whole phase)

- `make ci-local` and `make test-cov` both exit 0 on a clean `uv` checkout; coverage ≥ 90.
- `pyproject.toml` uses hatchling, `requires-python>=3.12`, version `1.0.0`, 3.12/3.13 classifiers, PEP 735 dev group, house ruff/mypy/pytest/coverage config (no `C901`/`PLR0915`).
- `litvar_link/py.typed`, `.python-version`, `Makefile`, `scripts/check_file_size.py`, `.loc-allowlist`, `.pre-commit-config.yaml`, `.editorconfig`, and `uv.lock` exist and are committed; `.flake8` is removed.
- No application logic changed beyond the mechanical lint/type fixes in Task 11.

## Cross-phase notes (what P1/P2/P3 depend on from P0)

- **P1 (docs):** `AGENTS.md` must reference `make ci-local` (defined here) and the file/function size discipline (`scripts/check_file_size.py`, 600-line cap). The function-size guards are NOT active yet — P1 docs should describe them as enforced *from P3*.
- **P2 (CI):** `ci.yml` calls `uv sync --group dev --frozen` (relies on the committed `uv.lock`) then `make ci-local` + `make test-cov` (both defined here). The `[dependency-groups] dev` group name (`dev`) is the contract.
- **P3 (refactor):** (a) `scripts/check_file_size.py` gets EXTENDED with the AST per-function (~60-line) check; (b) ruff config gains `C901` + `PLR0915` (+ `[tool.ruff.lint.mccabe] max-complexity=10`, `[tool.ruff.lint.pylint] max-statements=50`, and `C901`/`PLR0915` added to the tests per-file-ignore) — switched on only after the god files are split; (c) the `litvar-link` console script flips `:main`→`:app` with the typer migration; (d) the Makefile `docker-npm-config` `--env-file .env.npm.example` line must change to `.env.docker.example` when that file is renamed; (e) the wide `fastmcp>=0.2.0,<4.0.0` cap should be tightened to the actually-used major when the explicit MCP facade lands.
