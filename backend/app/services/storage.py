"""SQLite persistence: saved trips, chat sessions and messages."""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Storage:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self._init()

    @contextmanager
    def _conn(self):
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        finally:
            c.close()

    def _init(self) -> None:
        with self._conn() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.executescript("""
            CREATE TABLE IF NOT EXISTS trips(id TEXT PRIMARY KEY, name TEXT NOT NULL, destination_id TEXT, created_at TEXT, updated_at TEXT, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, state TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, payload TEXT, created_at TEXT);
            CREATE INDEX IF NOT EXISTS idx_msg_session ON messages(session_id);
            """)

    # ---- trips
    def save_trip(self, name: str, plan: dict, trip_id: str | None = None, versions: list | None = None) -> dict:
        payload = json.dumps(dict(plan=plan, versions=versions or []))
        now = _now()
        with self._conn() as c:
            if trip_id:
                cur = c.execute("UPDATE trips SET name=?, destination_id=?, updated_at=?, payload=? WHERE id=?", (name, plan.get("destination_id"), now, payload, trip_id))
                if cur.rowcount:
                    return self.get_trip(trip_id)  # type: ignore[return-value]
            tid = trip_id or uuid.uuid4().hex[:12]
            c.execute("INSERT INTO trips(id,name,destination_id,created_at,updated_at,payload) VALUES(?,?,?,?,?,?)", (tid, name, plan.get("destination_id"), now, now, payload))
        return self.get_trip(tid)  # type: ignore[return-value]

    def get_trip(self, tid: str) -> dict | None:
        with self._conn() as c:
            r = c.execute("SELECT * FROM trips WHERE id=?", (tid,)).fetchone()
        if not r:
            return None
        d = json.loads(r["payload"])
        return dict(id=r["id"], name=r["name"], destination_id=r["destination_id"], created_at=r["created_at"], updated_at=r["updated_at"], plan=d["plan"], versions=d.get("versions", []))

    def list_trips(self) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT id,name,destination_id,created_at,updated_at,payload FROM trips ORDER BY updated_at DESC").fetchall()
        out = []
        for r in rows:
            plan = json.loads(r["payload"])["plan"]
            cs = plan.get("costs", {})
            out.append(dict(id=r["id"], name=r["name"], destination_id=r["destination_id"], destination_name=plan.get("destination_name"), created_at=r["created_at"],
                            updated_at=r["updated_at"], days=len(plan.get("days", [])), total=cs.get("total"), travellers=cs.get("travellers")))
        return out

    def delete_trip(self, tid: str) -> bool:
        with self._conn() as c:
            return c.execute("DELETE FROM trips WHERE id=?", (tid,)).rowcount > 0

    # ---- chat sessions
    def load_session(self, sid: str) -> dict | None:
        with self._conn() as c:
            r = c.execute("SELECT state FROM sessions WHERE id=?", (sid,)).fetchone()
        return json.loads(r["state"]) if r else None

    def save_session(self, sid: str, state: dict) -> None:
        now = _now()
        with self._conn() as c:
            c.execute("INSERT INTO sessions(id,created_at,updated_at,state) VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET updated_at=excluded.updated_at, state=excluded.state",
                      (sid, now, now, json.dumps(state)))

    def add_message(self, sid: str, role: str, content: str, payload: dict | None = None) -> None:
        with self._conn() as c:
            c.execute("INSERT INTO messages(session_id,role,content,payload,created_at) VALUES(?,?,?,?,?)", (sid, role, content, json.dumps(payload) if payload else None, _now()))

    def messages(self, sid: str, limit: int = 200) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT role,content,payload,created_at FROM messages WHERE session_id=? ORDER BY id LIMIT ?", (sid, limit)).fetchall()
        return [dict(role=r["role"], content=r["content"], payload=json.loads(r["payload"]) if r["payload"] else None, created_at=r["created_at"]) for r in rows]

    def session_summaries(self, ids: list[str]) -> list[dict]:
        """Title (first user message), message count and last-activity time for the given sessions only."""
        out = []
        with self._conn() as c:
            for sid in ids[:50]:
                s = c.execute("SELECT updated_at FROM sessions WHERE id=?", (sid,)).fetchone()
                if not s:
                    continue
                first = c.execute("SELECT content FROM messages WHERE session_id=? AND role='user' ORDER BY id LIMIT 1", (sid,)).fetchone()
                n = c.execute("SELECT COUNT(*) AS n FROM messages WHERE session_id=?", (sid,)).fetchone()["n"]
                out.append(dict(id=sid, title=(first["content"][:60] if first else "New conversation"), messages=n, updated_at=s["updated_at"]))
        return sorted(out, key=lambda x: x["updated_at"], reverse=True)

    def delete_session(self, sid: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM sessions WHERE id=?", (sid,)); c.execute("DELETE FROM messages WHERE session_id=?", (sid,))
