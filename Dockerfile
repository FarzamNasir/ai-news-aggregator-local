# ── Build stage ──────────────────────────────────────────────
FROM python:3.12-slim AS builder

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first (cache-friendly)
COPY pyproject.toml uv.lock* ./

# Install dependencies
RUN uv sync --no-dev --no-install-project

# Copy the rest of the application
COPY . .

# Install the project itself
RUN uv sync --no-dev

# ── Runtime stage ────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Copy the virtual environment and app from builder
COPY --from=builder /app /app

# Use the virtual environment's Python
ENV PATH="/app/.venv/bin:$PATH"

# Default command: run the full pipeline once
CMD ["python", "-m", "app.runner"]
