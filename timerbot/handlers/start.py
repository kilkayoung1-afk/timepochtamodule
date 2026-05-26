"""
/start, главное меню, профиль, информация.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import emojis as em
import keyboards as kb
from database import DB
from handlers.common import is_admin, is_premium_user, safe_edit

router = Router(name="start")


def _greeting(user_name: str, is_premium: bool) -> str:
    status = (
        f"{em.CHECK} <b>Premium активен</b>"
        if is_premium
        else f"{em.LOCK_CLOSED} <b>Premium не подключён</b>"
    )
    return (
        f"<b>{em.BOT} Pochta Modules</b>\n\n"
        f"{em.SMILE} Привет, <b>{user_name}</b>!\n"
        f"{status}\n\n"
        f"{em.APPS} Это бот с подключаемыми модулями.\n"
        f"{em.CLOCK} Первый модуль — <b>Таймер</b>: вставляет текущее "
        f"время в имя вашего профиля.\n\n"
        f"{em.INFO} Нажмите <b>Модули</b>, чтобы посмотреть список."
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, db: DB) -> None:
    await state.clear()
    user = message.from_user
    if not user:
        return

    is_prem = is_premium_user(user.id, user.is_premium)
    await db.upsert_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        is_premium=is_prem,
    )

    await message.answer(
        _greeting(user.first_name or "друг", is_prem),
        reply_markup=kb.main_menu(is_admin=is_admin(user.id)),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "user:menu")
async def cb_main_menu(cb: CallbackQuery, state: FSMContext, db: DB) -> None:
    await state.clear()
    user = cb.from_user
    is_prem = is_premium_user(user.id, user.is_premium)
    await db.upsert_user(user.id, user.username, user.first_name, is_prem)

    await safe_edit(
        cb.message,
        _greeting(user.first_name or "друг", is_prem),
        reply_markup=kb.main_menu(is_admin=is_admin(user.id)),
    )
    await cb.answer()


@router.callback_query(F.data == "user:profile")
async def cb_profile(cb: CallbackQuery, db: DB) -> None:
    user = cb.from_user
    db_user = await db.get_user(user.id) or {}
    is_prem = is_premium_user(user.id, user.is_premium)

    text = (
        f"<b>{em.PROFILE} Профиль</b>\n\n"
        f"{em.TAG} <b>Имя:</b> {user.full_name}\n"
        f"{em.LINK} <b>Username:</b> "
        + (f"@{user.username}" if user.username else "<i>—</i>")
        + "\n"
        f"{em.CODE} <b>ID:</b> <code>{user.id}</code>\n"
        f"{em.GIFT} <b>Premium:</b> "
        + ("активен" if is_prem else "не подключён")
        + "\n"
        f"{em.LOCK_OPEN} <b>Аккаунт подключён:</b> "
        + ("да" if db_user.get("has_session") else "нет")
    )
    await safe_edit(cb.message, text, reply_markup=kb.back_to_main())
    await cb.answer()


@router.callback_query(F.data == "user:info")
async def cb_info(cb: CallbackQuery) -> None:
    text = (
        f"<b>{em.INFO} Pochta Modules</b>\n\n"
        f"{em.APPS} Бот с модульной архитектурой. Модули — это автономные "
        f"плагины, которые работают поверх вашего Telegram-аккаунта.\n\n"
        f"{em.LOCK_OPEN} <b>Как подключить:</b>\n"
        f"  1. Оформите Telegram&nbsp;Premium\n"
        f"  2. В разделе <b>Аккаунт</b> авторизуйтесь по номеру телефона\n"
        f"  3. Откройте <b>Модули</b> и включите нужные\n\n"
        f"{em.CLOCK} <b>Доступные модули:</b>\n"
        f"  • <b>Таймер</b> — время в имени профиля\n\n"
        f"{em.BOT} Связь с разработчиком: @Kilka_Young"
    )
    await safe_edit(cb.message, text, reply_markup=kb.back_to_main())
    await cb.answer()
