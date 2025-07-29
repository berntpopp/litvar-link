# LitVar-Link Docker Deployment

Production-ready Docker setup for LitVar-Link with multi-stage builds and optimized configurations.

## 🚀 Quick Start

### Development Setup

```bash
# Copy environment template (if not already done)
cp .env.example .env

# Build and run development server
cd docker
docker-compose up --build
```

Server available at `http://localhost:8000` with API docs at `/docs`.

### Production Deployment

```bash
# Build and run production server
cd docker
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## 📁 File Structure

```
docker/
├── Dockerfile                 # Multi-stage production build
├── docker-compose.yml         # Development configuration
├── docker-compose.prod.yml    # Production overrides
├── docker-compose.dev.yml     # Hot-reload development (optional)
├── docker-compose.npm.yml     # NPM production deployment
├── gunicorn_conf.py          # Production WSGI configuration
├── .dockerignore             # Build optimization
└── README.md                 # This file

# Environment files (in project root)
├── .env.example              # Local development template
└── .env.npm.example          # NPM production template
```

## 🔧 Configuration

Key environment variables (edit `.env`):

```env
# Server settings
LITVAR_LINK_HOST=127.0.0.1
LITVAR_LINK_PORT=8000
LITVAR_LINK_LOG_LEVEL=INFO

# CORS settings (JSON format required)
LITVAR_LINK_CORS_ORIGINS=["http://localhost:3000","http://localhost:8080"]
LITVAR_LINK_CORS_ALLOW_METHODS=["GET","POST","PUT","DELETE","OPTIONS"]
LITVAR_LINK_CORS_ALLOW_HEADERS=["*"]

# Production scaling
GUNICORN_WORKERS=4
GUNICORN_THREADS=4
```

## 🏗️ Architecture

**Multi-Stage Build:**
- **Builder**: Installs dependencies in virtual environment
- **Production**: Minimal runtime image with non-root user

**Development vs Production:**
- Development: Simple uvicorn server, debug logging
- Production: Gunicorn + Uvicorn workers, JSON logging, resource limits

## 🐳 Deployment Options

### Local Development
```bash
docker-compose up --build
```

### Hot-Reload Development (optional)
```bash
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

### Production (Local Server)
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### NPM Production Deployment
```bash
# Setup NPM environment
cp .env.npm.example .env.npm
# Edit .env.npm with your domain and settings

# Deploy with NPM configuration
docker-compose -f docker-compose.yml -f docker-compose.npm.yml up -d
```

### Container Registry
```bash
# Build and push
docker build -f Dockerfile -t your-registry/litvar-link:latest ..
docker push your-registry/litvar-link:latest

# Run from registry
docker run -d --name litvar-link -p 8000:8000 --env-file ../.env your-registry/litvar-link:latest
```

## 🌐 Nginx Proxy Manager (NPM) Integration

LitVar-Link includes built-in support for deployment with Nginx Proxy Manager for production hosting with custom domains and SSL certificates.

### NPM Prerequisites

1. **Running NPM Instance**: Nginx Proxy Manager should be running on your server
2. **Shared Network**: Verify NPM's Docker network name with `docker network ls` (typically `npm_default`)
3. **Domain Access**: DNS records pointing your domain to the server

### NPM Setup Process

#### 1. Environment Configuration
```bash
# Copy and customize NPM environment
cp .env.npm.example .env.npm

# Edit .env.npm with your settings:
# - NPM_SHARED_NETWORK_NAME=npm_default (or your NPM network)
# - LITVAR_LINK_PUBLIC_DOMAIN=litvar.yourdomain.com
# - LITVAR_LINK_CORS_ORIGINS=["https://litvar.yourdomain.com"]
```

#### 2. Deploy LitVar-Link
```bash
# Deploy container without direct port exposure
docker-compose -f docker-compose.yml -f docker-compose.npm.yml up -d
```

#### 3. Configure NPM Proxy Host
In your NPM web interface:
- **Domain Names**: `litvar.yourdomain.com`
- **Scheme**: `http`
- **Forward Hostname/IP**: `litvar-link` (container name)
- **Forward Port**: `8000`
- **Enable SSL**: Add/Request SSL certificate

#### 4. Verify Deployment
```bash
# Check container health
docker-compose logs litvar-link

# Test health endpoint through NPM
curl https://litvar.yourdomain.com/api/health/
```

### NPM Network Architecture

```
Internet → NPM (SSL/443) → Docker Network → LitVar-Link Container (8000)
```

- **External Access**: Through your domain with SSL
- **Internal Routing**: NPM forwards to `litvar-link:8000`
- **No Direct Ports**: Container doesn't expose ports on host
- **Network Isolation**: Services communicate via shared Docker network

### NPM Configuration Examples

#### Basic Proxy Host
- **Domain**: `litvar.yourdomain.com`
- **Destination**: `litvar-link:8000`
- **SSL**: Let's Encrypt or custom certificate

#### Advanced Configuration
- **Custom locations**: `/api/*` for API-specific routing
- **Caching**: Enable for static assets if needed
- **Rate limiting**: Configure in NPM for additional protection
- **Access lists**: Restrict access by IP if required

### NPM vs Development Differences

| Feature | Development | NPM Production |
|---------|-------------|----------------|
| **Access** | `localhost:8000` | `https://yourdomain.com` |
| **Ports** | Direct port mapping | No port exposure |
| **SSL** | None | NPM-managed SSL |
| **Networks** | Bridge only | NPM shared network |
| **Logging** | Console format | JSON format |
| **CORS** | Localhost origins | Production domains |

## 🔍 Monitoring

- **Health Check**: `curl http://localhost:8000/api/health/`
- **API Documentation**: `http://localhost:8000/docs`
- **Container Logs**: `docker-compose logs -f litvar-link`

## 🛠️ Development Workflow

1. Edit source code in `../litvar_link/`
2. For simple changes: `docker-compose restart litvar-link`
3. For dependency changes: `docker-compose up --build`

## 🚨 Troubleshooting

**Port conflicts:**
```bash
# Change port in .env
LITVAR_LINK_PORT=8001
```

**Permission errors:**
```bash
# Clean build cache
docker system prune -a
docker-compose build --no-cache
```

**CORS configuration:**
- Must use JSON array format in environment variables
- Example: `["http://localhost:3000","http://localhost:8080"]`

**NPM deployment issues:**
```bash
# Check if NPM network exists
docker network ls | grep npm

# Verify container is on NPM network
docker inspect litvar-link | grep NetworkMode

# Check NPM container logs
docker logs nginx-proxy-manager

# Test internal connectivity
docker exec litvar-link curl -f http://localhost:8000/api/health/
```

**NPM proxy configuration:**
- Ensure Forward Hostname/IP is `litvar-link` (not IP address)
- Use scheme `http` (not https) for internal routing
- Forward Port should be `8000`
- SSL should be configured in NPM, not the container

## 🔐 Security Features

- Non-root container user (`app:app`)
- Minimal base image (Python 3.11 slim)
- No secrets in image layers
- Resource limits and health checks
- Production-grade process management

This setup provides a robust foundation for deploying LitVar-Link from development to production environments.