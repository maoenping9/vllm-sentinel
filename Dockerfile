FROM node:22-alpine AS frontend-build
WORKDIR /build
# 2026-09-29：构建机所在网络下，容器内访问 registry.npmjs.org 会被 reset（宿主 curl 通、容器不通），
# 于是 `corepack enable` 后 pnpm 触发 corepack 去取 registry.npmjs.org/pnpm/latest 直接 UND_ERR_SOCKET、
# docker build 必失败。改为「从可覆盖的镜像源显式装指定版本 pnpm」，绕开 corepack 的联网探测。
# 境外/有专线时传 --build-arg NPM_REGISTRY=https://registry.npmjs.org 回到官方源。
# 版本固定 pnpm@12.6.0：实测可用本仓库 pnpm-lock.yaml(lockfileVersion 9.0) 做 --frozen-lockfile 安装。
ARG NPM_REGISTRY=https://registry.npmmirror.com
RUN npm config set registry "${NPM_REGISTRY}" \
    && npm install -g pnpm@12.6.0 \
    && pnpm config set registry "${NPM_REGISTRY}"
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
# 2026-09-29：构建机所在网络对 deb.debian.org 的**明文 HTTP** 会被中间代理拦成
# 501/NOSPLIT（apt 报 "Clearsigned file isn't valid"），导致 docker build 必失败；
# HTTPS 的国内镜像源可用。故把镜像源做成可覆盖的 ARG（默认阿里云 HTTPS），
# 境外/有专线时传 --build-arg APT_MIRROR=http://deb.debian.org/debian 即可回到官方源。
# 注意替换顺序：先替 debian-security（更长的具体路径），再替 debian，否则会被前缀规则吃掉。
ARG APT_MIRROR=https://mirrors.aliyun.com/debian
ARG APT_SECURITY_MIRROR=https://mirrors.aliyun.com/debian-security
# pip 同理：pypi.org 的索引本身可达，但 wheel 实际落在 files.pythonhosted.org —— 本网络下
# 该域名 ReadTimeout 重试到失败，故默认走国内镜像（同样可用 --build-arg 覆盖回官方源）。
ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
RUN set -eux; \
    sed -i -e "s|http://deb.debian.org/debian-security|${APT_SECURITY_MIRROR}|g" \
           -e "s|https://deb.debian.org/debian-security|${APT_SECURITY_MIRROR}|g" \
           -e "s|http://deb.debian.org/debian|${APT_MIRROR}|g" \
           -e "s|https://deb.debian.org/debian|${APT_MIRROR}|g" \
           /etc/apt/sources.list /etc/apt/sources.list.d/*.sources 2>/dev/null || true; \
    apt-get update && apt-get install -y --no-install-recommends ipmitool && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" --requirement /tmp/requirements.txt
COPY backend/ /app/backend/
COPY --from=frontend-build /build/dist/ /app/static/
RUN mkdir -p /data && chown -R sentinel:sentinel /app /data
USER sentinel
EXPOSE 8733
VOLUME ["/data"]
HEALTHCHECK --interval=15s --timeout=4s --start-period=15s --retries=3 CMD ["sh", "-c", "python -c \"import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:'+os.getenv('SENTINEL_PORT','8733')+'/api/health',timeout=3)\""]
CMD ["python", "-m", "backend.run"]
