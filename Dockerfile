# ATLAS API Dockerfile for Railway deployment
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy API pyproject.toml first for better caching
COPY apps/api/pyproject.toml ./

# Create src directory structure
RUN mkdir -p src/atlas

# Copy API source code
COPY apps/api/src/atlas ./src/atlas

# Install Python dependencies
RUN pip install --no-cache-dir -e ".[postgres]"

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PORT=8000

# Expose port
EXPOSE 8000

# Run the application - use shell form to allow PORT variable substitution
CMD uvicorn atlas.main:app --host 0.0.0.0 --port $PORT
