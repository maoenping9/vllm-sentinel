from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from .settings import BMC_SAMPLE_INTERVAL, BMC_STATE_FILE


def _run(*args: str) -> str:
    result = subprocess.run(
        ["ipmitool", *args], capture_output=True, text=True, timeout=12, check=True
    )
    return result.stdout


def _number(value: str) -> float | None:
    match = re.search(r"-?\d+(?:\.\d+)?", value)
    return float(match.group()) if match else None


def _sensor_rows(raw: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in raw.splitlines():
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 4:
            continue
        value = _number(parts[1]) if parts[1].lower() not in {"na", "no reading"} else None
        rows.append({
            "name": parts[0], "value": value, "units": parts[2], "status": parts[3].lower(),
            "lower_non_recoverable": _number(parts[4]) if len(parts) > 4 else None,
            "lower_critical": _number(parts[5]) if len(parts) > 5 else None,
            "lower_warning": _number(parts[6]) if len(parts) > 6 else None,
            "upper_warning": _number(parts[7]) if len(parts) > 7 else None,
            "upper_critical": _number(parts[8]) if len(parts) > 8 else None,
            "upper_non_recoverable": _number(parts[9]) if len(parts) > 9 else None,
        })
    return rows


def _power(raw: str) -> dict[str, Any]:
    def find(label: str) -> float:
        match = re.search(rf"{label}:\s+(\d+)\s+Watts", raw, re.IGNORECASE)
        return float(match.group(1)) if match else 0.0
    period = re.search(r"Sampling period:\s+(\d+)\s+Seconds", raw, re.IGNORECASE)
    state = re.search(r"Power reading state is:\s+(.+)", raw, re.IGNORECASE)
    return {
        "instant_w": find("Instantaneous power reading"),
        "minimum_w": find("Minimum during sampling period"),
        "maximum_w": find("Maximum during sampling period"),
        "average_w": find("Average power reading over sample period"),
        "sampling_seconds": float(period.group(1)) if period else 0,
        "state": state.group(1).strip() if state else "unknown",
    }


def _key_values(raw: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in raw.splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip() and value.strip():
            result[key.strip().lower().replace(" ", "_")] = value.strip()
    return result


def _psus(raw: str) -> list[dict[str, Any]]:
    rows = []
    for line in raw.splitlines():
        parts = [part.strip() for part in line.split("|")]
        if len(parts) >= 4:
            rows.append({"name": parts[0], "status": parts[2].lower(), "detail": parts[3]})
    return rows


def collect() -> dict[str, Any]:
    sensors = _sensor_rows(_run("sensor", "list"))
    return {
        "online": True, "timestamp": time.time(), "error": "",
        "info": _key_values(_run("mc", "info")),
        "power": _power(_run("dcmi", "power", "reading")),
        "temperatures": [row for row in sensors if row["units"].lower() == "degrees c" and row["value"] is not None],
        "fans": [row for row in sensors if row["units"].upper() == "RPM" and row["value"] is not None],
        "voltages": [row for row in sensors if row["units"].lower() == "volts" and row["value"] is not None],
        "discrete": [row for row in sensors if row["units"].lower() == "discrete"],
        "psus": _psus(_run("sdr", "type", "Power Supply")),
    }


def write_state(payload: dict[str, Any]) -> None:
    path = Path(BMC_STATE_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, separators=(",", ":")))
    os.replace(temporary, path)


def main() -> None:
    while True:
        started = time.time()
        try:
            write_state(collect())
        except Exception as error:
            write_state({"online": False, "timestamp": time.time(), "error": str(error), "info": {}, "power": {}, "temperatures": [], "fans": [], "voltages": [], "discrete": [], "psus": []})
        time.sleep(max(0.2, BMC_SAMPLE_INTERVAL - (time.time() - started)))


if __name__ == "__main__":
    main()
