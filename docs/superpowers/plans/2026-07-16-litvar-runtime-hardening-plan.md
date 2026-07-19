# LitVar Runtime Hardening Implementation Plan

> Historical record — this document records the plan as of its date. Current behavior is defined
> by implemented code, standards, release evidence, and tests.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every LitVar deployment path runtime-confined and release/deploy the
fix so fleet-wide attestation is green.

**Architecture:** The fix is declarative Compose configuration. A small test reads
the exact base and NPM documents (including Compose-specific YAML tags) and asserts
the confinement contract. The Make target is corrected to render the same two-file
chain used by Strato, then normal release and router drift-control paths publish the
new source revision.

**Tech Stack:** Docker Compose v2, Python 3.12, PyYAML, pytest, uv, GitHub Actions,
GHCR, and Strato deployment management.

**Spec:** `docs/superpowers/specs/2026-07-16-litvar-runtime-hardening-design.md`

---

### Task 1: Make the deployed Compose chain observable and testable

**Files:**
- Create: `tests/unit/test_docker_compose_hardening.py`
- Modify: `Makefile:131-133`

- [ ] **Step 1: Write a failing test**

  Add a test that loads `docker/docker-compose.yml` and
  `docker/docker-compose.npm.yml` with a loader that accepts Compose extension
  tags. For `services.litvar-link`, require `read_only: true`, `init: true`, a
  `/tmp` tmpfs entry, `no-new-privileges:true`, and `ALL` in `cap_drop`. Also
  assert the `docker-npm-config` recipe names the base and NPM files but not the
  production overlay.

- [ ] **Step 2: Verify RED**

  Run: `uv run pytest tests/unit/test_docker_compose_hardening.py -q`

  Expected: failure because neither the base nor NPM document currently declares
  the confinement controls and the Make target includes the unused prod overlay.

- [ ] **Step 3: Correct the Make target**

  Make `docker-npm-config` render only
  `docker/docker-compose.yml -f docker/docker-compose.npm.yml` with the existing
  placeholder image and env file.

### Task 2: Apply the confinement controls to every actual LitVar deploy path

**Files:**
- Modify: `docker/docker-compose.yml`
- Modify: `docker/docker-compose.npm.yml`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add the minimal hardening block**

  In both service definitions, add the standard 64 MiB `/tmp` tmpfs, read-only
  root filesystem, `no-new-privileges:true`, `cap_drop: [ALL]`, and `init: true`.
  Use the existing production overlay's values; do not change ports, networks,
  image pinning, command, resource limits, or the non-root image user.

- [ ] **Step 2: Verify GREEN**

  Run:

  ```bash
  uv run pytest tests/unit/test_docker_compose_hardening.py -q
  make docker-prod-config
  make docker-npm-config
  ```

  Expected: the regression test and both rendered configurations pass; the NPM
  rendering contains each control.

- [ ] **Step 3: Document the release**

  Add the security fix to the existing unpublished `6.0.0` changelog section.
  Do not change the already-consistent `6.0.0` package/lock version.

### Task 3: Verify, review, and publish LitVar v6.0.0

**Files:**
- Verify: repository-wide checks and release artifacts

- [ ] **Step 1: Run the required local gate**

  Run: `make ci-local`

- [ ] **Step 2: Commit and open a focused PR for #67**

  Include the red–green regression evidence, rendered Compose checks, and
  v6.0.0 release intent in the PR body.

- [ ] **Step 3: Merge after all GitHub checks pass**

  Verify the merged commit and post-merge check conclusions before tagging.

- [ ] **Step 4: Sign and push `v6.0.0`**

  Verify the tag signature and wait for the container-release workflow to publish
  a non-draft GitHub release and digest-addressed image manifest.

### Task 4: Re-pin control plane and deploy the complete path

**Files:**
- Modify: `genefoundry-router` release inventory/baseline and release metadata
- Modify: `strato_v6_docker_npm/config/fleet.lock.yaml`

- [ ] **Step 1: Re-pin LitVar in the router**

  Regenerate the verified release candidate and baseline using the v6.0.0 release
  manifest, run the router local gate, review, merge, sign, and publish the router
  patch release.

- [ ] **Step 2: Pin both signed manifests in Strato**

  Use `manage.py pin` for the router and LitVar, verify lockfile tests and
  formatting, open/merge the deployment PR, and deploy the exact digests.

- [ ] **Step 3: Prove production completion**

  Run LitVar and router health checks, then `uv run python scripts/manage.py
  attest`. The command must report every fleet container as image-attested and
  confined. Verify the public LitVar health/MCP endpoint and close #67 with the
  evidence links.
