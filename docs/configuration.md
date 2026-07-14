# Configuration

## Environment variables

All settings can be supplied via environment variables (or a local `.env`
file). The canonical prefix is `LITVAR_LINK_`.

**Nested settings use the `__` (double-underscore) delimiter.** The `api.*`
and `cache.*` sub-configs are addressed as `LITVAR_LINK_API__<FIELD>` and
`LITVAR_LINK_CACHE__<FIELD>`. Top-level server/log/CORS settings take the
prefix directly (`LITVAR_LINK_<FIELD>`).

> The `__` delimiter is required so nested pydantic-settings fields resolve
> correctly. Flat names like `LITVAR_LINK_API_BASE_URL` (single underscore)
> do NOT map onto the nested `api` model and are ignored.

### Server

```bash
LITVAR_LINK_HOST=127.0.0.1
LITVAR_LINK_PORT=8000
LITVAR_LINK_RELOAD=false
LITVAR_LINK_TRANSPORT_MODE=unified        # stdio | http | unified
LITVAR_LINK_MCP_PATH=/mcp
```

### Host and Origin guard

```bash
LITVAR_LINK_ALLOWED_HOSTS=["localhost","127.0.0.1","::1"]
LITVAR_LINK_ALLOWED_ORIGINS=[]
```

These two are the request-admission gate on every HTTP route, and they are
**not** the same thing as CORS (below).

- `LITVAR_LINK_ALLOWED_HOSTS` is a JSON list of **exact** Host values and
  defaults to `["localhost","127.0.0.1","::1"]`. Production must add the public
  reverse-proxy hostname — for the hosted fleet instance,
  `litvar-link.genefoundry.org`.
- Write IPv6 entries **bare, without brackets** (`::1`, not `[::1]`).
- **Wildcard patterns are rejected.** There is no `*.example.org` form.
- `LITVAR_LINK_ALLOWED_ORIGINS` defaults to `[]` and is the browser-origin
  admission gate: it must include every origin that `LITVAR_LINK_CORS_ORIGINS`
  is intended to serve. Requests **without** an `Origin` header (i.e. non-browser
  clients such as MCP hosts and `curl`) remain valid.

### CORS

CORS controls the response headers a browser sees. Admission is still decided by
the Host/Origin guard above; an origin listed here but absent from
`LITVAR_LINK_ALLOWED_ORIGINS` will be rejected before CORS is ever applied.

```bash
LITVAR_LINK_CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]
LITVAR_LINK_CORS_ALLOW_CREDENTIALS=false
LITVAR_LINK_CORS_ALLOW_METHODS=["GET","POST","PUT","DELETE","OPTIONS"]
LITVAR_LINK_CORS_ALLOW_HEADERS=["*"]
```

`LITVAR_LINK_CORS_ALLOW_CREDENTIALS` is **off by default**: this backend is
unauthenticated (no cookies, no session), so credentials are meaningless here and
unsafe when paired with a permissive origin.

### Logging

```bash
LITVAR_LINK_LOG_LEVEL=INFO                 # DEBUG | INFO | WARNING | ERROR | CRITICAL
LITVAR_LINK_LOG_FORMAT=console             # console | json
LITVAR_LINK_LOG_SHOW_CALLER=false
```

### LitVar2 API client (nested `api.*`)

```bash
LITVAR_LINK_API__BASE_URL=https://www.ncbi.nlm.nih.gov/research/litvar2-api/
LITVAR_LINK_API__TIMEOUT=30                # seconds, 1-300
LITVAR_LINK_API__RATE_LIMIT_PER_SECOND=2.0 # requests/second, 0-10
LITVAR_LINK_API__BURST_SIZE=5              # token-bucket burst, 1-20
LITVAR_LINK_API__MAX_RETRIES=3             # 0-10
LITVAR_LINK_API__RETRY_DELAY=1.0           # seconds between retries, 0.1-10
LITVAR_LINK_API__USER_AGENT=LitVar-Link/1.0.0
```

### Caching (nested `cache.*`)

```bash
LITVAR_LINK_CACHE__SIZE=1000               # max cached items, 10-10000
LITVAR_LINK_CACHE__TTL=3600                # seconds, 60-86400
LITVAR_LINK_CACHE__STATS_ENABLED=true
LITVAR_LINK_CACHE__CLEANUP_INTERVAL=300    # seconds, 60-3600
```

## Transports

`LITVAR_LINK_TRANSPORT_MODE` selects how the server runs:

| Mode | Behavior |
|------|----------|
| `stdio` | MCP only, over stdio (best for Claude Desktop). |
| `http` | REST API only. |
| `unified` | REST API plus the MCP HTTP endpoint at `LITVAR_LINK_MCP_PATH`. |

## Rate-limit and cache tuning

The token-bucket limiter defaults to **2.0 requests/second** with a burst of
5, honouring NCBI LitVar2 etiquette. Keep it conservative.

```bash
# Higher-throughput cache (still rate-limit-bounded upstream)
LITVAR_LINK_CACHE__SIZE=4000
LITVAR_LINK_CACHE__TTL=7200
LITVAR_LINK_API__TIMEOUT=45

# Memory-frugal cache
LITVAR_LINK_CACHE__SIZE=256
LITVAR_LINK_CACHE__TTL=1800
```

## Notes on the `__` delimiter migration

Earlier README drafts documented flat nested names
(`LITVAR_LINK_API_BASE_URL`, `LITVAR_LINK_CACHE_TTL`, `LITVAR_LINK_RATE_LIMIT`).
Those did not map onto the nested `api` / `cache` pydantic models and were
silently ignored. The current contract is the `__`-delimited form documented
above. Update `.env` files and deployment configs to the `__` form.
