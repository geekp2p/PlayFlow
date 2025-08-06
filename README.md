# PlayFlow
Dockerized Android emulator  Web UI for RPA/testing flows | สแต็ก Docker Android emulator  เว็บ UI สำหรับ RPA/Testing flows



PlayFlow provides a Dockerized Android 33 emulator with a simple web UI for
controlling applications.  The container joins a `macvlan` network and obtains
its IP address from a Mikrotik router on `192.168.88.0/24` via DHCP.

## Features

* Android 33 Google Play emulator
* DHCP networking through `macvlan88` (Mikrotik as DHCP server)
* Basic Flask/Socket.IO web UI exposing `adb` operations

## Usage

1. Create the `macvlan88` network on the Docker host:

   ```bash
   docker network create -d macvlan \
     --subnet=192.168.88.0/24 \
     --gateway=192.168.88.1 \
     -o parent=eth0 macvlan88
   ```

2. Build and launch the container:

   ```bash
   docker compose up --build
   ```

3. Access the web UI from the assigned IP on port `5000`.

