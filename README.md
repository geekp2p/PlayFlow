# PlayFlow
Dockerized Android emulator & Web UI for RPA/testing flows | สแต็ก Docker Android emulator และเว็บ UI สำหรับ RPA/Testing flows

PlayFlow provides a Dockerized Android 33 emulator with a simple web UI for controlling applications. The stack uses a standard Docker bridge network and exposes ports on the host so the emulator and web UI can be accessed directly from the host or other machines.

## Features

* Android 33 Google Play emulator
* Host-accessible services via port mapping
* Basic Flask/Socket.IO web UI exposing `adb` operations

## Quick Start

```bash
make up
```

The command builds/starts the stack and prints an endpoint table for each container. Run `make ps` at any time to show the endpoints again. Use `make down` to stop the containers.

## Services & Ports

| Container    | Service  | Port | Proto | Access                        |
|--------------|----------|------|-------|-------------------------------|
| pf_emulator  | noVNC    | 6080 | TCP   | http://<host-ip>:6080         |
| pf_emulator  | VNC      | 5900 | TCP   | vnc://<host-ip>:5900          |
| pf_emulator  | ADB      | 5037 | TCP   | `adb connect <host-ip>:5037`  |
| pf_droidflow | Flask UI | 5000 | TCP   | http://<host-ip>:5000/        |

Replace `<host-ip>` with the IP address of the machine running PlayFlow.

## Endpoints

`tools/show-endpoints.sh` probes the above ports and prints a readable table including URLs or how to access each service.

## Troubleshooting

* Ensure `curl` and `nc` (`netcat-openbsd`) are installed; the script warns if missing.
* If ADB is DOWN, set `ADB_SERVER_SOCKET=tcp:5037` before starting the server.
* For VNC issues, verify the password file `/root/.vnc/passwd`.