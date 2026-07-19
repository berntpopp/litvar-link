# LitVar Runtime Hardening Design

- **Date:** 2026-07-16
- **Status:** Approved for execution under the user's end-to-end release directive

> Historical record — this document records the design as of its date. Current behavior is defined
> by implemented code, standards, release evidence, and tests.

- **Tracking issue:** [#67](https://github.com/berntpopp/litvar-link/issues/67)

## Context

`litvar_link_server` is the only fleet backend whose deployed container is not
confined. The source has a correct hardening block in
`docker/docker-compose.prod.yml`, but the Strato deployment command renders only
`docker/docker-compose.yml` and `docker/docker-compose.npm.yml`. Consequently the
running container has an attested image but a writable root filesystem, retained
capabilities, and no `no-new-privileges` control.

## Decision

Declare the same runtime controls in both Compose files that can be deployed:

- read-only root filesystem;
- a bounded, non-executable `/tmp` tmpfs;
- `no-new-privileges`;
- `cap_drop: [ALL]`; and
- an init process.

The image already runs as the non-root `app` user, so no user override is needed.
The NPM overlay must carry its own controls instead of depending on the unused
production overlay. The base Compose file receives the same controls so local,
production, and NPM paths cannot diverge again.

## Regression Prevention

The current `docker-npm-config` target incorrectly renders base + production +
NPM. Change it to the exact Strato chain, base + NPM. Add a unit guard that reads
both Compose documents, including Compose extension tags, and asserts the five
runtime controls. This catches both a missing declaration and a future return to a
three-file-only validation path.

## Release and Deployment

The current source version and unreleased changelog entry are `6.0.0`; publish
v6.0.0 with this fix rather than skip that pending release line. The release creates
a new attestable image revision, so refresh the router's LitVar inventory/baseline,
release the router, pin both images in Strato, deploy them, and require the complete
fleet attestation to be green.

## Acceptance Criteria

1. `make docker-npm-config` renders precisely the files that Strato deploys and
   includes all five confinement controls.
2. The base and NPM Compose definitions each declare the controls explicitly.
3. `make ci-local` and Compose rendering pass on the LitVar PR.
4. The v6.0.0 tag and container release are signed/published; the router receives
   a matching signed release pin.
5. The deployed LitVar container is healthy and full Strato attestation reports
   every fleet service as both attested and confined.
