import json, time
from pathlib import Path


def watch(registry, handler):
    """Poll configured folders, using an exclusive lock per folder."""
    configs = json.loads(Path(registry).read_text(encoding="utf-8")); seen = set()
    while True:
        for config in configs:
            folder = Path(config["path"]); folder.mkdir(parents=True, exist_ok=True)
            lock = folder / ".pof.lock"
            try: fd = lock.open("x")
            except FileExistsError: continue
            try:
                for item in folder.iterdir():
                    if item.is_file() and item != lock and str(item) not in seen:
                        handler(item, config); seen.add(str(item))
            finally: fd.close(); lock.unlink(missing_ok=True)
        time.sleep(1)
