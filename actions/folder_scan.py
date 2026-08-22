import hashlib
from collections import Counter, defaultdict
from pathlib import Path


def scan_folder(folder):
    root = Path(folder).resolve(); files = [x for x in root.rglob("*") if x.is_file()]
    types, hashes, entries = Counter(), defaultdict(list), []
    for path in files:
        digest = hashlib.sha256(path.read_bytes()).hexdigest(); hashes[digest].append(str(path.relative_to(root)))
        types[path.suffix.lower() or "[no extension]"] += 1
        entries.append({"path": str(path.relative_to(root)), "size": path.stat().st_size, "sha256": digest})
    return {"root": str(root), "file_count": len(files), "total_size": sum(x["size"] for x in entries), "types": dict(types), "duplicates": [x for x in hashes.values() if len(x) > 1], "files": entries}
