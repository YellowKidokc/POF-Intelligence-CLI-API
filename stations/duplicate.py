"""Duplicate a station's configuration and support files, never its work."""
import json
import shutil
from pathlib import Path

WORK_DIRS = {"inbox", "waiting", "outbox", "failed", "receipts"}


def duplicate_station(source, new_name, *, description="", chain_after=None):
    source = Path(source).resolve(); target = source.parent / new_name
    if target.exists(): raise FileExistsError(target)
    target.mkdir(parents=True)
    for child in source.iterdir():
        if child.name in WORK_DIRS: continue
        destination = target / child.name
        if child.is_dir(): shutil.copytree(child, destination)
        else: shutil.copy2(child, destination)
    for name in WORK_DIRS: (target / name).mkdir(parents=True, exist_ok=True)
    config_path = target / "station.json"; config = json.loads(config_path.read_text(encoding="utf-8"))
    config["name"] = new_name; config["description"] = description
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    if chain_after:
        prior = Path(chain_after).resolve(); prior_config_path = prior / "station.json"
        prior_config = json.loads(prior_config_path.read_text(encoding="utf-8"))
        prior_config["on_success"] = str(Path("..") / new_name / "inbox").replace("\\", "/")
        prior_config_path.write_text(json.dumps(prior_config, indent=2) + "\n", encoding="utf-8")
    return target
