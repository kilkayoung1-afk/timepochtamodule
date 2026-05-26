"""
Админ-панель: статистика, рассылка, выдача/снятие Premium-флага.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import config
import emojis as em
import keyboards as kb
from database import DB
from handlers.common import (
    answer_callback,
    is_admin,
    safe_edit,
)
from states import AdminStates
from userbot import UserbotManager

logger = logging.getLogger(__name__)

router = Router(name="admin")


def _admin_guard(user_id: int) -> bool:
    return is_admin(user_id)


@router.callback_query(F.data == "admin:menu")
async def cb_menu(cb: CallbackQuery, state: FSMContext) -> None:
    if not _admin_guard(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await state.clear()

    text = (
        f"<b>{em.SETTINGS} Админ-панель</b>\n\n"
        f"{em.INFO} Управление пользователями и рассылками."
    )
    await safe_edit(cb.message, text, reply_markup=kb.admin_menu())
    await cb.answer()


@router.callback_query(F.data == "admin:stats")
async def cb_stats(cb: CallbackQuery, db: DB, userbot: UserbotManager) -> None:
    if not _admin_guard(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return

    total = await db.count_users()
    premium = await db.count_premium()
    enabled_timers = await db.all_enabled_for_module("timer")
    text = (
        f"<b>{em.STATS} Статистика</b>\n\n"
        f"{em.PEOPLE} Всего пользователей: <b>{total}</b>\n"
        f"{em.GIFT} Premium: <b>{premium}</b>\n"
        f"{em.CLOCK} Активных таймеров: <b>{len(enabled_timers)}</b>"
    )
    await safe_edit(cb.message, text, reply_markup=kb.back_to_admin())
    await cb.answer()


@router.callback_query(F.data == "admin:users")
async def cb_users(cb: CallbackQuery, db: DB) -> None:
    if not _admin_guard(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return

    users = await db.all_users()
    lines = [f"<b>{em.PEOPLE} Пользователи ({len(users)})</b>", ""]
    for u in users[:50]:
        flag = em.CHECK if u.get("is_premium") else em.CROSS
        sess = em.LOCK_OPEN if u.get("has_session") else em.LOCK_CLOSED
        uname = f"@{u['username']}" if u.get("username") else "<i>—</i>"
        lines.append(
            f"{flag} {sess} <code>{u['user_id']}</code> · {uname}"
        )
    if len(users) > 50:
        lines.append(f"\n{em.INFO} И ещё {len(users) - 50}…")
    await safe_edit(cb.message, "\n".join(lines), reply_markup=kb.back_to_admin())
    await cb.answer()


@router.callback_query(F.data == "admin:timers")
async def cb_active_timers(cb: CallbackQuery, db: DB, userbot: UserbotManager) -> None:
    if not _admin_guard(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return

    rows = await db.all_enabled_for_module("timer")
    lines = [f"<b>{em.TIME_PASSED} Активные таймеры ({len(rows)})</b>", ""]
    for r in rows[:50]:
        uid = r["user_id"]
        live = "•" if userbot.has_timer(uid) else "—"
        fmt = (r.get("config") or {}).get("format", "")
        lines.append(f"{live} <code>{uid}</code> · <code>{fmt}</code>")
    await safe_edit(cb.message, "\n".join(lines), reply_markup=kb.back_to_admin())
    await cb.answer()


# ── рассылка ────────────────────────────────────────────────────────────────


@router.callback_query(F.data == "admin:broadcast")
async def cb_broadcast(cb: CallbackQuery, state: FSMContext) -> None:
    if not _admin_guard(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return

    await state.set_state(AdminStates.broadcast)
    text = (
        f"<b>{em.MEGAPHONE} Рассылка</b>\n\n"
        f"Отправьте сообщение — оно уйдёт всем пользователям бота. "
        f"Поддерживается HTML."
    )
    await safe_edit(cb.message, text, reply_markup=kb.broadcast_keyboard())
    await cb.answer()


@router.message(AdminStates.broadcast, F.text)
async def msg_broadcast(message: Message, state: FSMContext, db: DB) -> None:
    if not _admin_guard(message.from_user.id):
        return

    text = message.html_text or message.text or ""
    users = await db.all_users()
    await state.clear()

    sent = 0
    failed = 0
    notice = await message.answer(
        f"{em.LOADING} Рассылка запущена ({len(users)})…",
        parse_mode="HTML",
    )

    for u in users:
        try:
            await message.bot.send_message(u["user_id"], text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    try:
        await notice.edit_text(
            f"<b>{em.CHECK} Рассылка завершена</b>\n\n"
            f"{em.PARTY} Доставлено: <b>{sent}</b>\n"
            f"{em.CROSS} Ошибок: <b>{failed}</b>",
            reply_markup=kb.back_to_admin(),
            parse_mode="HTML",
        )
    except Exception:
        await message.answer(f"Доставлено: {sent}, ошибок: {failed}")


# ── ручной premium ─────────────────────────────────────────────────────────


@router.callback_query(F.data == "admin:grant")
async def cb_grant(cb: CallbackQuery, state: FSMContext) -> None:
    if not _admin_guard(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(AdminStates.grant_premium)
    await safe_edit(
        cb.message,
        f"<b>{em.GIFT} Выдать Premium</b>\n\nОтправьте ID пользователя.",
        reply_markup=kb.broadcast_keyboard(),
    )
    await cb.answer()


@router.callback_query(F.data == "admin:revoke")
async def cb_revoke(cb: CallbackQuery, state: FSMContext) -> None:
    if not _admin_guard(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(AdminStates.revoke_premium)
    await safe_edit(
        cb.message,
        f"<b>{em.TRASH} Снять Premium</b>\n\nОтправьте ID пользователя.",
        reply_markup=kb.broadcast_keyboard(),
    )
    await cb.answer()


@router.message(AdminStates.grant_premium, F.text)
async def msg_grant(message: Message, state: FSMContext) -> None:
    if not _admin_guard(message.from_user.id):
        return
    raw = (message.text or "").strip()
    if not raw.lstrip("-").isdigit():
        await message.answer(f"{em.CROSS} Ожидаю числовой ID.", parse_mode="HTML")
        return
    config.MANUAL_PREMIUM_IDS.add(int(raw))
    await state.clear()
    await message.answer(
        f"{em.CHECK} ID <code>{raw}</code> добавлен в ручной Premium.",
        reply_markup=kb.back_to_admin(),
        parse_mode="HTML",
    )


@router.message(AdminStates.revoke_premium, F.text)
async def msg_revoke(message: Message, state: FSMContext) -> None:
    if not _admin_guard(message.from_user.id):
        return
    raw = (message.text or "").strip()
    if not raw.lstrip("-").isdigit():
        await message.answer(f"{em.CROSS} Ожидаю числовой ID.", parse_mode="HTML")
        return
    config.MANUAL_PREMIUM_IDS.discard(int(raw))
    await state.clear()
    await message.answer(
        f"{em.CHECK} ID <code>{raw}</code> удалён из ручного Premium.",
        reply_markup=kb.back_to_admin(),
        parse_mode="HTML",
    )
