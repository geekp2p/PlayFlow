import subprocess
from flask import Flask, jsonify, render_template
from flask_socketio import SocketIO

app = Flask(__name__, template_folder="templates")
socketio = SocketIO(app, cors_allowed_origins="*")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/devices")
def devices():
    """Return list of ADB-visible devices."""
    out = subprocess.check_output(["adb", "devices"], text=True)
    lines = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) == 2 and parts[1] == "device":
            lines.append(parts[0])
    return jsonify(lines)