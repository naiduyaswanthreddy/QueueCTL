# QueueCTL Dockerfile
# - Lightweight Python base
# - Installs dependencies and the package
# - Provides two entrypoints: web dashboard and CLI

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# System deps (add gcc if building heavy wheels; not needed here)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (leverage Docker layer caching)
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip && \
    python -m pip install -r requirements.txt

# Copy source and install in editable mode
COPY . /app
RUN python -m pip install -e .

# Expose dashboard port
EXPOSE 5000

# Volume for DB so container restarts keep data
VOLUME ["/data"]
ENV QUEUECTL_DB=/data/queuectl.db

# Default command runs the web dashboard
# To run CLI, override the command, e.g.: docker run --rm queuectl queuectl status --db /data/queuectl.db
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "queuectl.cli", "web", "start", "--port", "5000", "--db", "/data/queuectl.db"]
