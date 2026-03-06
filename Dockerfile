FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ .
RUN npm run build

FROM python:3.12-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ARG TARGETARCH
RUN ARCH=$(case ${TARGETARCH} in amd64) echo "amd64";; arm64) echo "arm64";; *) echo "amd64";; esac) && \
    wget -O /tmp/mihomo.gz "https://github.com/MetaCubeX/mihomo/releases/download/v1.19.0/mihomo-linux-${ARCH}-v1.19.0.gz" && \
    gunzip /tmp/mihomo.gz && \
    mv /tmp/mihomo /app/mihomo && \
    chmod +x /app/mihomo

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY --from=frontend-builder /app/frontend/dist frontend/dist

RUN mkdir -p data/mihomo

EXPOSE 8080 9090
EXPOSE 7901-8100

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
