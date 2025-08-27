# apps/etl/Dockerfile
# - Python 3.12 slim, non-root, reproducible-ish
# - OCI labels, tini, pip 최적화
# - CSV는 런타임에 PVC로 마운트 (이미지에 포함 X)

FROM python:3.12-slim AS base

ARG APP_NAME="carbon-etl"
ARG APP_VERSION="0.1.0"
ARG VCS_REF
ARG BUILD_DATE

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 필요한 최소 패키지 (pandas/psycopg[binary]는 빌드툴 없이 wheel로 설치 가능)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl tini && \
    rm -rf /var/lib/apt/lists/*

# OCI 표준 라벨
LABEL org.opencontainers.image.title=$APP_NAME \
      org.opencontainers.image.version=$APP_VERSION \
      org.opencontainers.image.created=$BUILD_DATE \
      org.opencontainers.image.revision=$VCS_REF \
      org.opencontainers.image.source="https://github.com/<ORG>/<REPO>" \
      org.opencontainers.image.licenses="MIT"

# 비루트 유저
RUN useradd -ms /bin/bash appuser
WORKDIR /app

# 의존성 먼저 설치(캐시 최적화)
COPY apps/etl/requirements.txt /app/requirements.txt
RUN pip install -U pip wheel setuptools && \
    pip install --no-cache-dir -r /app/requirements.txt

# 코드 복사 (소유권 지정)
COPY --chown=appuser:appuser apps/etl/csv_to_pg /app/csv_to_pg

# 런 스크립트 (테이블 생성 -> 적재)
RUN printf '%s\n' \
  '#!/usr/bin/env bash' \
  'set -euo pipefail' \
  'echo "[ENTRY] CSV_PATH=${CSV_PATH:-unset} CSV_TABLE=${CSV_TABLE:-unset}"' \
  'if [[ -z "${CSV_PATH:-}" ]]; then echo "[ERROR] CSV_PATH not set"; exit 2; fi' \
  'python -m csv_to_pg.create_table_from_csv' \
  'python -m csv_to_pg.load_csv_to_db' \
  > /app/run_etl.sh && chmod +x /app/run_etl.sh

# 디폴트 환경변수(쿠버네티스에서 override)
ENV CSV_ENCODING=utf-8 CSV_SEP=, CSV_CHUNKSIZE=2000

USER appuser
ENTRYPOINT ["/usr/bin/tini","--"]
CMD ["/app/run_etl.sh"]
