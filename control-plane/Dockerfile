# Phase 2 — FastAPI control-plane image (build from repo root).
FROM python:3.12-slim
WORKDIR /app

COPY control-plane/requirements.txt /app/control-plane/requirements.txt
RUN pip install --no-cache-dir -r /app/control-plane/requirements.txt

COPY packages /app/packages
COPY templates /app/templates
COPY control-plane /app/control-plane

ENV PYTHONPATH=/app
ENV AF_PORT=8080
ENV AF_DOCKER_DRIVER=off
WORKDIR /app/control-plane
EXPOSE 8080
CMD ["python", "main.py"]
