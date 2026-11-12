# =============================================================================
# Production Multi-Stage Containerfile for AttendSure Cloud Deployment
# =============================================================================
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

# Install security updates and curl for container health check
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copy package specifications
COPY pyproject.toml requirements.txt* ./

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools && \
    pip install --no-cache-dir -e .

# Copy source code and documentation
COPY src/ /app/src/
COPY data/ /app/data/
COPY .streamlit/ /app/.streamlit/

# Create dedicated persistent storage directory and non-root application user
RUN mkdir -p /app/data/backups && \
    useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["streamlit", "run", "src/attendsure/ui/app.py"]

