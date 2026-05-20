#!/usr/bin/env python3
import sys
from monitors.vierlande_monitor import VierlandeMonitor
from monitors.frischfrost_monitor import FrischFrostMonitor

MONITORS = [VierlandeMonitor, FrischFrostMonitor]


def main() -> int:
    results: list[tuple[str, bool]] = []

    for MonitorClass in MONITORS:
        try:
            monitor = MonitorClass()
            exit_code = monitor.run()
            results.append((monitor.name, exit_code == 0))
        except Exception as exc:
            name = getattr(MonitorClass, "name", MonitorClass.__name__)
            print(f"[{name}] Unbehandelter Fehler: {exc}", file=sys.stderr)
            results.append((name, False))

    print()
    print("================================")
    print("   MONITORING ZUSAMMENFASSUNG   ")
    print("================================")
    for name, ok in results:
        icon = "✅" if ok else "🔴"
        label = "OK" if ok else "FEHLER"
        print(f"{icon} {name:<18} – {label}")
    print("================================")

    return 0 if all(ok for _, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())
