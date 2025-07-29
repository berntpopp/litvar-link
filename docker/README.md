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
├── gunicorn_conf.py          # Production WSGI configuration
├── .dockerignore             # Build optimization
└── README.md                 # This file
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

### Production
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Container Registry
```bash
# Build and push
docker build -f Dockerfile -t your-registry/litvar-link:latest ..
docker push your-registry/litvar-link:latest

# Run from registry
docker run -d --name litvar-link -p 8000:8000 --env-file ../.env your-registry/litvar-link:latest
```

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

## 🔐 Security Features

- Non-root container user (`app:app`)
- Minimal base image (Python 3.11 slim)
- No secrets in image layers
- Resource limits and health checks
- Production-grade process management

This setup provides a robust foundation for deploying LitVar-Link from development to production environments.