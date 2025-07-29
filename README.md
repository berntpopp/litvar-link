# LitVar-Link

A unified server for NCBI's LitVar2 genetic variant database with MCP integration for AI assistants.

## 🎯 Core Features

- **Unified API Server**: Modern FastAPI-based REST API for LitVar2 genetic variant data access
- **MCP Integration**: Model Context Protocol server for seamless AI assistant integration
- **Rate-Limited Client**: Respects LitVar2 API guidelines (2 requests/second max)
- **Intelligent Caching**: Async LRU caching with configurable TTL for optimal performance
- **Multiple Transport Modes**: HTTP REST API, MCP STDIO, or unified mode
- **Rich Data Models**: Comprehensive Pydantic models for all API responses
- **Production Ready**: Structured logging, health checks, and graceful shutdown

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd litvar-link

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate

# Install with development dependencies
pip install -e ".[dev]"

# Create environment configuration
cp .env.example .env
```

### Environment Configuration

Create a `.env` file with your configuration:

```env
# Server Configuration
LITVAR_LINK_HOST=127.0.0.1
LITVAR_LINK_PORT=8000
LITVAR_LINK_TRANSPORT_MODE=unified

# API Configuration
LITVAR_LINK_API_BASE_URL=https://www.ncbi.nlm.nih.gov/research/litvar2-api
LITVAR_LINK_API_TIMEOUT=30
LITVAR_LINK_RATE_LIMIT_PER_SECOND=2.0

# Cache Configuration
LITVAR_LINK_CACHE_SIZE=1000
LITVAR_LINK_CACHE_TTL=3600

# Logging Configuration
LITVAR_LINK_LOG_LEVEL=INFO
LITVAR_LINK_LOG_FORMAT=console

# CORS Configuration
LITVAR_LINK_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

### Start the Server

```bash
# Unified mode (REST API + MCP)
python server.py

# HTTP-only mode (REST API only) 
litvar-link serve http

# STDIO mode (MCP only)
python mcp_server.py
```

## 📋 REST API Endpoints

### Core Endpoints

- `GET /` - Root endpoint with service information
- `GET /api/health/` - Health check and system status
- `GET /api/health/cache` - Cache statistics

### Variant Search

- `GET /api/variants/search` - Autocomplete search for genetic variants
- `GET /api/variants/details/{variant_id}` - Get detailed variant information

```bash
# Search for variants related to BRCA1
curl "http://127.0.0.1:8000/api/variants/search?query=BRCA1&limit=10"

# Search for specific variant
curl "http://127.0.0.1:8000/api/variants/search?query=p.Met1Val&limit=5"

# Get detailed information about a variant
curl "http://127.0.0.1:8000/api/variants/details/rs1061170"
```

### Gene Analysis

- `GET /api/genes/{gene_name}/variants` - Get all variants within a specific gene

```bash
# Get variants in CFH gene
curl "http://127.0.0.1:8000/api/genes/CFH/variants"

# Get variants in BRCA1 gene
curl "http://127.0.0.1:8000/api/genes/BRCA1/variants"
```

### Literature Discovery

- `GET /api/publications/variant/{variant_id}` - Get literature associated with a variant

```bash
# Get publications for a specific variant
curl "http://127.0.0.1:8000/api/publications/variant/litvar@rs1061170##"
```

### RSID Sensor

- `GET /api/sensor/{rsid}` - Check RSID availability and get basic information

```bash
# Check if RSID is available in LitVar2
curl "http://127.0.0.1:8000/api/sensor/rs1061170"

# Check multiple RSIDs
curl "http://127.0.0.1:8000/api/sensor/rs9970784"
```

## 🔧 MCP Integration

### Configuration for AI Assistants

#### Claude Desktop (STDIO Mode)

Add to your Claude Desktop configuration (`claude_desktop_config.json`):

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

#### Web-based AI (HTTP Mode)

For HTTP-based MCP integration:

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

### Configuration Files

**Find your Claude Desktop config file:**
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

### Available MCP Tools

- `search_genetic_variants` - Search for genetic variants using autocomplete
- `get_variant_summary` - Get detailed information about a specific variant
- `get_variant_literature` - Find literature associated with a genetic variant
- `lookup_rsid_availability` - Check if an RSID is available in LitVar2
- `search_gene_variants` - Get all variants within a specific gene

