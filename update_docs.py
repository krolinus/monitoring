#!/usr/bin/env python3
"""Append the latest run_result.json entry to docs/history.json."""
import json
from pathlib import Path

HISTORY_FILE = Path("docs/history.json")
RESULT_FILE = Path("run_result.json")
MAX_ENTRIES = 100

HISTORY_FILE.parent.mkdir(exist_ok=True)

with open(RESULT_FILE) as f:
    current = json.load(f)

history = []
if HISTORY_FILE.exists():
    with open(HISTORY_FILE) as f:
        history = json.load(f)

history.insert(0, current)
history = history[:MAX_ENTRIES]

with open(HISTORY_FILE, "w") as f:
    json.dump(history, f, indent=2)

print(f"history.json aktualisiert: {len(history)} Einträge")
