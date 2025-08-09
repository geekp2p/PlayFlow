# emulator/Dockerfile

# (0) Base image
FROM halimqarroum/docker-android:api-33-playstore

USER root

# ติดตั้งแพ็กเกจที่ต้องใช้ (รวม dhclient ผ่าน isc-dhcp-client)
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      isc-dhcp-client git dos2unix xserver-xorg-core xserver-xorg-video-dummy \
      libgl1-mesa-dri libgl1-mesa-glx x11vnc websockify netcat-openbsd dnsutils iputils-ping curl \
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

# (1) ให้บิวด์รู้จัก EMULATOR_DEVICE
ARG EMULATOR_DEVICE=emu-33-playstore
ENV EMULATOR_DEVICE=${EMULATOR_DEVICE}

# (2) ENV พื้นฐาน
ENV ANDROID_SDK_ROOT=/opt/android-sdk \
    ANDROID_HOME=/opt/android-sdk \
    ANDROID_EMULATOR_HOME=/root/.android \
    ANDROID_AVD_HOME=/root/.android/avd \
    PATH=/opt/android-sdk/cmdline-tools/latest/bin:/opt/android-sdk/emulator:/opt/android-sdk/platform-tools:$PATH

# (3) ใส่ licenses
COPY licenses/ $ANDROID_SDK_ROOT/licenses/
RUN if [ -d $ANDROID_SDK_ROOT/licenses ]; then \
      chmod -R a+r $ANDROID_SDK_ROOT/licenses && \
      mkdir -p /opt/android/licenses && \
      cp -a $ANDROID_SDK_ROOT/licenses/. /opt/android/licenses; \
    fi

# (4) เตรียม SDK + system-image + สร้าง AVD
COPY prepare-android-cache.sh /usr/local/bin/prepare-android-cache.sh
RUN chmod +x /usr/local/bin/prepare-android-cache.sh \
 && /usr/local/bin/prepare-android-cache.sh

# (5) start.sh เป็น ENTRYPOINT
COPY start.sh /usr/local/bin/start.sh
RUN dos2unix /usr/local/bin/start.sh && chmod +x /usr/local/bin/start.sh

ENTRYPOINT ["/usr/local/bin/start.sh"]

