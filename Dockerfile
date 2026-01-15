# ATLAS Full Stack Dockerfile for Railway
# Builds both UI and API, serves everything from one container

# Stage 1: Build the UI
FROM node:20-slim AS ui-builder

WORKDIR /ui

# Copy UI package files
COPY apps/ui/package*.json ./

# Install dependencies
RUN npm ci

# Copy UI source
COPY apps/ui/ ./

# Build the UI (outputs to dist/)
RUN npm run build


# Stage 2: Build and run the API
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy API pyproject.toml
COPY apps/api/pyproject.toml ./

# Create src directory structure
RUN mkdir -p src/atlas

# Copy API source code
COPY apps/api/src/atlas ./src/atlas

# Install Python dependencies
RUN pip install --no-cache-dir -e ".[postgres]"

# Copy built UI from previous stage
COPY --from=ui-builder /ui/dist ./static

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PORT=8000

# Expose port
EXPOSE 8000

# Run the application
CMD uvicorn atlas.main:app --host 0.0.0.0 --port $PORT
