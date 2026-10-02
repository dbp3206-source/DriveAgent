# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim AS web
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /usr/local/bin/uv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENV PATH="/app/backend/.venv/bin:$PATH"
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-17-jre-headless fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 veridra
COPY backend/pyproject.toml backend/README.md backend/uv.lock /app/backend/
COPY backend/app /app/backend/app
RUN uv sync --project /app/backend --frozen --no-dev && uv pip check --python /app/backend/.venv/bin/python
COPY backend/evals /app/backend/evals
COPY --from=web /build/dist /app/frontend/dist
RUN mkdir /app/data && chown veridra:veridra /app/data
USER veridra
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/api/health', timeout=4)"
CMD ["sh", "-c", "exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
