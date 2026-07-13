# Multi-stage Dockerfile for LitVar-Link.

# --- Builder ---
FROM python:3.14-slim@sha256:b877e50bd90de10af8d82c57a022fc2e0dc731c5320d762a27986facfc3355c1 AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV VIRTUAL_ENV="/opt/venv" \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY uv.lock pyproject.toml README.md ./

# Pin uv by digest (fleet-shared anchor) instead of a floating pip/uv upgrade,
# for a reproducible, supply-chain-hardened build.
COPY --from=ghcr.io/astral-sh/uv:0.8.7@sha256:1e26f9a868360eeb32500a35e05787ffff3402f01a8dc8168ef6aee44aef0aab /uv /usr/local/bin/uv

RUN uv sync --frozen --no-dev --active

# --- Production ---
FROM python:3.14-slim@sha256:b877e50bd90de10af8d82c57a022fc2e0dc731c5320d762a27986facfc3355c1 AS production


ARG APP_VERSION=0.0.0
ARG VCS_REF=unknown
ARG BUILD_DATE=1970-01-01T00:00:00Z
LABEL org.opencontainers.image.title="LitVar-Link" \
      org.opencontainers.image.description="Research-use MCP/API server for NCBI LitVar2 variant literature data." \
      org.opencontainers.image.source="https://github.com/berntpopp/litvar-link" \
      org.opencontainers.image.url="https://github.com/berntpopp/litvar-link" \
      org.opencontainers.image.documentation="https://github.com/berntpopp/litvar-link#readme" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.vendor="GeneFoundry"
ENV APP_VERSION="${APP_VERSION}" \
    VCS_REF="${VCS_REF}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/home/app/web" \
    LITVAR_LINK_HOST=0.0.0.0 \
    LITVAR_LINK_PORT=8000

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

RUN groupadd --gid 10001 app && \
    useradd --uid 10001 --gid app --home /home/app --create-home --shell /usr/sbin/nologin app

COPY --from=builder /opt/venv /opt/venv

WORKDIR /home/app/web

COPY --chown=app:app ./litvar_link ./litvar_link
COPY --chown=app:app ./server.py ./mcp_server.py ./pyproject.toml ./README.md ./
COPY --chown=app:app ./docker/gunicorn_conf.py ./

RUN /opt/venv/bin/pip install -e . --no-deps

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -fsS -H 'Host: localhost' http://localhost:8000/health || exit 1

CMD ["litvar-link", "serve", "unified", "--host", "0.0.0.0", "--port", "8000"]
