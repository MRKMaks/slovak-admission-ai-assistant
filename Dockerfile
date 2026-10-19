FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install uv from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install LibreOffice for PDF conversion and other system dependencies
RUN apt-get update && \
    apt-get install -y libreoffice libreoffice-writer --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies with uv (creates .venv in /app)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Copy application code
COPY . .

# Expose API port
EXPOSE 8000

# Run Uvicorn from the uv virtual environment
CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
