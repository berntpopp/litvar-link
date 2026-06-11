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
└── .env.docker.example          # Docker/NPM production template
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
cp .env.docker.example .env.docker
# Edit .env.docker with your domain and settings

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
cp .env.docker.example .env.docker

# Edit .env.docker with your settings:
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

## 🖥️ VPS Production Deployment Guide

Complete guide for deploying LitVar-Link on a Virtual Private Server with Nginx Proxy Manager.

### Prerequisites

1. **VPS Requirements**:
   - Ubuntu 20.04+ or similar Linux distribution
   - 2GB+ RAM, 1+ CPU cores
   - 20GB+ storage space
   - Root or sudo access

2. **Domain Setup**:
   - Domain name pointing to your VPS IP
   - DNS A record configured (e.g., `litvar.yourdomain.com` → `your.vps.ip`)

3. **NPM Installation**:
   - Nginx Proxy Manager running on the same VPS
   - NPM accessible via web interface (typically port 81)

### Step-by-Step Deployment

#### 1. Server Preparation

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install Docker and Docker Compose
sudo apt install -y docker.io docker-compose git

# Start and enable Docker
sudo systemctl start docker
sudo systemctl enable docker

# Add user to docker group (logout/login required)
sudo usermod -aG docker $USER
```

#### 2. Project Setup

```bash
# Clone the repository
git clone https://github.com/your-org/litvar-link.git
cd litvar-link

# Create production environment file
cp .env.docker.example .env.docker

# Edit environment with your domain settings
nano .env.docker
```

#### 3. Environment Configuration

Edit `.env.docker` with your specific settings:

```env
# Critical settings to customize:
NPM_SHARED_NETWORK_NAME=npm_default
LITVAR_LINK_PUBLIC_DOMAIN=litvar.yourdomain.com  
LITVAR_LINK_PUBLIC_URL=https://litvar.yourdomain.com
LITVAR_LINK_CORS_ORIGINS=["https://litvar.yourdomain.com"]

# Production optimizations:
GUNICORN_WORKERS=4
GUNICORN_LOG_LEVEL=warning
LITVAR_LINK_LOG_LEVEL=INFO
```

#### 4. Network Verification

```bash
# Verify NPM network exists
docker network ls | grep npm

# If NPM network doesn't exist, check NPM container
docker ps | grep nginx-proxy-manager

# Get actual network name if different
docker inspect <npm_container_id> | grep NetworkMode
```

#### 5. Deploy LitVar-Link

```bash
# Build and deploy with NPM configuration
cd docker
docker-compose -f docker-compose.yml -f docker-compose.npm.yml up -d --build

# Verify deployment
docker-compose logs -f litvar-link
```

#### 6. NPM Proxy Configuration

1. **Access NPM Web Interface**:
   - Open `http://your-vps-ip:81`
   - Login with your NPM credentials

2. **Create Proxy Host**:
   - **Domain Names**: `litvar.yourdomain.com`
   - **Scheme**: `http` (internal)
   - **Forward Hostname/IP**: `litvar-link`
   - **Forward Port**: `8000`
   - **Cache Assets**: Enable
   - **Block Common Exploits**: Enable

3. **Configure SSL**:
   - Go to SSL tab
   - Select "Request a new SSL Certificate"
   - Enable "Force SSL" and "HTTP/2 Support"
   - Add email for Let's Encrypt

#### 7. Verification and Testing

```bash
# Check container health
docker exec litvar-link curl -f http://localhost:8000/api/health/

# Test external access
curl https://litvar.yourdomain.com/api/health/

# Check logs
docker-compose -f docker-compose.yml -f docker-compose.npm.yml logs litvar-link
```

### Production Monitoring

#### Log Management

```bash
# View real-time logs
docker-compose -f docker-compose.yml -f docker-compose.npm.yml logs -f litvar-link

# View specific time range
docker-compose logs --since=1h litvar-link

# Check log file sizes (automatic rotation configured)
docker exec litvar-link ls -la /var/log/
```

#### Health Monitoring

```bash
# Create health check script
cat > /opt/litvar-health-check.sh << 'EOF'
#!/bin/bash
HEALTH_URL="https://litvar.yourdomain.com/api/health/"
if curl -f -s "$HEALTH_URL" > /dev/null; then
    echo "$(date): LitVar-Link is healthy"
else
    echo "$(date): LitVar-Link health check failed" >&2
    # Optional: restart container
    # docker-compose -f /path/to/docker-compose.yml restart litvar-link
fi
EOF

chmod +x /opt/litvar-health-check.sh

# Add to crontab for periodic checking
(crontab -l ; echo "*/5 * * * * /opt/litvar-health-check.sh >> /var/log/litvar-health.log") | crontab -
```

#### Resource Monitoring

```bash
# Monitor container resources
docker stats litvar-link

# Check disk usage
docker system df

# Monitor logs size
docker-compose config | grep max-size
```

### Maintenance and Updates

#### Update Deployment

```bash
# Pull latest changes
git pull origin main

# Rebuild and redeploy
docker-compose -f docker-compose.yml -f docker-compose.npm.yml down
docker-compose -f docker-compose.yml -f docker-compose.npm.yml up -d --build

# Verify health
curl https://litvar.yourdomain.com/api/health/
```

#### Backup Configuration

```bash
# Backup environment and configs
tar -czf litvar-backup-$(date +%Y%m%d).tar.gz .env.docker docker/

# Backup to remote location (optional)
scp litvar-backup-*.tar.gz user@backup-server:/backups/
```

### Troubleshooting VPS Deployment

#### Common Issues

**Container won't start:**
```bash
# Check Docker daemon
sudo systemctl status docker

# Check container logs
docker-compose logs litvar-link

# Verify environment file
cat .env.docker | grep -v "^#" | grep -v "^$"
```

**NPM connectivity issues:**
```bash
# Verify network connectivity
docker exec litvar-link ping npm-container-name

# Check network attachments
docker inspect litvar-link | grep -A 10 Networks

# Test internal health endpoint
docker exec litvar-link curl localhost:8000/api/health/
```

**SSL certificate issues:**
```bash
# Check NPM logs
docker logs nginx-proxy-manager

# Verify domain DNS
nslookup litvar.yourdomain.com

# Test port 80/443 accessibility
curl -I http://litvar.yourdomain.com
```

**Performance issues:**
```bash
# Monitor resource usage
htop
docker stats

# Check LitVar2 API rate limits
docker-compose logs litvar-link | grep -i rate

# Adjust worker count in .env.docker
# GUNICORN_WORKERS=2  # For lower-spec VPS
```

### Security Hardening

#### Firewall Configuration

```bash
# Configure UFW firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 81/tcp  # NPM admin (consider restricting by IP)
sudo ufw enable
```

#### Regular Updates

```bash
# System updates
sudo apt update && sudo apt upgrade -y

# Docker updates
sudo apt update docker.io docker-compose

# Container updates (schedule monthly)
docker-compose pull && docker-compose up -d
```

This comprehensive VPS deployment guide provides everything needed to run LitVar-Link in production with NPM on a virtual private server.