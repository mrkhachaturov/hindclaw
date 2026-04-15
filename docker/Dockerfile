# syntax=docker/dockerfile:1.7
# Hindsight — Astromech custom image
#
# Custom build tailored for our infrastructure:
#   - External PostgreSQL (pgvector) — no embedded pg0
#   - External S3 (MinIO) — file storage
#   - FlashRank local reranker — without torch/sentence-transformers
#   - OpenAI embeddings — external provider
#   - Claude Code LLM provider — via claude-agent-sdk (core dep)
#   - hindclaw-extension — server-side access control
#
# Build context must contain the upstream hindsight-control-plane/ source
# (consumed by the cp-builder stage below). The api stage now installs
# everything from PyPI, so no patched sources are required.
#
#   docker build -t hindsight-astromech \
#     -f build/hindclaw/docker/Dockerfile \
#     build/hindsight/.upstream

# =============================================================================
# Stage: API Builder
# =============================================================================
FROM python:3.11-slim AS api-builder

WORKDIR /app/api

RUN apt-get update && apt-get install -y curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv \
    && uv venv .venv

# Install hindsight-api-slim from PyPI plus the FlashRank reranker and the
# HindClaw extension. Pinned explicitly so the final image is reproducible.
# No local-ml (torch/sentence-transformers) and no embedded-db (pg0) extras —
# this image runs against external Postgres+pgvector and external rerankers.
RUN uv pip install --python /app/api/.venv/bin/python \
    "hindsight-api-slim==0.5.2" \
    "flashrank>=0.2.0" \
    "hindclaw-extension==0.5.0"

# =============================================================================
# Stage: Control Plane Builder (Next.js UI)
# =============================================================================
FROM node:20-slim AS cp-builder

WORKDIR /app/memory-poc/hindsight-control-plane
ARG HINDSIGHT_CLIENT_VERSION

# TEMPORARY: rewrite hindsight-control-plane's local-path @vectorize-io/hindsight-client
# dep to the npm-published version. Upstream's control-plane package.json still uses
# "file:../hindsight-clients/typescript" because their monorepo build resolves that
# through npm workspaces; we are not building from that workspace, so we need a real
# version pin. Two passes required because the second COPY below clobbers package.json
# with the upstream-shipped version.
# Tracked: no upstream PR (upstream's monorepo-workspace layout is intentional)
# Replace with: DELETE both rewrite lines if upstream ever ships a hindsight-control-plane/
#               package.json with a published-version pin instead of file:...

# Pass 1: package.json-only layer so the npm install layer cache stays stable.
COPY hindsight-control-plane/package.json ./
RUN sed -i "s|\"@vectorize-io/hindsight-client\": \"file:[^\"]*\"|\"@vectorize-io/hindsight-client\": \"${HINDSIGHT_CLIENT_VERSION}\"|" package.json
RUN npm install

# Pass 2: full source copy re-overwrites package.json — re-apply the rewrite.
COPY hindsight-control-plane/ ./
RUN rm -f package-lock.json \
    && sed -i "s|\"@vectorize-io/hindsight-client\": \"file:[^\"]*\"|\"@vectorize-io/hindsight-client\": \"${HINDSIGHT_CLIENT_VERSION}\"|" package.json

RUN npm exec -- next build

