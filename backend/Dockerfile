# Backend image — FastAPI + uvicorn.
# Built from repo root so we can pull in /data alongside /backend:
#   docker build -f backend/Dockerfile -t word-describer-backend .

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps stay minimal — uvicorn[standard] pulls in C-extensions via wheels.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

# Install Python deps first for cache reuse.
COPY backend/pyproject.toml ./backend/pyproject.toml
RUN pip install --upgrade pip \
 && pip install \
      "fastapi>=0.115" \
      "uvicorn[standard]>=0.30" \
      "pydantic>=2.6" \
      "pydantic-settings>=2.2" \
      "httpx>=0.27" \
      "structlog>=24.1" \
      "websockets>=12.0" \
      "openai>=1.40"

# App + corpus.
COPY backend/app ./app
COPY data /data
ENV APP_CORPUS_DIR=/data

# Non-root user.
RUN useradd --create-home --uid 1001 app && chown -R app:app /app /data
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
