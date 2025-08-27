# apps/frontend/Dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates tini && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY apps/frontend/requirements.txt /app/requirements.txt
RUN pip install -U pip wheel setuptools && pip install -r /app/requirements.txt

COPY apps/frontend/ /app/
ENV FRONTEND_PORT=8501
EXPOSE 8501

USER root
ENTRYPOINT ["/usr/bin/tini","--"]
CMD ["bash","-lc","streamlit run /app/streamlit_app.py --server.port=${FRONTEND_PORT} --server.address=0.0.0.0 --server.headless=true"]
