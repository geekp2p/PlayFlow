# Use slim Python image
FROM python:3.11-slim

# Install adb and Python build deps
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      android-tools-adb \
      curl \
      build-essential \
      python3-dev \
      isc-dhcp-client \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Create directory for APKs
RUN mkdir -p /apks

# Copy Python requirements and install
COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Make entrypoint script executable
RUN chmod +x docker-entrypoint.sh

# Expose the web UI port
EXPOSE 5000

# Launch entrypoint
ENTRYPOINT ["./docker-entrypoint.sh"]
