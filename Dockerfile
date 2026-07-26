FROM python:3.12-slim

# Set working directory
WORKDIR /app

# System deps needed by psycopg2-binary
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Expose API port
EXPOSE 8000

# Default command (overridden in docker-compose for dev with --reload)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
