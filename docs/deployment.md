# Deployment

How LitVar-Link is packaged and run in production. For the full VPS + Nginx
Proxy Manager walkthrough (server preparation, SSL, monitoring scripts,
firewall, troubleshooting) see [`../docker/README.md`](../docker/README.md) —
this page is the entry point and the policy, that one is the long-form runbook.

## Hosted endpoint

The GeneFoundry fleet runs a hosted instance:

```
https://litvar-link.genefoundry.org/mcp
```

It is federated by [`genefoundry-router`](https://github.com/berntpopp/genefoundry-router)
under the `litvar` namespace. The backend is unauthenticated by design and must
be reachable only through the router / reverse proxy — never published directly.

## Compose overlays

All Compose files live in `docker/`. The base file is the development stack;
the others are overlays applied on top of it.

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Base / local development. Direct port access. |
| `docker-compose.dev.yml` | Optional hot-reload development overlay. |
| `docker-compose.prod.yml` | Production: Gunicorn + Uvicorn workers, resource limits, JSON logging. |
| `docker-compose.npm.yml` | Nginx Proxy Manager: no published ports, joins the NPM shared network. |

```bash
make docker-build          # build the image
make docker-up             # start the development stack
make docker-logs           # follow logs
make docker-down           # stop the stack

make docker-prod-config    # render the production Compose config (syntax/policy check)
make docker-npm-config     # render the NPM Compose config
```

### Fleet deploy contract (numeric user)

`docker-compose.npm.yml` is the overlay the GeneFoundry fleet controller
(`strato_v6_docker_npm`) deploys and validates; it declares
`user: "10001:10001"` (this image's own uid:gid from `docker/Dockerfile`) so
the controller's runtime observer can prove the effective uid from `/proc`.
That `user` key must **not** appear in `docker-compose.yml` or
`docker-compose.prod.yml` — the shared release gate forbids it there.
`docker-compose.npm.yml` also declares `expose: ["8000"]` (even though
`ports: !reset []` publishes nothing) because the controller's
`validate-deployed-overlay` gate refuses a rendered model with no `expose`
entry naming the image's container port. `container-release.json`'s
`deployed_compose_files` lists exactly the two files above — the set Strato
deploys — so that gate checks what is actually deployed. `container-
release.yml` and `container-ci.yml` both pin their shared workflow at
`genefoundry-router` `v0.8.5` (`31ea81cee5475fc3655c047c63a89739948f99a9`), and
must move together since both validate `container-release.json` against the
same schema. `tests/unit/test_docker_compose_hardening.py` guards all of the
above. To self-check the merged render before deploying:

```bash
export LITVAR_LINK_IMAGE=ghcr.io/berntpopp/litvar-link@sha256:<digest>
docker compose -f docker/docker-compose.yml -f docker/docker-compose.npm.yml \
  config --format json > /tmp/litvar-link-rendered.json
# from a strato_v6_docker_npm checkout:
uv run python -c "
import sys, json; sys.path.insert(0, 'scripts')
from utils.deployment_preflight import canonical_projection
p = canonical_projection(json.load(open('/tmp/litvar-link-rendered.json')), project='litvar-link')
for n, s in p['services'].items(): print(n, 'user=', s.get('user'))
print('PROJECTION OK')"
```

### The production overlay is digest-pinned

`docker-compose.prod.yml` requires `LITVAR_LINK_IMAGE` and **refuses to render
without it** — this is the container-release standard, not a bug. Real deploys
export the verified digest:

```bash
export LITVAR_LINK_IMAGE=ghcr.io/berntpopp/litvar-link@sha256:<digest>
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d
```

`make docker-prod-config` and `make docker-npm-config` default the variable to a
zeroed placeholder digest so the config can be rendered as a check without a
deploy.

## Production checklist

1. **Set the Host allowlist.** `LITVAR_LINK_ALLOWED_HOSTS` must contain the
   exact public hostname served by the reverse proxy (e.g.
   `litvar-link.genefoundry.org`) in addition to the loopback defaults.
2. **Set the Origin allowlist.** `LITVAR_LINK_ALLOWED_ORIGINS` defaults to `[]`
   and is the browser-origin admission gate; it must include every origin
   `LITVAR_LINK_CORS_ORIGINS` is intended to serve.
3. **Pin the image by digest** (`LITVAR_LINK_IMAGE`, above).
4. **Switch logging to JSON** (`LITVAR_LINK_LOG_FORMAT=json`).
5. **Do not raise the upstream rate limit.** The token bucket defaults to 2.0
   requests/second (burst 5) as NCBI LitVar2 etiquette.

The full semantics of the Host/Origin guard and every environment variable are
in [`configuration.md`](configuration.md).

## Health and monitoring

```bash
curl http://localhost:8000/api/health/        # health check and system status
curl http://localhost:8000/api/health/cache   # cache statistics
```

Both endpoints are served by the REST surface, so they exist in `unified` and
`http` transport modes.

## Observability

- **Structured logging** (structlog): `json` format for production, `console`
  for development.
- **Transport-aware logging**: stdio mode logs to stderr so it never corrupts
  the MCP protocol stream on stdout.
- **Performance metrics**: request timing and cache hit/miss statistics.
- **Error tracking**: errors are logged with request context (correlation id).
- **Rate limiting**: outbound token-bucket protection against upstream abuse.

## Container security

The image follows the GeneFoundry Container & Deployment Hardening standard:

- non-root container user,
- no secrets baked into image layers,
- resource limits and health checks in the production overlay,
- production-grade process management (Gunicorn + Uvicorn workers),
- no published ports under the NPM overlay — traffic arrives via the proxy only.

See also [`../SECURITY.md`](../SECURITY.md).
