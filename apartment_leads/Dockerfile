FROM python:3.12-slim

LABEL maintainer="apartment-leads"
LABEL description="Apartment building lead-generation pipeline"

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY src/ ./src/
COPY configs/ ./configs/
COPY __main__.py .
COPY pyproject.toml .

# Create data directories
RUN mkdir -p data/cache data/processed data/raw logs

# Default environment
ENV LOG_LEVEL=INFO
ENV OUTPUT_DIR=/app/data/processed
ENV CACHE_DB_PATH=/app/data/cache/requests.db

# Expose data directory as volume for persistence
VOLUME ["/app/data", "/app/logs"]

# Default entrypoint: run the CLI
ENTRYPOINT ["python", "-m", "apartment_leads"]

# Default command: show help
CMD ["--help"]
