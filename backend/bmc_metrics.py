from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .settings import BMC_STATE_FILE


class BmcCollector:
    def collect(self) -> dict[str, Any]:
        try:
            payload = json.loads(Path(BMC_STATE_FILE).read_text())
            payload["stale"] = time.time() - float(payload.get("timestamp", 0)) > 30
            if payload["stale"]:
                payload["online"] = False
                payload["error"] = "BMC sensor data is stale"
            return payload
        except (OSError, ValueError, TypeError) as error:
            return {"online": False, "stale": True, "timestamp": 0, "error": str(error), "info": {}, "power": {}, "temperatures": [], "fans": [], "voltages": [], "discrete": [], "psus": []}
