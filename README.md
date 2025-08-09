 # PlayFlow
 Dockerized Android emulator  Web UI for RPA/testing flows | สแต็ก Docker Android emulator  เว็บ UI สำหรับ RPA/Testing flows
 
PlayFlow provides a Dockerized Android 33 emulator with a simple web UI for controlling applications.  The container joins a `macvlan` network and obtains its IP address from a Mikrotik router on `192.168.88.0/24` via DHCP.
 
 ## Features
 
 * Android 33 Google Play emulator
 * DHCP networking through `macvlan88` (Mikrotik as DHCP server)
 * Basic Flask/Socket.IO web UI exposing `adb` operations
 
-## Usage
## Quick Start

```bash
make up
```

The command builds/starts the stack and prints an endpoint table for each container. Run `make ps` at any time to show the endpoints again. Use `make down` to stop the containers.
 
-1. Create the `macvlan88` network on the Docker host:
## Services & Ports
 
-   ```bash
-   docker network create -d macvlan \
-     --subnet=192.168.88.0/24 \
-     --gateway=192.168.88.1 \
-     -o parent=eth0 macvlan88
-   ```
| Container    | Service  | Port | Proto | Access                          |
|--------------|----------|------|-------|---------------------------------|
| pf_emulator  | noVNC    | 6080 | TCP   | http://<IP>:6080                |
| pf_emulator  | VNC      | 5900 | TCP   | vnc://<IP>:5900                 |
| pf_emulator  | ADB      | 5037 | TCP   | `adb connect <IP>:5037`         |
| pf_droidflow | Flask UI | 5000 | TCP   | http://<IP>:5000/               |
 
-2. Build and launch the container:
## Endpoints
 
-   ```bash
-   docker compose up --build
-   ```
`tools/show-endpoints.sh` collects IP addresses from network `macvlan88`, probes the above ports, and prints a readable table including URLs or how to access each service.
 
-3. Access the web UI from the assigned IP on port `5000`.
## Troubleshooting
 
* Ensure `curl` and `nc` (`netcat-openbsd`) are installed; the script warns if missing.
* If ADB is DOWN, set `ADB_SERVER_SOCKET=tcp:5037` before starting the server.
* For VNC issues, verify the password file `/root/.vnc/passwd`.
* Hosts on `macvlan` may not reach containers directly; use another LAN device.
