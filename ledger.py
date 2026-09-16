import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """CREATE TABLE IF NOT EXISTS operations (id INTEGER PRIMARY KEY,timestamp TEXT NOT NULL,operation TEXT NOT NULL,provider TEXT,model TEXT,profile TEXT,input_hash TEXT,output_hash TEXT,input_tokens INTEGER,output_tokens INTEGER,cost_usd REAL,source_path TEXT,dest_path TEXT,status TEXT,error_message TEXT,receipt_path TEXT,duration_seconds REAL,station TEXT,item TEXT);
CREATE TABLE IF NOT EXISTS cumulative_costs (provider TEXT PRIMARY KEY,total_calls INTEGER DEFAULT 0,total_input_tokens INTEGER DEFAULT 0,total_output_tokens INTEGER DEFAULT 0,total_cost_usd REAL DEFAULT 0.0,last_call TEXT);"""


class Ledger:
    def __init__(self, path="ledger.sqlite"):
        self.path = Path(path); self.connection = sqlite3.connect(self.path)
        self.connection.executescript(SCHEMA)
        columns = {row[1] for row in self.connection.execute("PRAGMA table_info(operations)")}
        for name in ("station", "item"):
            if name not in columns: self.connection.execute(f"ALTER TABLE operations ADD COLUMN {name} TEXT")
        self.connection.commit()

    def record(self, operation, **values):
        now = datetime.now(timezone.utc).isoformat()
        fields = ["timestamp", "operation"] + list(values)
        self.connection.execute(f"INSERT INTO operations ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})", [now, operation, *values.values()])
        if operation == "api_call" and values.get("status") == "success":
            self.connection.execute("""INSERT INTO cumulative_costs VALUES (?,?,?,?,?,?) ON CONFLICT(provider) DO UPDATE SET total_calls=total_calls+1,total_input_tokens=total_input_tokens+excluded.total_input_tokens,total_output_tokens=total_output_tokens+excluded.total_output_tokens,total_cost_usd=total_cost_usd+excluded.total_cost_usd,last_call=excluded.last_call""", (values.get("provider"), 1, values.get("input_tokens", 0), values.get("output_tokens", 0), values.get("cost_usd", 0), now))
        self.connection.commit()

    def stats(self):
        columns = [x[0] for x in self.connection.execute("SELECT * FROM cumulative_costs").description]
        return [dict(zip(columns, row)) for row in self.connection.execute("SELECT * FROM cumulative_costs ORDER BY provider")]
