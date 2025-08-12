# Use slim Python image
FROM python:3.11-slim

# OS deps: dhclient (ผ่าน isc-dhcp-client), adb, build tools, netcat, curl, bash
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      android-tools-adb \
      build-essential \
      python3-dev \
      isc-dhcp-client \
      iproute2 \
      netcat-openbsd \
      unzip \
      bash \
    && rm -rf /var/lib/apt/lists/* \
 && curl -fsSL https://dl.google.com/android/repository/platform-tools-latest-linux.zip -o /tmp/pt.zip \
 && unzip /tmp/pt.zip -d /opt/android-sdk \
 && rm /tmp/pt.zip

# Ensure our platform-tools adb is used first
ENV PATH=/opt/android-sdk/platform-tools:$PATH

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

# ติดตั้ง entrypoint ไว้ใน PATH และทำให้ executable
RUN cp docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

# Make entrypoint script executable
RUN chmod +x docker-entrypoint.sh

# Expose the web UI port
EXPOSE 5000

# Launch entrypoint
ENTRYPOINT ["./docker-entrypoint.sh"]
