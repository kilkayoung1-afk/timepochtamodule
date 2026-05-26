"""
Общие зависимости и хелперы хэндлеров.
"""

from __future__ import annotations

from aiogram import Bot
from aiogram.types import CallbackQuery, Message

import config
import emojis as em


def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


def is_premium_user(user_id: int, is_premium_field: bool | None) -> bool:
    """Premium = Telegram Premium ИЛИ выдан вручную админом."""
    if user_id in config.MANUAL_PREMIUM_IDS:
        return True
    return bool(is_premium_field)


async def safe_edit(
    message: Message | None,
    text: str,
    reply_markup=None,
    parse_mode: str = "HTML",
) -> None:
    """Безопасная редактура сообщения (ловит «message is not modified»)."""
    if not message:
        return
    try:
        await message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception:
        try:
            await message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception:
            pass


async def answer_callback(cb: CallbackQuery, text: str = "", alert: bool = False) -> None:
    try:
        await cb.answer(text=text, show_alert=alert)
    except Exception:
        pass


def premium_required_text() -> str:
    return (
        f"<b>{em.LOCK_CLOSED} Доступ только для Premium</b>\n\n"
        "Модули бота работают только на аккаунтах с активной подпиской "
        "Telegram&nbsp;Premium. Оформите Premium в Telegram и вернитесь сюда."
    )
