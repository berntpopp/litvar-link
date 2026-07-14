# REST API

LitVar-Link is dual-surface: the same service layer backs both the MCP tools and
a FastAPI REST API. The REST surface is served in the `unified` and `http`
transport modes (see [`configuration.md`](configuration.md#transports)); the
`stdio` mode is MCP-only.

Interactive documentation, when the server is running:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI schema: `http://localhost:8000/openapi.json`

## Core endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/` | Root endpoint with service information. |
| `GET` | `/health` | Liveness probe. |
| `GET` | `/api/health/` | Health check and system status. |
| `GET` | `/api/health/cache` | Cache statistics. |

## Variant search

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/variants/search` | Autocomplete search for genetic variants. |
| `GET` | `/api/variants/details/{variant_id}` | Detailed variant information. |

```bash
# Search for variants related to BRCA1
curl "http://127.0.0.1:8000/api/variants/search?query=BRCA1&limit=10"

# Search by protein notation
curl "http://127.0.0.1:8000/api/variants/search?query=p.Met1Val&limit=5"

# Get detailed information about a variant
curl "http://127.0.0.1:8000/api/variants/details/rs1061170"
```

## Gene analysis

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/genes/{gene_name}/variants` | All variants within a specific gene. |

```bash
curl "http://127.0.0.1:8000/api/genes/CFH/variants"
curl "http://127.0.0.1:8000/api/genes/BRCA1/variants"
```

Gene-variant responses carry a clinical-significance tally (pathogenic / benign /
uncertain counts) computed across the returned variants. A variant with no
`data_clinical_significance` counts as uncertain. This is a summary of what
LitVar2 reports in the literature — **not** a clinical assertion.

## Literature discovery

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/publications/variant/{variant_id}` | Literature associated with a variant. |

```bash
curl "http://127.0.0.1:8000/api/publications/variant/litvar@rs1061170##"
```

## RSID sensor

`sensor` is a LitVar2 primitive: it answers whether an rsID exists in LitVar2 and
returns its basic record (PMID count and LitVar2 link). It is the REST twin of
the `resolve_rsid` MCP tool.

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/sensor/{rsid}` | Check RSID availability and get basic information. |

```bash
curl "http://127.0.0.1:8000/api/sensor/rs1061170"
curl "http://127.0.0.1:8000/api/sensor/rs9970784"
```

## Error contract

Route handlers stay thin; app-level exception handlers in
`litvar_link/api/error_handlers.py` map exceptions uniformly:

| Exception | HTTP status |
|-----------|-------------|
| `ValidationError` (bad rsID, gene symbol, limit, empty query) | `400` |
| `LitVarAPIError` (upstream failure) | `502` |
| anything else | `500` |

## Response models

Responses are Pydantic models under `litvar_link/models/`:

- `litvar_link/models/responses.py` — `VariantSearchResponse`,
  `VariantDetailsResponse`, `PublicationResponse`, `SensorResponse`,
  `GeneVariantsResponse`, `CacheStatsResponse`, `HealthResponse`.
- `litvar_link/models/endpoint_specific.py` — the per-item models:
  `AutocompleteVariantItem`, `GeneVariantItem`, `VariantDetailsItem`,
  `SensorItem`, `PublicationsItem`.
- `litvar_link/models/requests.py` — request validation models.

The OpenAPI `responses={...}` and per-parameter `openapi_examples` dicts are
extracted to `litvar_link/api/routes/openapi_examples.py` to keep handlers under
the function-size cap.
