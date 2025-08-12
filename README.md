# PlayFlow
Dockerized Android emulator & Web UI for RPA/testing flows | สแต็ก Docker Android emulator และเว็บ UI สำหรับ RPA/Testing flows

PlayFlow provides a Dockerized Android 33 emulator with a simple web UI for controlling applications. The stack uses a standard Docker bridge network and exposes ports on the host so the emulator and web UI can be accessed directly from the host or other machines.

## Features

* Android 33 Google Play emulator
* Host-accessible services via port mapping
* Basic Flask/Socket.IO web UI exposing `adb` operations

## Host Setup (Ubuntu)

On a fresh Ubuntu host run the helper script once to install Docker, the
Compose plugin and utilities such as `scrcpy`:

```bash
./setup_host.sh
```

The script installs required packages and ensures the `scrcpy-server.jar`
file is available. Host-side ADB is **not** needed; all ADB commands run
inside the containers.

## Quick Start

```bash
make up
```

The command builds/starts the stack and prints an endpoint table for each container. Run `make ps` at any time to show the endpoints again. Use `make down` to stop the containers.

### Using ADB inside the container

To interact with a connected Android device directly from the `pf_droidflow` container and reverse port `5000` for the web UI, run:

```bash
./start_host.sh
```

The script stops any host-side ADB server, starts the Docker stack, launches an ADB server inside `pf_droidflow`, and performs `adb reverse tcp:5000 tcp:5000` so apps on the device can reach the web UI at `http://127.0.0.1:5000`.

## Services & Ports

| Container    | Service  | Port | Proto | Access                        |
|--------------|----------|------|-------|-------------------------------|
| pf_emulator  | noVNC    | 6080 | TCP   | http://<host-ip>:6080         |
| pf_emulator  | VNC      | 5900 | TCP   | vnc://<host-ip>:5900          |
| pf_droidflow | Flask UI | 5000 | TCP   | http://<host-ip>:5000/        |

Replace `<host-ip>` with the IP address of the machine running PlayFlow. ADB is now internal to the stack; for direct commands run `docker exec pf_droidflow adb ...`.

## Endpoints

`tools/show-endpoints.sh` probes the above ports and prints a readable table including URLs or how to access each service.

## Troubleshooting

* Ensure `curl` and `nc` (`netcat-openbsd`) are installed; the script warns if missing.
* If ADB is DOWN or you see `ECONNREFUSED` errors, ensure the emulator is
  reachable on the Docker network. The droidflow container now starts its own
  ADB server and connects to `pf_emulator:5555` automatically.
* Python tools rely on the `adbutils` library which talks to the local `adb`
  server. When running Python manually inside the container, ensure the
  emulator is connected by issuing `adb connect pf_emulator:5555` first.
* For VNC issues, verify the password file `/root/.vnc/passwd`.
* For high-performance video streaming, install `scrcpy` or set
  `SCRCPY_SERVER_JAR` to the path of `scrcpy-server.jar`. On Ubuntu the file is
  typically located under `/usr/local/share/scrcpy/scrcpy-server.jar` or
  `/usr/share/scrcpy/scrcpy-server.jar`.