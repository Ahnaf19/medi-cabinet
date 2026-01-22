# Multi-stage build for Medi-Cabinet Bot

# Builder stage
FROM python:3.11-slim as builder

# Install uv
RUN pip install --no-cache-dir uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml .

# Install dependencies with uv
RUN uv sync --no-dev

# Runtime stage
FROM python:3.11-slim

# Install necessary system dependencies
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY src/ src/
COPY config/ config/
COPY migrations/ migrations/
COPY alembic.ini .
COPY run.py .

# Create necessary directories
RUN mkdir -p logs backups data

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Run database migrations and start bot
CMD ["sh", "-c", "alembic upgrade head && python run.py"]
