FROM halimqarroum/docker-android:api-33-playstore

USER root

# Install Python and tools for DHCP
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      python3 python3-pip python3-dev dhclient \
 && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# Application code
COPY app /app
COPY start.sh /start.sh
RUN chmod +x /start.sh

WORKDIR /app

ENTRYPOINT ["/start.sh"]
