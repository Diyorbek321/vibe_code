# ── Stage 1: Build React frontend ─────────────────────────────────────────────
FROM node:20-slim AS frontend-builder

WORKDIR /frontend

# Copy package files (handle "finance(1)" directory name)
COPY finance\(1\)/package*.json ./
RUN npm ci --silent

COPY finance\(1\)/ ./

# VITE_API_URL="" means all /api calls go to same origin (no CORS needed)
ENV VITE_API_URL=""
RUN npm run build


# ── Stage 2: Build Python dependencies ────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 3: Runtime ───────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

RUN addgroup --system app && adduser --system --ingroup app app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Python packages
COPY --from=builder /install /usr/local

# Application source
COPY --chown=app:app . .

# Built frontend → served as static files by FastAPI
COPY --from=frontend-builder /frontend/dist /app/static

RUN mkdir -p logs && chown app:app logs

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--loop", "asyncio"]
