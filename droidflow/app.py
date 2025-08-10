# droidflow/app.py
from flask import Flask, render_template, request, jsonify
import threading
import os
import runner
from engine import Engine

app = Flask(__name__, template_folder="templates")

# Single Engine instance used by the web UI
engine = Engine(device_serial=os.environ.get("DEVICE_SERIAL"))


@app.route("/")
def index():
    """Render the main DroidFlow UI."""
    instance_name = os.environ.get("INSTANCE_NAME")
    app_list: list = []
    return render_template("index.html", instance_name=instance_name, app_list=app_list)


@app.route("/terminal")
def terminal():
    """Render a lightweight web terminal page."""
    return render_template("terminal.html")


@app.route("/run", methods=["POST"])
def run_flow():
    """Run a flow supplied as JSON payload."""
    payload = request.get_json(force=True) or {}
    engine.run_flow(payload)
    return jsonify({"status": "ok", "received": payload})


def start_runner():
    """Run automation flows in a background thread."""
    try:
        runner.main()
    except Exception:
        # Log exceptions to stderr so Docker logs capture them
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    thread = threading.Thread(target=start_runner, daemon=True)
    thread.start()
    app.run(host="0.0.0.0", port=5000)