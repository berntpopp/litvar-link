# MCP clients and CLI

How to attach an AI assistant to LitVar-Link, and how to drive the same data
from a terminal.

## Transports

`LITVAR_LINK_TRANSPORT_MODE` (or the `serve` sub-command) selects the surface:

| Mode | Behavior |
|------|----------|
| `stdio` | MCP only, over stdio. Best for Claude Desktop. |
| `http` | REST API only. |
| `unified` | REST API **plus** the MCP HTTP endpoint at `LITVAR_LINK_MCP_PATH` (default `/mcp`). The default. |

```bash
make dev              # unified: REST + MCP over HTTP on 127.0.0.1:8000
make mcp-serve        # MCP over stdio
make mcp-serve-http   # unified server with MCP over HTTP

# equivalently, through the CLI
uv run litvar-link serve unified --host 127.0.0.1 --port 8000
uv run litvar-link serve http
uv run litvar-link serve mcp
```

## Claude Code

Hosted instance:

```bash
claude mcp add --transport http litvar https://litvar-link.genefoundry.org/mcp
```

Local server (`make dev` running):

```bash
claude mcp add --transport http litvar http://127.0.0.1:8000/mcp
```

## Claude Desktop (stdio)

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "litvar-link": {
      "command": "python",
      "args": ["/absolute/path/to/litvar-link/mcp_server.py"],
      "env": {
        "PYTHONUNBUFFERED": "1",
        "LITVAR_LINK_LOG_LEVEL": "WARNING"
      }
    }
  }
}
```

Where that file lives:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

In stdio mode the server logs to stderr, so stdout stays a clean MCP protocol
stream.

## Web-based / HTTP MCP clients

```json
{
  "mcpServers": {
    "litvar-link": {
      "transport": {
        "type": "http",
        "url": "http://localhost:8000/mcp"
      }
    }
  }
}
```

## Console scripts

`pyproject.toml` ships two entry points:

| Script | Purpose |
|--------|---------|
| `litvar-link` | The CLI (`serve`, `test`, `search`, `rsid`, `gene`). |
| `litvar-link-mcp` | The MCP stdio entry point (`mcp_server:main`). |

## CLI usage

```bash
# Test the connection to the LitVar2 API
litvar-link test

# Search for variants
litvar-link search "BRCA1 p.Met1Val" --limit 10

# Check RSID availability
litvar-link rsid rs1061170

# List variants in a gene
litvar-link gene CFH --limit 20
```

## Tool response conventions

- **`response_mode`** on data tools: `compact` (default, high-signal fields
  only) or `full` (the raw service payload).
- **Pagination**: list-returning tools take a `limit` and report
  `_meta.pagination.{total_count, has_more, next_cursor}`. `total_count` is
  LitVar2's real total where it supplies one, and `null` where it does not — the
  autocomplete endpoint behind `search_genetic_variants` publishes no count, and
  inventing one would tell you that you had seen everything when you had not.
  `search_gene_variants` and `get_variant_literature` carry an opaque `cursor`
  that pages through the entire set; an invalid cursor is an `invalid_input`
  error, never a silent first page.
- **`recommended_citation`**: literature results carry a PMID-based citation
  string. Paste it verbatim; never paraphrase or fabricate it.
- **Errors** come in two classes. User-recoverable problems (empty query, out-of-
  range `limit`, malformed rsID or gene symbol) surface as a visible
  `ToolValidationError` with an actionable message so the agent can self-correct.
  Internal errors (transport, client, unexpected) are masked as
  `ToolInternalError` and logged. See `litvar_link/mcp/errors.py`.
- **`get_server_capabilities`** returns the tool inventory, the response-mode and
  limit semantics, the citation contract, and the research-use notice, so a cold
  client can self-orient.
