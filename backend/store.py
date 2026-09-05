import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

GENESIS = "0" * 64


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def verify_entries(entries: list[dict], expected_head: str | None = None) -> dict:
    previous = GENESIS
    session_id = entries[0]["session_id"] if entries else None
    for index, entry in enumerate(entries, start=1):
        payload = {key: value for key, value in entry.items() if key != "hash"}
        if (
            entry.get("sequence") != index
            or entry.get("prev_hash") != previous
            or entry.get("session_id") != session_id
            or digest(payload) != entry.get("hash")
        ):
            return {"valid": False, "count": len(entries), "broken_at": index, "head": previous}
        previous = entry["hash"]
    valid = expected_head is None or expected_head == previous
    return {
        "valid": valid,
        "count": len(entries),
        "broken_at": None if valid else len(entries) + 1,
        "head": previous,
    }


CATALOG = [
    {
        "id": "arc-75",
        "name": "Arc 75 keyboard",
        "price": 349900,
        "category": "keyboards",
        "stock": 6,
        "tags": ["quiet", "wireless", "mechanical", "compact"],
        "description": "A quiet, compact mechanical board for focused work.",
    },
    {
        "id": "forma-75",
        "name": "Forma 75 keyboard",
        "price": 329900,
        "category": "keyboards",
        "stock": 12,
        "tags": ["quiet", "wireless", "mechanical", "compact"],
        "description": "Same quiet switches. A simpler aluminium finish.",
    },
    {
        "id": "felt-mat",
        "name": "Felt desk mat",
        "price": 89900,
        "category": "accessories",
        "stock": 24,
        "tags": ["desk", "felt", "bundle"],
        "description": "A soft landing for your everyday workspace.",
    },
    {
        "id": "studio-audio",
        "name": "Studio headphones",
        "price": 649900,
        "category": "audio",
        "stock": 4,
        "tags": ["audio", "wireless"],
        "description": "Over-ear listening for a quieter working day.",
    },
]


class Store:
    def __init__(self, path: str | Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, document TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS audit(session_id TEXT NOT NULL, sequence INTEGER NOT NULL,
                    entry TEXT NOT NULL, PRIMARY KEY(session_id, sequence));
                CREATE TABLE IF NOT EXISTS products(id TEXT PRIMARY KEY, document TEXT NOT NULL);
            """)
            for product in CATALOG:
                db.execute(
                    "INSERT OR IGNORE INTO products VALUES (?, ?)", (product["id"], canonical(product))
                )

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            db.execute("PRAGMA journal_mode=WAL")
            with db:
                yield db
        finally:
            db.close()

    def catalog(self):
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute("SELECT document FROM products ORDER BY rowid")]

    def save(self, session: dict):
        with self.connect() as db:
            db.execute(
                "INSERT INTO sessions VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET document=excluded.document",
                (session["id"], canonical(session)),
            )

    def get(self, session_id: str):
        with self.connect() as db:
            row = db.execute("SELECT document FROM sessions WHERE id=?", (session_id,)).fetchone()
        if not row:
            raise KeyError(session_id)
        return json.loads(row[0])

    def sessions(self):
        with self.connect() as db:
            return [
                json.loads(row[0])
                for row in db.execute("SELECT document FROM sessions ORDER BY rowid DESC LIMIT 100")
            ]

    def entries(self, session_id: str):
        with self.connect() as db:
            return [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT entry FROM audit WHERE session_id=? ORDER BY sequence", (session_id,)
                )
            ]

    def append(
        self,
        session: dict,
        actor: str,
        action: str,
        summary: str,
        evidence: dict | None = None,
        reserve_lines: list[dict] | None = None,
    ):
        # Inventory reservation, event and checkout checkpoint commit together or not at all.
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            reserved = []
            for line in reserve_lines or []:
                row = db.execute("SELECT document FROM products WHERE id=?", (line["id"],)).fetchone()
                if not row:
                    return None
                product = json.loads(row[0])
                if product["stock"] < 1:
                    return None
                product["stock"] -= 1
                reserved.append(product)
            for product in reserved:
                db.execute("UPDATE products SET document=? WHERE id=?", (canonical(product), product["id"]))
            last = db.execute(
                "SELECT sequence,entry FROM audit WHERE session_id=? ORDER BY sequence DESC LIMIT 1",
                (session["id"],),
            ).fetchone()
            entry = {
                "session_id": session["id"],
                "sequence": last[0] + 1 if last else 1,
                "timestamp": now(),
                "actor": actor,
                "action": action,
                "summary": summary,
                "evidence": evidence or {},
                "prev_hash": json.loads(last[1])["hash"] if last else GENESIS,
            }
            entry["hash"] = digest(entry)
            session["audit_head"] = entry["hash"]
            db.execute(
                "INSERT INTO audit VALUES (?, ?, ?)", (session["id"], entry["sequence"], canonical(entry))
            )
            db.execute("UPDATE sessions SET document=? WHERE id=?", (canonical(session), session["id"]))
        return entry
