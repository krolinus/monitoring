#!/usr/bin/env python3
import json
import os
import sys
from datetime import datetime, timezone

from monitors.vierlande_monitor import VierlandeMonitor
from monitors.frischfrost_monitor import FrischFrostMonitor

MONITORS = [VierlandeMonitor, FrischFrostMonitor]


def main() -> int:
    run_results: list[dict] = []

    for MonitorClass in MONITORS:
        try:
            monitor = MonitorClass()
            monitor.run()
            run_results.append(monitor.last_result)
        except Exception as exc:
            name = getattr(MonitorClass, "name", MonitorClass.__name__)
            print(f"[{name}] Unbehandelter Fehler: {exc}", file=sys.stderr)
            run_results.append({
                "name": name,
                "success": False,
                "http_code": 0,
                "message": str(exc),
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            })

    print()
    print("================================")
    print("   MONITORING ZUSAMMENFASSUNG   ")
    print("================================")
    for r in run_results:
        icon = "✅" if r["success"] else "🔴"
        label = "OK" if r["success"] else "FEHLER"
        print(f"{icon} {r['name']:<18} – {label}")
    print("================================")

    payload = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "run_id": os.environ.get("GITHUB_RUN_ID", "local"),
        "results": run_results,
    }
    with open("run_result.json", "w") as f:
        json.dump(payload, f)

    return 0 if all(r["success"] for r in run_results) else 1


if __name__ == "__main__":
    sys.exit(main())