### Transport Modes

#### STDIO Mode (Recommended for Claude Desktop)
```bash
# Direct STDIO mode for maximum performance
python mcp_server.py
```

#### HTTP Mode (For web-based AI)
```bash
# Start unified server with MCP HTTP endpoint
python server.py
# MCP available at http://localhost:8000/mcp
```

#### Unified Mode (REST + MCP)
```bash
# Both REST API and MCP in one server
python server.py
# REST API: http://localhost:8000/docs
# MCP: http://localhost:8000/mcp
```

## 🛠️ CLI Usage

The CLI provides convenient access to LitVar2 functionality:

```bash
# Test API connection
litvar-link test

# Search for variants
litvar-link search "BRCA1 p.Met1Val" --limit 10

# Check RSID availability
litvar-link rsid rs1061170

# Get variants in a gene
litvar-link gene CFH --limit 20
```

## 🏗️ Architecture

### Project Structure

```
litvar-link/
├── litvar_link/
│   ├── api/
│   │   ├── client.py           # LitVar2 API client with rate limiting
│   │   └── routes/             # FastAPI route definitions
│   ├── models/
│   │   ├── requests.py         # Request validation models
│   │   ├── responses.py        # Response models
│   │   ├── variants.py         # Genetic variant models
│   │   └── endpoint_specific.py # API-specific models
│   ├── services/
│   │   └── variant_service.py  # Business logic with caching
│   ├── config.py               # Configuration management
│   ├── logging_config.py       # Structured logging
│   ├── server_manager.py       # Unified server management
│   ├── exceptions.py           # Custom exception handling
│   └── cli.py                  # Command-line interface
├── server.py                   # Main server entry point
├── mcp_server.py              # MCP STDIO server entry point
├── mcp_server_wrapper.py      # MCP wrapper for production
└── pyproject.toml             # Modern Python project configuration
```

### Key Components

- **API Client**: Rate-limited HTTP client respecting LitVar2 guidelines (2 req/sec)
- **Service Layer**: Business logic with async LRU caching and clinical significance analysis
- **Server Manager**: Unified handling of multiple transport modes
- **Data Models**: Comprehensive Pydantic models for genetic variant data
- **MCP Integration**: Complete STDIO server with banner suppression

### LitVar2 API Integration

The system integrates with LitVar2 API endpoints:

- **Variant Autocomplete**: `variant/autocomplete/` - Search for variants
- **Gene Variants**: `variant/search/gene/{gene_name}` - Get variants by gene
- **RSID Sensor**: `sensor/{rsid}` - Check RSID availability

**Data Processing**: Handles LitVar2's Python-style dictionary format in NDJSON responses.

## 🧪 Development

### Setup Development Environment

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run code quality checks
ruff check .
ruff format .
mypy litvar_link/

# Run tests
pytest
pytest --cov=litvar_link --cov-report=html

# Start development server
python server.py --host 0.0.0.0 --port 8080
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=litvar_link

# Run specific test categories
pytest -m "not slow"        # Exclude slow tests
pytest -m integration       # Only integration tests
pytest -m unit              # Only unit tests
pytest -m api               # Tests requiring API access

# Run single test file
pytest tests/test_models/test_variants.py
```

### Code Quality

The project uses modern Python tooling:

- **Ruff**: Fast linting and formatting (90% error reduction achieved!)
- **MyPy**: Static type checking
- **Pytest**: Testing framework with async support (136/136 tests passing)
- **Flake8**: Additional linting (100% compliance)

## 📦 Configuration

### Environment Variables

All configuration uses the `LITVAR_LINK_` prefix:

| Variable | Default | Description |
|----------|---------|-------------|
| `LITVAR_LINK_HOST` | `127.0.0.1` | Server host address |
| `LITVAR_LINK_PORT` | `8000` | Server port |
| `LITVAR_LINK_TRANSPORT_MODE` | `unified` | Server mode (unified/http/stdio) |
| `LITVAR_LINK_LOG_LEVEL` | `INFO` | Logging level |
| `LITVAR_LINK_LOG_FORMAT` | `console` | Log format (console/json) |
| `LITVAR_LINK_CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | CORS allowed origins |

