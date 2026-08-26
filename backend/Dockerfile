FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for scientific libraries & postgres client
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY backend /app/backend
COPY simulator /app/simulator
COPY data /app/data
COPY models /app/models

ENV PYTHONPATH=/app
ENV PORT=8000

EXPOSE 8000

# Production start command respecting dynamic Render $PORT
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
