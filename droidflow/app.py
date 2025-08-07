# droidflow/app.py
from flask import Flask
import threading
import runner

app = Flask(__name__)

@app.route('/')
def index():
    return 'DroidFlow service running'

def start_runner():
    """Run automation flows in a background thread."""
    try:
        runner.main()
    except Exception as exc:
        # Log exceptions to stderr so Docker logs capture them
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    thread = threading.Thread(target=start_runner, daemon=True)
    thread.start()
    app.run(host='0.0.0.0', port=5000)
