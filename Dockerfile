# ---- Stage 1: Build ----
FROM python:3.13-slim AS builder

WORKDIR /build

# Build deps for cffi (needed by google-auth)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install \
    -r requirements.txt \
    gunicorn>=21.0

# ---- Stage 2: Runtime ----
FROM python:3.13-slim AS runtime

LABEL org.opencontainers.image.title="todo-list" \
      org.opencontainers.image.description="Todo list web app with Flask backend" \
      org.opencontainers.image.source="https://github.com/user/todo-list"

# Non-root user
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid 1000 --create-home appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY --chown=appuser:appuser . .

# Data directory for JSON backend persistence
RUN mkdir -p /app/data && chown appuser:appuser /app/data

USER appuser

EXPOSE 5000

# Install curl for docker-compose healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Environment defaults
ENV PYTHONUNBUFFERED=1 \
    STORAGE_BACKEND=json \
    STORAGE_PATH=/app/data/todos.json \
    PORT=5000 \
    WORKERS=2

# Production WSGI server with container entry point
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT} --workers ${WORKERS} --timeout 30 --access-logfile - --error-logfile - docker_wsgi:app"]