# Assemble standalone output
RUN STANDALONE_ROOT=$(find .next/standalone -path '*/node_modules' -prune -o -name 'server.js' -print | head -1 | xargs dirname) && \
    mkdir -p standalone && \
    cp -r "$STANDALONE_ROOT"/* standalone/ && \
    cp -r "$STANDALONE_ROOT"/.next standalone/.next && \
    if [ -d ".next/standalone/node_modules" ] && [ "$STANDALONE_ROOT" != ".next/standalone" ]; then \
      cp -r .next/standalone/node_modules standalone/node_modules; \
    fi && \
    cp -r .next/static standalone/.next/static && \
    mkdir -p standalone/public && \
    cp -r public/* standalone/public/ 2>/dev/null || true && \
    test -f standalone/server.js || (echo "ERROR: server.js missing!" && exit 1) && \
    test -f standalone/.next/BUILD_ID || (echo "ERROR: BUILD_ID missing!" && exit 1)

# =============================================================================
# Stage: Final Image (API + Control Plane)
# =============================================================================
FROM python:3.11-slim AS prod

WORKDIR /app

# System deps + Node.js for Control Plane
RUN apt-get update && apt-get install -y \
    curl \
    procps \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash hindsight

# Copy API with venv from builder
COPY --from=api-builder /app/api /app/api

# Copy Control Plane standalone build
WORKDIR /app/control-plane
COPY --from=cp-builder /app/memory-poc/hindsight-control-plane/standalone ./
COPY --from=cp-builder /app/memory-poc/hindsight-control-plane/.next/static ./.next/static
COPY --from=cp-builder /app/memory-poc/hindsight-control-plane/public ./public

WORKDIR /app

# Copy startup script from upstream
COPY docker/standalone/start-all.sh /app/start-all.sh
RUN chmod +x /app/start-all.sh

RUN chown -R hindsight:hindsight /app

USER hindsight

ENV PATH="/app/api/.venv/bin:${PATH}"

# Pre-download tiktoken encoding (required for token counting)
RUN /app/api/.venv/bin/python -c "\
import tiktoken; \
print('Downloading cl100k_base encoding...'); \
tiktoken.get_encoding('cl100k_base'); \
print('Tiktoken encoding cached successfully')"

# Pre-download FlashRank reranker model
RUN /app/api/.venv/bin/python -c "\
from flashrank import Ranker; \
print('Downloading ms-marco-MultiBERT-L-12 reranker model...'); \
Ranker(model_name='ms-marco-MultiBERT-L-12'); \
print('FlashRank model cached successfully')"

EXPOSE 8888 9999

ENV HINDSIGHT_API_HOST=0.0.0.0
ENV HINDSIGHT_API_PORT=8888
ENV HINDSIGHT_API_LOG_LEVEL=info
ENV NODE_ENV=production
ENV HINDSIGHT_CP_DATAPLANE_API_URL=http://localhost:8888
ENV HINDSIGHT_ENABLE_API=true
ENV HINDSIGHT_ENABLE_CP=true
ENV PYTHONUNBUFFERED=1

CMD ["/app/start-all.sh"]

# =============================================================================
# Stage: Dev (local hindclaw-extension from named build context)
# =============================================================================
#
# Used by Tier 2 integration tests and local development. Swaps the
# PyPI-installed hindclaw-extension for an editable install from a
# named BuildKit build context:
#
#   DOCKER_BUILDKIT=1 docker build \
#     -t hindsight-astromech:latest \
#     -f build/hindclaw/docker/Dockerfile \
#     --build-context hindclaw-ext=build/hindclaw/hindclaw-extension \
#     --target dev \
#     build/hindsight/.upstream
#
# Both targets must be passed explicitly (see Section 6 of the design
# spec) so a future stage reorder cannot silently flip the default.

FROM prod AS dev

USER root
# `hindclaw-ext` is satisfied by `--build-context hindclaw-ext=build/hindclaw/hindclaw-extension`
COPY --from=hindclaw-ext . /app/hindclaw-ext
# The prod venv was built with `uv sync` and has no pip — copy the uv
# binary from api-builder and drive the venv via `uv pip --python`.
COPY --from=api-builder /usr/local/bin/uv /usr/local/bin/uv
RUN uv pip uninstall --python /app/api/.venv/bin/python hindclaw-extension \
    && uv pip install --python /app/api/.venv/bin/python -e /app/hindclaw-ext
RUN chown -R hindsight:hindsight /app/hindclaw-ext
USER hindsight
