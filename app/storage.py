from __future__ import annotations

import threading
import time
import re
import json
import os
import sqlite3
import uuid
from pathlib import Path

from .graphrag import GraphContextStore
from .schemas import Event, Participant, Room, validate_protocol_payload


class MemoryStore:
    """Thread-safe prototype store with event sequence and idempotency support."""

    def __init__(self):
        self.rooms = {}
        self.events: dict[str, list[Event]] = {}
        self.participants: dict[str, list[Participant]] = {}
        self._idempotency: dict[tuple[str, str], Event] = {}
        self._lock = threading.RLock()
        self.graph = GraphContextStore(lock=self._lock)

    def create_room(self, topic="", mode="learning", task_id="daofu"):
        if mode not in {"learning", "production"}:
            raise ValueError("mode_invalid")
        if not isinstance(topic, str) or len(topic) > 500:
            raise ValueError("topic_invalid")
        if not isinstance(task_id, str) or not task_id or len(task_id) > 128:
            raise ValueError("task_id_invalid")
        with self._lock:
            r = Room(topic=topic, mode=mode, task_id=task_id, created_at=time.time())
            self.rooms[r.id] = r
            self.events[r.id] = []
            self.participants[r.id] = []
            self.graph.index_room(r.id, r.topic, r.task_id)
            return r

    def get_room(self, room_id):
        with self._lock:
            return self.rooms.get(room_id)

    def join_room(self, room_id, seat_id, display_name="学习者", kind="human"):
        with self._lock:
            if room_id not in self.rooms:
                raise KeyError(room_id)
            if isinstance(seat_id, bool) or not isinstance(seat_id, int) or not 0 <= seat_id < 7:
                raise ValueError("seat_invalid")
            if not isinstance(display_name, str) or not display_name.strip() or len(display_name) > 80:
                raise ValueError("display_name_invalid")
            if kind not in {"human", "agent"}:
                raise ValueError("participant_kind_invalid")
            if any(item.seat_id == seat_id for item in self.participants[room_id]):
                raise ValueError("seat_occupied")
            participant = Participant(room_id, seat_id, display_name or "学习者", kind, joined_at=time.time())
            self.participants[room_id].append(participant)
            return participant

    def room_state(self, room_id):
        with self._lock:
            if room_id not in self.rooms:
                raise KeyError(room_id)
            return {
                "room": self.rooms[room_id].to_dict(),
                "participants": [item.to_dict() for item in self.participants[room_id]],
                "last_seq": len(self.events[room_id]),
            }

    def add_event(self, room_id, type, payload=None, *, actor_id=None, stage=None, visibility="room", idempotency_key=None, event_id=None):
        with self._lock:
            if room_id not in self.rooms:
                raise KeyError(room_id)
            if not isinstance(type, str) or not re.fullmatch(r"[a-zA-Z0-9_.-]{1,80}", type):
                raise ValueError("event_type_invalid")
            if payload is not None and not isinstance(payload, dict):
                raise ValueError("payload_invalid")
            payload = validate_protocol_payload(type, payload or {})
            if visibility not in {"room", "seat", "private", "research"}:
                raise ValueError("visibility_invalid")
            if idempotency_key is not None and (not isinstance(idempotency_key, str) or len(idempotency_key) > 160):
                raise ValueError("idempotency_key_invalid")
            if idempotency_key:
                previous = self._idempotency.get((room_id, idempotency_key))
                if previous:
                    return previous
            stream = self.events[room_id]
            event = Event(
                room_id=room_id,
                type=type,
                payload=payload or {},
                id=event_id or uuid.uuid4().hex,
                seq=len(stream) + 1,
                actor_id=actor_id,
                stage=stage,
                visibility=visibility,
                idempotency_key=idempotency_key,
                created_at=time.time(),
            )
            stream.append(event)
            if idempotency_key:
                self._idempotency[(room_id, idempotency_key)] = event
            self.graph.ingest_event(event.to_dict())
            return event

    def list_events(self, room_id, after_seq=0):
        with self._lock:
            if room_id not in self.rooms:
                raise KeyError(room_id)
            return [event for event in self.events[room_id] if event.seq > after_seq]


