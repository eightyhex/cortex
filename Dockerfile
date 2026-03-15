# =============================================================================
# Cortex — Multi-Stage Docker Build
# =============================================================================
# Stage 1: Install dependencies (cached when pyproject.toml/uv.lock unchanged)
# Stage 2: Download embedding model (~500MB, cached separately)
# Stage 3: Lean runtime image with code + deps + model
# =============================================================================

# Stage 1: Dependencies
FROM python:3.13-slim AS deps
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Stage 2: Model download (cached separately — ~500MB, rarely changes)
FROM deps AS models
RUN uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('nomic-ai/nomic-embed-text-v1.5')"

# Stage 3: Runtime
FROM python:3.13-slim AS runtime
WORKDIR /app

# Install uv in runtime for running the app
RUN pip install --no-cache-dir uv

# Copy virtualenv and cached model from build stages
COPY --from=models /app/.venv /app/.venv
COPY --from=models /root/.cache/huggingface /root/.cache/huggingface

# Copy application code, config, and vault templates
COPY src/ ./src/
COPY vault.example/ ./vault.example/
COPY settings.example.yaml ./settings.example.yaml
COPY pyproject.toml ./

# Copy and set up entrypoint
COPY scripts/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["uv", "run", "python", "-m", "cortex.main"]
