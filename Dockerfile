# ============================================
# Python backend + serve pre-built frontend
# ============================================
FROM python:3.12-slim

WORKDIR /app

# Install backend deps
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy backend code
COPY backend/ /app/backend/

# Copy ALREADY BUILT frontend (we push this directly to GitHub now)
COPY dist/ /app/dist/

# Set working directory to backend
WORKDIR /app/backend

# Railway sets PORT env var dynamically
ENV PORT=8000

EXPOSE ${PORT}

CMD python -m uvicorn main:app --host 0.0.0.0 --port $PORT
