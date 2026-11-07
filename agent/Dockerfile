# syntax=docker/dockerfile:1
# =============================================================================
# auto-monitor agent (Python 3.12 / FastAPI) - hardened image
#  - OS packages patched, apt lists removed, pip cache disabled
#  - runs as uid 1000 "app", code owned by root (read-only for the process)
# =============================================================================
FROM python:3.12-slim
LABEL org.opencontainers.image.title="auto-monitor-agent" \
      org.opencontainers.image.description="Autonomous agent of auto-monitor" \
      org.opencontainers.image.licenses="MIT"
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update \
 && apt-get upgrade -y \
 && apt-get install -y --no-install-recommends git \
 && rm -rf /var/lib/apt/lists/* \
 && useradd -m -u 1000 app
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app ./app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/healthz', timeout=3)" || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
