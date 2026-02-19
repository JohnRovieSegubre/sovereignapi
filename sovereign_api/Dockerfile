# Use an official lightweight Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose the Gateway port
EXPOSE 8000

# Metadata
LABEL maintainer="Sovereign AI"
LABEL version="1.0"

# The command is overridden in docker-compose.yml
CMD ["python", "gateway_server.py"]
