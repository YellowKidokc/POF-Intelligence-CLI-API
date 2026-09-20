"""Audited, reversible filesystem operations."""
import hashlib, json, shutil
from datetime import datetime, timezone
from pathlib import Path


class FileRouter:
    def __init__(self, root=".", ledger=None):
        self.root = Path(root); self.receipts = self.root / "receipts"; self.receipts.mkdir(parents=True, exist_ok=True)
        self.undo_log = self.root / "undo_log.jsonl"; self.ledger = ledger

    @staticmethod
    def hash(path):
        h = hashlib.sha256()
        with Path(path).open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""): h.update(chunk)
        return h.hexdigest()

    def _run(self, operation, source, dest, dry_run=True, reversible=True):
        source, dest = Path(source).resolve(), Path(dest).resolve()
        if not source.exists(): raise FileNotFoundError(source)
        if dest.is_dir(): dest = dest / source.name
        if source == dest or dest.exists():
            raise FileExistsError(f'Destination already exists; refusing overwrite: {dest}')
        digest = self.hash(source) if source.is_file() else None
        stamp = datetime.now(timezone.utc); status = "dry_run" if dry_run else "success"
        receipt = {"source_path": str(source), "dest_path": str(dest), "source_hash": digest, "operation": operation, "timestamp": stamp.isoformat(), "reversible": reversible, "undo_command": f'move "{dest}" "{source}"' if reversible else None, "status": status}
        receipt_path = self.receipts / f'{stamp.strftime("%Y%m%dT%H%M%S%fZ")}_{operation}.json'
        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            (shutil.copy2 if operation == "copy" else shutil.move)(source, dest)
            if digest and self.hash(dest) != digest:
                raise RuntimeError(f'Destination hash mismatch: {dest}')
            if reversible:
                with self.undo_log.open("a", encoding="utf-8") as out: out.write(json.dumps({"op": operation, "from": str(source), "to": str(dest), "ts": stamp.isoformat(), "undone": False}) + "\n")
        receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        if self.ledger: self.ledger.record(f"file_{operation}", provider="file_router", source_path=str(source), dest_path=str(dest), status=status, receipt_path=str(receipt_path))
        return receipt

    def move(self, source, dest, dry_run=True): return self._run("move", source, dest, dry_run)
    def copy(self, source, dest, dry_run=True): return self._run("copy", source, dest, dry_run, False)
    def rename(self, source, new_name, dry_run=True): return self.move(source, Path(source).parent / new_name, dry_run)
    def archive(self, source, dry_run=True): return self._run("archive", source, self.root / "archive" / Path(source).name, dry_run)

    def undo(self, count=1, dry_run=False):
        if count < 1:
            raise ValueError('Undo count must be positive')
        lines = [json.loads(x) for x in self.undo_log.read_text(encoding="utf-8").splitlines()] if self.undo_log.exists() else []
        candidates = [i for i, x in enumerate(lines) if not x.get("undone") and x["op"] != "copy"][-count:]
        results = []
        for i in reversed(candidates):
            item = lines[i]; source, dest = Path(item["to"]), Path(item["from"])
            if dest.exists():
                raise FileExistsError(f'Undo destination already exists: {dest}')
            if not dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True); shutil.move(source, dest); item["undone"] = True
            results.append({"from": str(source), "to": str(dest), "status": "dry_run" if dry_run else "success"})
        if not dry_run: self.undo_log.write_text("".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8")
        return results
