from difflib import unified_diff
from pathlib import Path


def check_drift(candidate, canonical):
    before = Path(canonical).read_text(encoding="utf-8").splitlines()
    after = Path(candidate).read_text(encoding="utf-8").splitlines()
    return {"drifted": before != after, "diff": "\n".join(unified_diff(before, after, fromfile=str(canonical), tofile=str(candidate), lineterm=""))}
