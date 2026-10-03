FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for SQLite, Playwright, and building wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser dependencies and chromium
RUN playwright install-deps chromium && playwright install chromium

# Copy backend application code and migration configuration
COPY . .

# Ensure storage directories exist
RUN mkdir -p /app/data /app/storage/snapshots /app/storage/diffs /app/storage/logs

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
