"""Staff database (SQLite) on the Jetson: employees, encrypted face samples, event log.

Face data never leaves this machine (D-12, NFR-09): embeddings are encrypted at rest (Fernet) and
no method here returns them to the PROTO-3 layer; `list_staff` only exposes counts. No raw images
are stored.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet

SCHEMA = """
CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    allowed INTEGER NOT NULL DEFAULT 1,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS face_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    embedding BLOB NOT NULL,
    quality REAL NOT NULL,
    yaw REAL NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at REAL NOT NULL,
    kind TEXT NOT NULL,
    employee_id INTEGER,
    detail TEXT NOT NULL DEFAULT ''
);
"""
MAX_TEXT = 200


class StoreError(ValueError):
    """A staff operation was refused; the message is safe to show on the web."""


def load_key(key: str, key_path: Path) -> bytes:
    """The Fernet key from the environment, else from a key file created (0600) on first use."""
    if key:
        return key.encode()
    if key_path.exists():
        return key_path.read_bytes().strip()
    key_path.parent.mkdir(parents=True, exist_ok=True)
    data = Fernet.generate_key()
    fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
    return data


def _text(value: Any, field: str, required: bool = False) -> str:
    if not isinstance(value, str):
        if required or value is not None:
            raise StoreError(f"{field} must be text")
        return ""
    value = value.strip()
    if (required and not value) or len(value) > MAX_TEXT:
        raise StoreError(f"{field} is empty or too long")
    return value


class Store:
    def __init__(self, db_path: Path | str, key: bytes) -> None:
        if str(db_path) != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(db_path))
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.executescript(SCHEMA)
        self._fernet = Fernet(key)

    def close(self) -> None:
        self._db.close()

    # ---- events ----

    def log_event(self, kind: str, employee_id: int | None = None, detail: str = "") -> None:
        self._db.execute(
            "INSERT INTO events (at, kind, employee_id, detail) VALUES (?, ?, ?, ?)",
            (time.time(), kind, employee_id, detail[:MAX_TEXT]),
        )
        self._db.commit()

    def events(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._db.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    # ---- employees ----

    def list_staff(self) -> list[dict[str, Any]]:
        """Display fields only: sample count and last enrolment, never embeddings."""
        rows = self._db.execute(
            """SELECT e.id, e.code, e.name, e.note, e.allowed, e.created_at, e.updated_at,
                      COUNT(f.id) AS samples, MAX(f.created_at) AS last_enrolled
               FROM employees e LEFT JOIN face_samples f ON f.employee_id = e.id
               GROUP BY e.id ORDER BY e.code"""
        ).fetchall()
        return [{**dict(r), "allowed": bool(r["allowed"])} for r in rows]

    def get(self, employee_id: Any) -> dict[str, Any]:
        for row in self.list_staff():
            if row["id"] == employee_id and not isinstance(employee_id, bool):
                return row
        raise StoreError("employee not found")

    def create(self, code: Any, name: Any, note: Any = "", allowed: Any = True) -> int:
        code, name, note = _text(code, "code", True), _text(name, "name", True), _text(note, "note")
        if not isinstance(allowed, bool):
            raise StoreError("allowed must be true or false")
        now = time.time()
        try:
            cur = self._db.execute(
                "INSERT INTO employees (code, name, note, allowed, created_at, updated_at) VALUES (?,?,?,?,?,?)",
                (code, name, note, int(allowed), now, now),
            )
        except sqlite3.IntegrityError as exc:
            raise StoreError("code already exists") from exc
        self._db.commit()
        self.log_event("staff_create", cur.lastrowid, code)
        return int(cur.lastrowid)

    def update(self, employee_id: Any, **fields: Any) -> dict[str, Any]:
        """Returns the employee as before the change, so the caller can see what was revoked."""
        before = self.get(employee_id)
        sets: dict[str, Any] = {}
        if fields.get("code") is not None:
            sets["code"] = _text(fields["code"], "code", True)
        if fields.get("name") is not None:
            sets["name"] = _text(fields["name"], "name", True)
        if fields.get("note") is not None:
            sets["note"] = _text(fields["note"], "note")
        if fields.get("allowed") is not None:
            if not isinstance(fields["allowed"], bool):
                raise StoreError("allowed must be true or false")
            sets["allowed"] = int(fields["allowed"])
        if sets:
            cols = ", ".join(f"{k} = ?" for k in sets)
            try:
                self._db.execute(
                    f"UPDATE employees SET {cols}, updated_at = ? WHERE id = ?",
                    (*sets.values(), time.time(), employee_id),
                )
            except sqlite3.IntegrityError as exc:
                raise StoreError("code already exists") from exc
            self._db.commit()
            self.log_event("staff_update", employee_id, ",".join(sets))
        return before

    def delete(self, employee_id: Any) -> None:
        self.get(employee_id)
        self._db.execute("DELETE FROM employees WHERE id = ?", (employee_id,))  # samples cascade
        self._db.commit()
        self.log_event("staff_delete", employee_id)

    # ---- face samples (encrypted) ----

    def add_samples(
        self, employee_id: int, samples: list[tuple[list[float], float, float]], replace: bool = False
    ) -> None:
        """samples: (embedding, quality, yaw_deg). Replaces the old samples atomically if asked."""
        self.get(employee_id)
        now = time.time()
        with self._db:
            if replace:
                self._db.execute("DELETE FROM face_samples WHERE employee_id = ?", (employee_id,))
            for embedding, quality, yaw in samples:
                blob = self._fernet.encrypt(json.dumps(embedding).encode())
                self._db.execute(
                    "INSERT INTO face_samples (employee_id, embedding, quality, yaw, created_at) VALUES (?,?,?,?,?)",
                    (employee_id, blob, quality, yaw, now),
                )
        self.log_event("faces_enrolled", employee_id, f"{len(samples)} samples")

    def clear_samples(self, employee_id: Any) -> None:
        self.get(employee_id)
        self._db.execute("DELETE FROM face_samples WHERE employee_id = ?", (employee_id,))
        self._db.commit()
        self.log_event("faces_clear", employee_id)

    def gallery(self) -> dict[int, list[list[float]]]:
        """Decrypted embeddings of allowed employees, for the matcher on this machine only."""
        rows = self._db.execute(
            "SELECT f.employee_id, f.embedding FROM face_samples f "
            "JOIN employees e ON e.id = f.employee_id WHERE e.allowed = 1"
        ).fetchall()
        out: dict[int, list[list[float]]] = {}
        for r in rows:
            out.setdefault(r["employee_id"], []).append(json.loads(self._fernet.decrypt(r["embedding"])))
        return out
