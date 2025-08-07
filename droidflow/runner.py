# droidflow/runner.py
import json
import os
from engine import Engine


def main() -> None:
    apps_env = os.environ.get("DROIDFLOW_APPS", "[]")
    try:
        flows = json.loads(apps_env)
    except json.JSONDecodeError:
        flows = []
    engine = Engine(device_serial=os.environ.get("DEVICE_SERIAL"))
    for flow in flows:
        engine.run_flow(flow)


if __name__ == "__main__":
    main()