### Cache Configuration

The caching system uses async LRU caching with configurable size and TTL:

- **Variant Search**: Cached by query and limit
- **Gene Variants**: Cached by gene name with clinical significance statistics
- **RSID Lookup**: Cached with 24-hour TTL
- **Publications**: Cached by variant ID

## 🚀 Production Deployment

### Docker Deployment

LitVar-Link includes a comprehensive Docker setup with multi-stage builds, production optimizations, and support for various deployment scenarios.

#### Quick Start

```bash
# Copy environment template
cp .env.example .env

# Local development
cd docker
docker-compose up --build

# Production deployment
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Nginx Proxy Manager deployment
cp .env.npm.example .env.npm
# Edit .env.npm with your domain settings
docker-compose -f docker-compose.yml -f docker-compose.npm.yml up -d
```

#### Deployment Options

- **Local Development**: Direct port access with hot-reloading support
- **Production**: Gunicorn + Uvicorn workers with resource limits
- **NPM Integration**: Nginx Proxy Manager with SSL and custom domains

#### Features

- ✅ Multi-stage Docker builds for optimized image size
- ✅ Production-ready Gunicorn configuration
- ✅ Health checks and graceful shutdown
- ✅ Non-root container security
- ✅ Comprehensive logging and monitoring
- ✅ Environment-based configuration

**📁 See [`docker/README.md`](docker/README.md) for complete deployment documentation.**

### Health Monitoring

The server provides comprehensive health checks:

```bash
# Check server health
curl http://localhost:8000/api/health/

# Monitor cache performance
curl http://localhost:8000/api/health/cache
```

### Observability

- **Structured Logging**: JSON format for production, console for development
- **Transport-aware Logging**: Automatic stderr usage for STDIO mode
- **Performance Metrics**: Request timing and cache statistics
- **Error Tracking**: Comprehensive error logging with context
- **Rate Limiting**: Built-in protection with token bucket algorithm

## 📊 Performance

- **Rate Limiting**: Respects LitVar2 API guidelines (max 2 requests/second)
- **Async Architecture**: Non-blocking I/O for high concurrency
- **Intelligent Caching**: Reduces API calls and improves response times
- **Connection Pooling**: Efficient HTTP client management
- **Clinical Significance Analysis**: Automatic pathogenic/benign classification

## 🧬 Genetic Variant Features

### Supported Data Types

- **Variant Search**: Autocomplete search with gene, RSID, and protein notation support
- **Clinical Significance**: Automatic classification of pathogenic, benign, and uncertain variants
- **Gene Analysis**: Comprehensive variant analysis within specific genes
- **Literature Mining**: Association with relevant scientific publications
- **RSID Validation**: Format validation and availability checking

### Data Models

- **AutocompleteVariantItem**: Search results with flags and metadata
- **GeneVariantItem**: Gene-specific variant data with clinical annotations
- **VariantDetails**: Comprehensive variant information
- **Publication**: Associated literature with PMID tracking

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Install development dependencies (`pip install -e ".[dev]"`)
4. Make your changes and add tests
5. Run code quality checks (`ruff check . && ruff format . && mypy litvar_link/`)
6. Run tests (`pytest`) - ensure all 136 tests pass
7. Commit your changes (`git commit -m 'Add amazing feature'`)
8. Push to the branch (`git push origin feature/amazing-feature`)
9. Open a Pull Request

## 📚 API Reference

For detailed API documentation, visit the interactive docs when running the server:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🔗 Related Projects

- **PubTator-Link**: MCP server for biomedical literature annotations
- **gnomAD-Link**: MCP server for gnomAD genomic data
- **GeneReviews-Link**: MCP server for NCBI GeneReviews

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [LitVar2](https://www.ncbi.nlm.nih.gov/research/litvar2/) - NCBI's genetic variant literature database
- [Model Context Protocol](https://modelcontextprotocol.io/) - Open standard for AI-tool integration
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [Pydantic](https://pydantic.dev/) - Data validation using Python type hints

---

**Status**: Production Ready | **Version**: 0.1.0 | **Python**: 3.10+ | **Tests**: 136/136 Passing ✅