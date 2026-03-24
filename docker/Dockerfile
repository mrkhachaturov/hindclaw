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
# Build context must be the patched hindsight monorepo:
#
#   docker build -t hindsight-astromech \
#     -f build/hindclaw/docker/Dockerfile \
#     build/hindsight/.upstream
#
# Requires .upstream checked out at the pinned tag (build/hindsight/UPSTREAM_VERSION).

# =============================================================================
# Stage: API Builder
# =============================================================================
FROM python:3.11-slim AS api-builder

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

COPY hindsight-api-slim/pyproject.toml ./api/
COPY hindsight-api-slim/README.md ./api/

WORKDIR /app/api

# Core deps only — no local-ml (torch/sentence-transformers), no embedded-db (pg0)
RUN uv sync

# FlashRank reranker (~50MB, no torch dependency)
RUN uv pip install "flashrank>=0.2.0"

# Hindclaw server-side access control extensions
RUN uv pip install "hindclaw-extension==0.1.3"

# Copy source and install package
COPY hindsight-api-slim/hindsight_api ./hindsight_api
RUN uv pip install -e .

# =============================================================================
# Stage: SDK Builder (TypeScript client for Control Plane)
# =============================================================================
FROM node:20-slim AS sdk-builder

WORKDIR /app

COPY package.json package-lock.json ./
COPY hindsight-clients/typescript/ ./hindsight-clients/typescript/

RUN npm ci --ignore-scripts -w @vectorize-io/hindsight-client
RUN npm run build -w @vectorize-io/hindsight-client

# =============================================================================
# Stage: Control Plane Builder (Next.js UI)
# =============================================================================
FROM node:20-slim AS cp-builder

WORKDIR /app/memory-poc/hindsight-control-plane

COPY hindsight-control-plane/package.json ./
RUN sed -i '/"@vectorize-io\/hindsight-client":/d' package.json
RUN npm install

COPY hindsight-control-plane/ ./
RUN rm -f package-lock.json && sed -i '/"@vectorize-io\/hindsight-client":/d' package.json

COPY --from=sdk-builder /app/hindsight-clients/typescript ./node_modules/@vectorize-io/hindsight-client

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
FROM python:3.11-slim

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

# Copy built SDK
COPY --from=sdk-builder /app/hindsight-clients/typescript /app/sdk

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
