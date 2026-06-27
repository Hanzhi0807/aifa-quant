# AifaQuant all-in-one Docker image
# Builds the web UI + Hono API and bundles the Python CLI.
# Usage:
#   docker build -t aifa-quant .
#   docker run -p 3000:3000 -v ./data_store:/app/data_store aifa-quant
#
# The web API reads from DUCKDB_PATH (default /app/data_store/aifa_quant.duckdb).

# ------------------------------------------------------------------------------
# Stage 1: Build the web frontend + API bundle
# ------------------------------------------------------------------------------
FROM node:22-slim AS web-build

WORKDIR /app/web
COPY web/package*.json ./
RUN npm ci

COPY web/ ./
RUN npm run build

# ------------------------------------------------------------------------------
# Stage 2: Python runtime with Node.js for the web server
# ------------------------------------------------------------------------------
FROM python:3.12-slim

# Install system dependencies for Python data packages and Node native addons
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    build-essential \
    libxml2-dev libxslt-dev \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python package and CLI dependencies
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir -e .

# Copy the built web assets and node_modules needed for production
COPY --from=web-build /app/web/dist ./web/dist
COPY --from=web-build /app/web/node_modules ./web/node_modules
COPY --from=web-build /app/web/package.json ./web/package.json

# Copy the application source so the CLI works inside the container
COPY aifa_quant/ ./aifa_quant/

# Copy maintenance scripts used by the web "refresh" button
COPY scripts/ ./scripts/

# Seed an empty data_store directory (mount a real DuckDB file here)
RUN mkdir -p /app/data_store

ENV DUCKDB_PATH=/app/data_store/aifa_quant.duckdb
ENV NODE_ENV=production
EXPOSE 3000

WORKDIR /app/web
CMD ["node", "dist/boot.js"]
