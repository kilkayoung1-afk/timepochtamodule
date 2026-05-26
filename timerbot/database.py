"""
Хранение пользователей, сессий и состояния модулей в SQLite.
"""

from __future__ import annotations

import json
import time
from typing import Any, Optional

import aiosqlite


CREATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id        INTEGER PRIMARY KEY,
    username       TEXT,
    first_name     TEXT,
    is_premium     INTEGER DEFAULT 0,
    has_session    INTEGER DEFAULT 0,
    session_string TEXT,
    base_name      TEXT,
    created_at     INTEGER DEFAULT (CAST(strftime('%s','now') AS INTEGER)),
    last_seen      INTEGER DEFAULT (CAST(strftime('%s','now') AS INTEGER))
);

CREATE TABLE IF NOT EXISTS user_modules (
    user_id INTEGER NOT NULL,
    module  TEXT    NOT NULL,
    enabled INTEGER DEFAULT 0,
    config  TEXT    DEFAULT '{}',
    PRIMARY KEY (user_id, module)
);
"""


class DB:
    """Лёгкий асинхронный SQLite-репозиторий."""

    def __init__(self, path: str) -> None:
        self.path = path

    async def init(self) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(CREATE_SCHEMA)
            await db.commit()

    # ── Users ─────────────────────────────────────────────────────────────

    async def upsert_user(
        self,
        user_id: int,
        username: Optional[str],
        first_name: Optional[str],
        is_premium: bool,
    ) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO users (user_id, username, first_name, is_premium, last_seen)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username   = excluded.username,
                    first_name = excluded.first_name,
                    is_premium = excluded.is_premium,
                    last_seen  = excluded.last_seen
                """,
                (user_id, username, first_name, int(is_premium), int(time.time())),
            )
            await db.commit()

    async def get_user(self, user_id: int) -> Optional[dict]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = await cur.fetchone()
            return dict(row) if row else None

    async def all_users(self) -> list[dict]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM users ORDER BY created_at DESC")
            return [dict(r) for r in await cur.fetchall()]

    async def count_users(self) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT COUNT(*) FROM users")
            row = await cur.fetchone()
            return int(row[0]) if row else 0

    async def count_premium(self) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT COUNT(*) FROM users WHERE is_premium = 1")
            row = await cur.fetchone()
            return int(row[0]) if row else 0

    # ── Pyrogram sessions ────────────────────────────────────────────────

    async def save_session(self, user_id: int, session_string: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE users SET session_string = ?, has_session = 1 WHERE user_id = ?",
                (session_string, user_id),
            )
            await db.commit()

    async def drop_session(self, user_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE users SET session_string = NULL, has_session = 0 WHERE user_id = ?",
                (user_id,),
            )
            await db.commit()

    async def get_session(self, user_id: int) -> Optional[str]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT session_string FROM users WHERE user_id = ?", (user_id,)
            )
            row = await cur.fetchone()
            return row[0] if row and row[0] else None

    async def set_base_name(self, user_id: int, base_name: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE users SET base_name = ? WHERE user_id = ?",
                (base_name, user_id),
            )
            await db.commit()

    async def get_base_name(self, user_id: int) -> Optional[str]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT base_name FROM users WHERE user_id = ?", (user_id,)
            )
            row = await cur.fetchone()
            return row[0] if row and row[0] else None

    # ── Modules ──────────────────────────────────────────────────────────

    async def set_module_state(
        self,
        user_id: int,
        module: str,
        enabled: bool,
        config: Optional[dict[str, Any]] = None,
    ) -> None:
        cfg_str = json.dumps(config or {}, ensure_ascii=False)
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO user_modules (user_id, module, enabled, config)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, module) DO UPDATE SET
                    enabled = excluded.enabled,
                    config  = excluded.config
                """,
                (user_id, module, int(enabled), cfg_str),
            )
            await db.commit()

    async def update_module_config(
        self, user_id: int, module: str, patch: dict[str, Any]
    ) -> dict[str, Any]:
        current = await self.get_module(user_id, module)
        cfg = (current or {}).get("config", {})
        cfg.update(patch)
        await self.set_module_state(
            user_id,
            module,
            (current or {}).get("enabled", False),
            cfg,
        )
        return cfg

    async def get_module(self, user_id: int, module: str) -> Optional[dict]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM user_modules WHERE user_id = ? AND module = ?",
                (user_id, module),
            )
            row = await cur.fetchone()
            if not row:
                return None
            d = dict(row)
            try:
                d["config"] = json.loads(d["config"] or "{}")
            except json.JSONDecodeError:
                d["config"] = {}
            d["enabled"] = bool(d["enabled"])
            return d

    async def all_enabled_for_module(self, module: str) -> list[dict]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM user_modules WHERE module = ? AND enabled = 1",
                (module,),
            )
            rows = await cur.fetchall()
        out: list[dict] = []
        for r in rows:
            d = dict(r)
            try:
                d["config"] = json.loads(d["config"] or "{}")
            except json.JSONDecodeError:
                d["config"] = {}
            d["enabled"] = bool(d["enabled"])
            out.append(d)
        return out
