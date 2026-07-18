from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import DATA_DIR
from .models import CheckIn, Profile


class AssistantStore:
    def __init__(self, path: Path | None = None):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.path = path or DATA_DIR / "assistant.db"
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.migrate()

    def migrate(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                data TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS checkins (
                day TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS plans (
                day TEXT PRIMARY KEY,
                draft_json TEXT NOT NULL,
                enhanced_json TEXT NOT NULL,
                provider TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    def get_profile(self) -> Profile | None:
        row = self.conn.execute("SELECT data FROM profiles WHERE id=1").fetchone()
        return Profile.from_dict(json.loads(row["data"])) if row else None

    def save_profile(self, profile: Profile) -> None:
        now = _now()
        self.conn.execute(
            "INSERT INTO profiles (id,data,updated_at) VALUES (1,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at",
            (json.dumps(profile.to_dict(), ensure_ascii=False), now),
        )
        self.conn.commit()

    def get_checkin(self, day: str) -> CheckIn | None:
        row = self.conn.execute("SELECT data FROM checkins WHERE day=?", (day,)).fetchone()
        return CheckIn.from_dict(json.loads(row["data"])) if row else None

    def latest_checkin_before(self, day: str) -> CheckIn | None:
        row = self.conn.execute("SELECT data FROM checkins WHERE day < ? ORDER BY day DESC LIMIT 1", (day,)).fetchone()
        return CheckIn.from_dict(json.loads(row["data"])) if row else None

    def save_checkin(self, checkin: CheckIn) -> None:
        now = _now()
        existing = self.conn.execute("SELECT created_at FROM checkins WHERE day=?", (checkin.day,)).fetchone()
        created_at = existing["created_at"] if existing else now
        self.conn.execute(
            """
            INSERT INTO checkins (day,data,created_at,updated_at)
            VALUES (?,?,?,?)
            ON CONFLICT(day) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at
            """,
            (checkin.day, json.dumps(checkin.to_dict(), ensure_ascii=False), created_at, now),
        )
        self.conn.commit()

    def checkins(self, limit: int = 30) -> list[CheckIn]:
        rows = self.conn.execute("SELECT data FROM checkins ORDER BY day DESC LIMIT ?", (limit,)).fetchall()
        return [CheckIn.from_dict(json.loads(row["data"])) for row in rows]

    def save_plan(self, day: str, draft: dict[str, Any], enhanced: dict[str, Any], provider: str) -> None:
        self.conn.execute(
            """
            INSERT INTO plans (day,draft_json,enhanced_json,provider,created_at)
            VALUES (?,?,?,?,?)
            ON CONFLICT(day) DO UPDATE SET draft_json=excluded.draft_json, enhanced_json=excluded.enhanced_json, provider=excluded.provider, created_at=excluded.created_at
            """,
            (
                day,
                json.dumps(draft, ensure_ascii=False),
                json.dumps(enhanced, ensure_ascii=False),
                provider,
                _now(),
            ),
        )
        self.conn.commit()

    def export_backup(self) -> dict[str, Any]:
        profile = self.get_profile()
        return {
            "version": 1,
            "exported_at": _now(),
            "profile": profile.to_dict() if profile else None,
            "checkins": [item.to_dict() for item in reversed(self.checkins(365))],
            "plans": [dict(row) for row in self.conn.execute("SELECT * FROM plans ORDER BY day").fetchall()],
        }

    def import_backup(self, payload: dict[str, Any]) -> None:
        profile = Profile.from_dict(payload.get("profile"))
        if profile:
            self.save_profile(profile)
        for item in payload.get("checkins", []):
            checkin = CheckIn.from_dict(item)
            if checkin:
                self.save_checkin(checkin)
        for row in payload.get("plans", []):
            if {"day", "draft_json", "enhanced_json", "provider"} <= set(row):
                self.conn.execute(
                    """
                    INSERT INTO plans (day,draft_json,enhanced_json,provider,created_at)
                    VALUES (?,?,?,?,?)
                    ON CONFLICT(day) DO UPDATE SET draft_json=excluded.draft_json, enhanced_json=excluded.enhanced_json, provider=excluded.provider
                    """,
                    (row["day"], row["draft_json"], row["enhanced_json"], row["provider"], row.get("created_at", _now())),
                )
        self.conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

