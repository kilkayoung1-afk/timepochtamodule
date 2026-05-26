"""
Менеджер Pyrogram-клиентов: логин по номеру и фоновые задачи модулей.

Бот через Bot API не умеет менять ник пользователя — нужна юзер-сессия.
Поэтому каждый Premium-пользователь подключает свой Telegram-аккаунт
через Pyrogram (телефон → код → 2FA), а бот сохраняет session_string.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

from pyrogram import Client
from pyrogram.errors import (
    BadRequest,
    PhoneCodeExpired,
    PhoneCodeInvalid,
    SessionPasswordNeeded,
)

logger = logging.getLogger(__name__)


@dataclass
class PendingLogin:
    client: Client
    phone: str
    phone_code_hash: str


class UserbotManager:
    """Управляет Pyrogram-сессиями всех пользователей бота."""

    def __init__(self, api_id: int, api_hash: str) -> None:
        self.api_id = api_id
        self.api_hash = api_hash

        self._pending: dict[int, PendingLogin] = {}
        self._timer_tasks: dict[int, asyncio.Task] = {}

    # ── Login flow ────────────────────────────────────────────────────────

    def is_configured(self) -> bool:
        return bool(self.api_id) and bool(self.api_hash)

    async def send_code(self, user_id: int, phone: str) -> str:
        """Шлёт код подтверждения, возвращает phone_code_hash."""
        await self.cancel_pending(user_id)

        client = Client(
            name=f"login_{user_id}",
            api_id=self.api_id,
            api_hash=self.api_hash,
            in_memory=True,
        )
        await client.connect()
        try:
            sent = await client.send_code(phone)
        except Exception:
            await client.disconnect()
            raise

        self._pending[user_id] = PendingLogin(
            client=client, phone=phone, phone_code_hash=sent.phone_code_hash
        )
        return sent.phone_code_hash

    async def confirm_code(self, user_id: int, code: str) -> tuple[str, Optional[str]]:
        """
        Подтверждает код. Возвращает (status, session_string|None).

        status:
          - "ok"          — авторизовано, есть session_string
          - "2fa"         — требуется пароль (вызовите confirm_password)
          - "invalid"     — неверный код
          - "expired"     — код просрочен
        """
        pending = self._pending.get(user_id)
        if not pending:
            return "invalid", None

        try:
            await pending.client.sign_in(
                pending.phone, pending.phone_code_hash, code
            )
        except PhoneCodeInvalid:
            return "invalid", None
        except PhoneCodeExpired:
            await self.cancel_pending(user_id)
            return "expired", None
        except SessionPasswordNeeded:
            return "2fa", None
        except BadRequest as exc:
            logger.warning("sign_in BadRequest for %s: %s", user_id, exc)
            return "invalid", None

        session_string = await pending.client.export_session_string()
        await self._finalize_login(user_id)
        return "ok", session_string

    async def confirm_password(self, user_id: int, password: str) -> tuple[str, Optional[str]]:
        pending = self._pending.get(user_id)
        if not pending:
            return "invalid", None

        try:
            await pending.client.check_password(password)
        except BadRequest as exc:
            logger.warning("check_password BadRequest for %s: %s", user_id, exc)
            return "invalid", None

        session_string = await pending.client.export_session_string()
        await self._finalize_login(user_id)
        return "ok", session_string

    async def cancel_pending(self, user_id: int) -> None:
        pending = self._pending.pop(user_id, None)
        if not pending:
            return
        try:
            await pending.client.disconnect()
        except Exception:
            pass

    async def _finalize_login(self, user_id: int) -> None:
        pending = self._pending.pop(user_id, None)
        if not pending:
            return
        try:
            await pending.client.disconnect()
        except Exception:
            pass

    # ── Profile actions ──────────────────────────────────────────────────

    async def get_me_info(self, session_string: str) -> dict:
        """Возвращает {id, first_name, last_name, username, is_premium}."""
        client = Client(
            name="probe",
            api_id=self.api_id,
            api_hash=self.api_hash,
            session_string=session_string,
            in_memory=True,
        )
        await client.start()
        try:
            me = await client.get_me()
            return {
                "id": me.id,
                "first_name": me.first_name or "",
                "last_name": me.last_name or "",
                "username": me.username or "",
                "is_premium": bool(getattr(me, "is_premium", False)),
            }
        finally:
            await client.stop()

    async def set_first_name(self, session_string: str, first_name: str) -> None:
        client = Client(
            name="setname",
            api_id=self.api_id,
            api_hash=self.api_hash,
            session_string=session_string,
            in_memory=True,
        )
        await client.start()
        try:
            await client.update_profile(first_name=first_name[:64])
        finally:
            await client.stop()

    # ── Timer module — background loop per user ─────────────────────────

    async def start_timer(
        self,
        user_id: int,
        session_string: str,
        base_name: str,
        time_format: str,
        interval: int = 60,
        timezone_offset_minutes: int = 0,
        on_error=None,
    ) -> None:
        """Запускает (или перезапускает) бесконечный цикл обновления ника."""
        await self.stop_timer(user_id)

        task = asyncio.create_task(
            self._timer_loop(
                user_id=user_id,
                session_string=session_string,
                base_name=base_name,
                time_format=time_format,
                interval=interval,
                tz_offset_min=timezone_offset_minutes,
                on_error=on_error,
            ),
            name=f"timer-{user_id}",
        )
        self._timer_tasks[user_id] = task

    async def stop_timer(self, user_id: int) -> None:
        task = self._timer_tasks.pop(user_id, None)
        if not task:
            return
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass

    def has_timer(self, user_id: int) -> bool:
        task = self._timer_tasks.get(user_id)
        return bool(task and not task.done())

    async def _timer_loop(
        self,
        user_id: int,
        session_string: str,
        base_name: str,
        time_format: str,
        interval: int,
        tz_offset_min: int,
        on_error,
    ) -> None:
        from datetime import datetime, timedelta, timezone

        tz = timezone(timedelta(minutes=tz_offset_min))
        client = Client(
            name=f"timer_{user_id}",
            api_id=self.api_id,
            api_hash=self.api_hash,
            session_string=session_string,
            in_memory=True,
        )

        try:
            await client.start()
        except Exception as exc:
            logger.exception("Timer start failed for %s: %s", user_id, exc)
            if on_error:
                try:
                    await on_error(user_id, exc)
                except Exception:
                    pass
            return

        try:
            while True:
                now = datetime.now(tz).strftime(time_format)
                name = f"{base_name} {now}".strip()
                try:
                    await client.update_profile(first_name=name[:64])
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.warning("update_profile failed for %s: %s", user_id, exc)
                    if on_error:
                        try:
                            await on_error(user_id, exc)
                        except Exception:
                            pass
                await asyncio.sleep(max(15, interval))
        except asyncio.CancelledError:
            pass
        finally:
            try:
                await client.stop()
            except Exception:
                pass

    async def shutdown(self) -> None:
        for uid in list(self._timer_tasks.keys()):
            await self.stop_timer(uid)
        for uid in list(self._pending.keys()):
            await self.cancel_pending(uid)
