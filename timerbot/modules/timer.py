"""
Модуль «Таймер».

Записывает текущее время в first_name пользователя в выбранном формате.
Работает поверх Pyrogram-сессии Premium-аккаунта.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import Module, ModuleMeta, register

if TYPE_CHECKING:
    from database import DB
    from userbot import UserbotManager


class TimerModule(Module):
    meta = ModuleMeta(
        key="timer",
        title="Таймер",
        description=(
            "Подставляет текущее время в имя профиля. "
            "Выберите формат — бот будет периодически обновлять ваш ник."
        ),
        requires_session=True,
        premium_only=True,
    )

    async def start(
        self,
        user_id: int,
        session_string: str,
        config: dict,
        db: "DB",
        userbot: "UserbotManager",
    ) -> None:
        base_name = config.get("base_name") or await db.get_base_name(user_id) or ""
        time_format = config.get("format") or "%H:%M"
        interval = int(config.get("interval", 60))
        tz_offset = int(config.get("tz_offset_min", 0))

        async def _on_error(uid: int, exc: Exception) -> None:
            # При фатальной ошибке выключаем модуль, чтобы не спамить логи
            await db.set_module_state(uid, self.meta.key, False, config)

        await userbot.start_timer(
            user_id=user_id,
            session_string=session_string,
            base_name=base_name,
            time_format=time_format,
            interval=interval,
            timezone_offset_minutes=tz_offset,
            on_error=_on_error,
        )

    async def stop(
        self,
        user_id: int,
        db: "DB",
        userbot: "UserbotManager",
    ) -> None:
        await userbot.stop_timer(user_id)
        # Возвращаем базовый ник (без времени)
        session = await db.get_session(user_id)
        base_name = await db.get_base_name(user_id)
        if session and base_name:
            try:
                await userbot.set_first_name(session, base_name)
            except Exception:
                pass


register(TimerModule())
