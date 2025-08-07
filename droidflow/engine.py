# droidflow/engine.py
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class Engine:
    """Very small stub engine that logs requested flows."""

    def __init__(self, device_serial: str | None = None) -> None:
        self.device_serial = device_serial
        if device_serial:
            logger.info("Engine initialised for device %s", device_serial)

    def run_flow(self, flow: Dict[str, Any]) -> None:
        """Log execution of a flow. Actual automation is out of scope."""
        label = flow.get("label", "<unknown>")
        pkg = flow.get("pkg", "<no-pkg>")
        logger.info("Running flow %s (%s) on device %s", label, pkg, self.device_serial)
        # Placeholder for real automation logic
