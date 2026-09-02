FROM node:22-alpine AS frontend-build
WORKDIR /build
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STATIC_DIR=/app/static \
    DATA_DIR=/data \
    HOST_ROOT=/host
WORKDIR /app
RUN groupadd --system sentinel && useradd --system --gid sentinel --home /app sentinel
COPY backend/requirements.txt /tmp/requirements.txt
RUN apt-get update && apt-get install -y --no-install-recommends ipmitool && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --requirement /tmp/requirements.txt
COPY backend/ /app/backend/
COPY --from=frontend-build /build/dist/ /app/static/
RUN mkdir -p /data && chown -R sentinel:sentinel /app /data
USER sentinel
EXPOSE 8733
VOLUME ["/data"]
HEALTHCHECK --interval=15s --timeout=4s --start-period=15s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8733/api/health', timeout=3)"]
CMD ["python", "-m", "backend.run"]
