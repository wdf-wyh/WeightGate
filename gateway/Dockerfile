# Phase 2 — FastAPI gateway image (build from repo root).
FROM python:3.12-slim
WORKDIR /app

COPY gateway/requirements.txt /app/gateway/requirements.txt
RUN pip install --no-cache-dir -r /app/gateway/requirements.txt

COPY packages /app/packages
COPY templates /app/templates
COPY gateway /app/gateway

ENV PYTHONPATH=/app
ENV AF_PORT=8000
WORKDIR /app/gateway
EXPOSE 8000
CMD ["python", "main.py"]
