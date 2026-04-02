# ============================================
# Stage 1: Build frontend (Vite/React)
# ============================================
FROM node:22-slim AS frontend-build

WORKDIR /app

# Copy package files (including lockfile if it exists)
COPY package*.json ./

# Limit Node memory to avoid OOM (exit code 137) on Railway builders
ENV NODE_OPTIONS="--max-old-space-size=350"

# Install deps and build using 'ci' which is much faster and uses less RAM than 'install'
RUN npm ci --no-fund --no-audit
COPY . .
RUN npx vite build

# ============================================
# Stage 2: Python backend + serve frontend
# ============================================
FROM python:3.12-slim

WORKDIR /app

# Install backend deps
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy backend code
COPY backend/ /app/backend/

# Copy frontend build from stage 1
COPY --from=frontend-build /app/dist /app/dist

# Set working directory to backend
WORKDIR /app/backend

# Railway sets PORT env var dynamically
ENV PORT=8000

EXPOSE ${PORT}

CMD python -m uvicorn main:app --host 0.0.0.0 --port $PORT