class SQLiteStore:
    """SQLite-backed room/event store with WAL and the MemoryStore API.

    The store deliberately keeps the same method signatures as ``MemoryStore``
    so the protocol and HTTP layer can migrate without changing event shapes.
    SQLite is appropriate for the local course/demo deployment; a service with
    several application processes can later replace this class with a shared
    database adapter.
    """

    def __init__(self, path: str | os.PathLike[str] | None = None):
        default_path = Path(__file__).resolve().parents[1] / "data" / "huitong.sqlite3"
        self.path = str(path or os.getenv("HUITONG_DB_PATH", default_path))
        if self.path != ":memory:":
            Path(self.path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._configure()
        self._init_schema()
        self.graph = GraphContextStore(self._conn, self._lock)
        if self.path != ":memory:":
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass

    def _configure(self) -> None:
        with self._lock:
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.execute("PRAGMA synchronous = NORMAL")
            self._conn.execute("PRAGMA journal_mode = WAL")

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS rooms (
                    id TEXT PRIMARY KEY,
                    topic TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    protocol_version TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS participants (
                    id TEXT PRIMARY KEY,
                    room_id TEXT NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
                    seat_id INTEGER NOT NULL,
                    display_name TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    joined_at REAL NOT NULL,
                    UNIQUE(room_id, seat_id)
                );
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    room_id TEXT NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
                    seq INTEGER NOT NULL,
                    type TEXT NOT NULL,
                    actor_id TEXT,
                    stage TEXT,
                    visibility TEXT NOT NULL,
                    idempotency_key TEXT,
                    payload_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    UNIQUE(room_id, seq),
                    UNIQUE(room_id, idempotency_key)
                );
                CREATE INDEX IF NOT EXISTS idx_events_room_seq ON events(room_id, seq);
                CREATE INDEX IF NOT EXISTS idx_participants_room ON participants(room_id);
                """
            )

    @staticmethod
    def _room(row: sqlite3.Row | None) -> Room | None:
        if row is None:
            return None
        return Room(
            id=row["id"], topic=row["topic"], mode=row["mode"], task_id=row["task_id"],
            protocol_version=row["protocol_version"], status=row["status"], created_at=row["created_at"],
        )

    @staticmethod
    def _participant(row: sqlite3.Row) -> Participant:
        return Participant(
            room_id=row["room_id"], seat_id=row["seat_id"], display_name=row["display_name"],
            kind=row["kind"], id=row["id"], joined_at=row["joined_at"],
        )

    @staticmethod
    def _event(row: sqlite3.Row) -> Event:
        try:
            payload = json.loads(row["payload_json"])
        except (TypeError, ValueError):
            payload = {}
        return Event(
            room_id=row["room_id"], type=row["type"], payload=payload,
            id=row["id"], seq=row["seq"], actor_id=row["actor_id"], stage=row["stage"],
            visibility=row["visibility"], idempotency_key=row["idempotency_key"], created_at=row["created_at"],
        )

    @property
    def rooms(self) -> dict[str, Room]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM rooms ORDER BY created_at").fetchall()
            return {row["id"]: self._room(row) for row in rows}

    def create_room(self, topic="", mode="learning", task_id="daofu"):
        if mode not in {"learning", "production"}:
            raise ValueError("mode_invalid")
        if not isinstance(topic, str) or len(topic) > 500:
            raise ValueError("topic_invalid")
        if not isinstance(task_id, str) or not task_id or len(task_id) > 128:
            raise ValueError("task_id_invalid")
        room = Room(topic=topic, mode=mode, task_id=task_id, created_at=time.time())
        with self._lock:
            self._conn.execute(
                "INSERT INTO rooms(id, topic, mode, task_id, protocol_version, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (room.id, room.topic, room.mode, room.task_id, room.protocol_version, room.status, room.created_at),
            )
            self.graph.index_room(room.id, room.topic, room.task_id)
        return room

    def get_room(self, room_id):
        with self._lock:
            row = self._conn.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
            return self._room(row)

    def join_room(self, room_id, seat_id, display_name="学习者", kind="human"):
        if isinstance(seat_id, bool) or not isinstance(seat_id, int) or not 0 <= seat_id < 7:
            raise ValueError("seat_invalid")
        if not isinstance(display_name, str) or not display_name.strip() or len(display_name) > 80:
            raise ValueError("display_name_invalid")
        if kind not in {"human", "agent"}:
            raise ValueError("participant_kind_invalid")
        participant = Participant(room_id, seat_id, display_name.strip(), kind, joined_at=time.time())
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                if self._conn.execute("SELECT 1 FROM rooms WHERE id = ?", (room_id,)).fetchone() is None:
                    raise KeyError(room_id)
                if self._conn.execute("SELECT 1 FROM participants WHERE room_id = ? AND seat_id = ?", (room_id, seat_id)).fetchone():
                    raise ValueError("seat_occupied")
                self._conn.execute(
                    "INSERT INTO participants(id, room_id, seat_id, display_name, kind, joined_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (participant.id, participant.room_id, participant.seat_id, participant.display_name, participant.kind, participant.joined_at),
                )
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise
        return participant

    def room_state(self, room_id):
        with self._lock:
            room = self._conn.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
            if room is None:
                raise KeyError(room_id)
            participants = self._conn.execute(
                "SELECT * FROM participants WHERE room_id = ? ORDER BY seat_id", (room_id,)
            ).fetchall()
            last = self._conn.execute("SELECT COALESCE(MAX(seq), 0) AS n FROM events WHERE room_id = ?", (room_id,)).fetchone()["n"]
            return {
                "room": self._room(room).to_dict(),
                "participants": [self._participant(row).to_dict() for row in participants],
                "last_seq": int(last or 0),
            }

    def add_event(self, room_id, type, payload=None, *, actor_id=None, stage=None, visibility="room", idempotency_key=None, event_id=None):
        if not isinstance(type, str) or not re.fullmatch(r"[a-zA-Z0-9_.-]{1,80}", type):
            raise ValueError("event_type_invalid")
        if payload is not None and not isinstance(payload, dict):
            raise ValueError("payload_invalid")
        payload = validate_protocol_payload(type, payload or {})
        if visibility not in {"room", "seat", "private", "research"}:
            raise ValueError("visibility_invalid")
        if idempotency_key is not None and (not isinstance(idempotency_key, str) or len(idempotency_key) > 160):
            raise ValueError("idempotency_key_invalid")
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                if self._conn.execute("SELECT 1 FROM rooms WHERE id = ?", (room_id,)).fetchone() is None:
                    raise KeyError(room_id)
                if idempotency_key:
                    previous = self._conn.execute(
                        "SELECT * FROM events WHERE room_id = ? AND idempotency_key = ?", (room_id, idempotency_key)
                    ).fetchone()
                    if previous is not None:
                        self._conn.execute("COMMIT")
                        return self._event(previous)
                seq = int(self._conn.execute("SELECT COALESCE(MAX(seq), 0) + 1 AS n FROM events WHERE room_id = ?", (room_id,)).fetchone()["n"])
                event = Event(
                    room_id=room_id, type=type, payload=payload or {}, id=event_id or uuid.uuid4().hex, seq=seq,
                    actor_id=actor_id, stage=stage, visibility=visibility,
                    idempotency_key=idempotency_key, created_at=time.time(),
                )
                self._conn.execute(
                    "INSERT INTO events(id, room_id, seq, type, actor_id, stage, visibility, idempotency_key, payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (event.id, event.room_id, event.seq, event.type, event.actor_id, event.stage, event.visibility,
                     event.idempotency_key, json.dumps(event.payload, ensure_ascii=False), event.created_at),
                )
                self.graph.ingest_event(event.to_dict())
                self._conn.execute("COMMIT")
                return event
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def list_events(self, room_id, after_seq=0):
        with self._lock:
            if self._conn.execute("SELECT 1 FROM rooms WHERE id = ?", (room_id,)).fetchone() is None:
                raise KeyError(room_id)
            rows = self._conn.execute(
                "SELECT * FROM events WHERE room_id = ? AND seq > ? ORDER BY seq", (room_id, int(after_seq))
            ).fetchall()
            return [self._event(row) for row in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __del__(self):
        try:
            self._conn.close()
        except Exception:
            pass
