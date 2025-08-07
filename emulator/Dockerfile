# Base image with Android Play Store emulator for API 33
FROM halimqarroum/docker-android:api-33-playstore

# Set up SDK and emulator paths
ENV ANDROID_SDK_ROOT=/opt/android-sdk
ENV ANDROID_HOME=$ANDROID_SDK_ROOT
ENV ANDROID_EMULATOR_HOME=/root/.android
ENV ANDROID_AVD_HOME=/root/.android/avd
ENV PATH=$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:$ANDROID_SDK_ROOT/emulator:$ANDROID_SDK_ROOT/platform-tools:$PATH

USER root

# (Optional) Copy any pre-accepted licenses into place
COPY licenses/ $ANDROID_SDK_ROOT/licenses/
RUN if [ -d $ANDROID_SDK_ROOT/licenses ]; then \
      chmod -R a+r $ANDROID_SDK_ROOT/licenses && \
      mkdir -p /opt/android/licenses && \
      cp -a $ANDROID_SDK_ROOT/licenses/. /opt/android/licenses; \
    fi

# Install required packages, VNC server and noVNC
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      isc-dhcp-client \
      git \
      dos2unix \
      xserver-xorg-core \
      xserver-xorg-video-dummy \
      libgl1-mesa-dri \
      libgl1-mesa-glx \
      x11vnc \
      websockify \
      netcat-openbsd \
      dnsutils \
      iputils-ping \
    && rm -rf /var/lib/apt/lists/* \
    && git clone https://github.com/novnc/noVNC.git /opt/noVNC \
    && ln -sf /opt/noVNC/vnc.html /opt/noVNC/index.html \
    && sed -i \
         -e 's/var autoconnect = false;/var autoconnect = true;/' \
         -e 's/var rfbHost = .*;/var rfbHost = window.location.hostname;/' \
         -e 's/var rfbPort = .*;/var rfbPort = window.location.port;/' \
         -e 's/var rfbPassword = "";/var rfbPassword = "android";/' \
         /opt/noVNC/index.html \
    && mkdir -p /root/.vnc \
    && x11vnc -storepasswd android /root/.vnc/passwd

# Copy helper scripts into the image
COPY prepare-android-cache.sh /usr/local/bin/prepare-android-cache.sh
RUN chmod +x /usr/local/bin/prepare-android-cache.sh

COPY start.sh /usr/local/bin/start.sh
RUN dos2unix /usr/local/bin/start.sh && chmod +x /usr/local/bin/start.sh

# entrypoint หรือ CMD จะเป็นสคริปต์ start.sh
COPY start.sh /usr/local/bin/start.sh
RUN chmod +x /usr/local/bin/start.sh

# Start with our custom launch script
ENTRYPOINT []
CMD ["/usr/local/bin/start.sh"]
