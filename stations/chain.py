"""Ordered station pipelines."""
import json
from pathlib import Path

from .runner import run_station


def load_chain(path):
    path = Path(path).resolve(); data = json.loads(path.read_text(encoding="utf-8"))
    return [(path.parent / item).resolve() for item in data["stations"]]


def run_chain(station_dirs, *, execute=False):
    if isinstance(station_dirs, (str, Path)):
        path = Path(station_dirs)
        station_dirs = load_chain(path) if path.suffix.lower() == ".json" else [path]
    results = []
    for station in station_dirs:
        result = run_station(station, execute=execute); results.append(result)
        if result["successes"] == 0 and result["failures"] > 0: break
    return results
