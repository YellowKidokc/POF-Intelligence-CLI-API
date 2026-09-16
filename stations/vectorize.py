"""Small, dependency-free SQLite vector store."""
import hashlib
import math
import sqlite3
import struct
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "CREATE TABLE IF NOT EXISTS vectors (path TEXT PRIMARY KEY, sha256 TEXT NOT NULL, model TEXT NOT NULL, dim INTEGER NOT NULL, vector BLOB NOT NULL, created TEXT NOT NULL)"


class VectorStore:
    def __init__(self, station, profile_name="openai", model="text-embedding-3-small", provider=None, config_path=None):
        self.station = Path(station).resolve(); self.model = model
        self.connection = sqlite3.connect(self.station / "vectors.sqlite"); self.connection.execute(SCHEMA); self.connection.commit()
        if provider is None:
            from cli import ROOT, profile
            from providers import create_provider
            settings = profile(config_path or ROOT / "config.ini", profile_name)
            provider = create_provider(settings["provider"], settings["api_key"], settings["base_url"] or None)
        self.provider = provider

    def add(self, paths):
        changed = []
        for path in map(lambda p: Path(p).resolve(), paths):
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            row = self.connection.execute("SELECT sha256,model FROM vectors WHERE path=?", (str(path),)).fetchone()
            if row != (digest, self.model): changed.append((path, digest))
        if not changed: return {"embedded": 0, "skipped": len(paths)}
        vectors = self.provider.embed([p.read_text(encoding="utf-8", errors="replace") for p, _ in changed], self.model)
        now = datetime.now(timezone.utc).isoformat()
        for (path, digest), vector in zip(changed, vectors):
            blob = struct.pack(f"<{len(vector)}f", *vector)
            self.connection.execute("INSERT OR REPLACE INTO vectors VALUES (?,?,?,?,?,?)", (str(path), digest, self.model, len(vector), blob, now))
        self.connection.commit(); return {"embedded": len(changed), "skipped": len(paths) - len(changed)}

    def search(self, query, top_k=10):
        query_vector = self.provider.embed([query], self.model)[0]; qnorm = math.sqrt(sum(x*x for x in query_vector)) or 1
        results = []
        for path, dim, blob in self.connection.execute("SELECT path,dim,vector FROM vectors WHERE model=?", (self.model,)):
            vector = struct.unpack(f"<{dim}f", blob); norm = math.sqrt(sum(x*x for x in vector)) or 1
            score = sum(a*b for a, b in zip(query_vector, vector)) / (qnorm * norm)
            results.append({"path": path, "score": score})
        return sorted(results, key=lambda row: row["score"], reverse=True)[:top_k]


def vectorize_folder(folder, station=None, execute=False, **kwargs):
    folder = Path(folder).resolve(); paths = [p for p in folder.rglob("*") if p.is_file()]
    if not execute: return {"status": "dry_run", "files": len(paths)}
    return VectorStore(station or folder.parent, **kwargs).add(paths)
