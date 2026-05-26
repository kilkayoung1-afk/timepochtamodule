"""
Подключение Pyrogram-сессии Premium-пользователя.

Сценарий:
  1. Нажимает «Подключить аккаунт»
  2. Бот просит номер телефона
  3. Telegram присылает код в официальный клиент → пользователь шлёт код боту
  4. При включённой 2FA — бот просит облачный пароль
  5. Бот сохраняет session_string в БД
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

import emojis as em
import keyboards as kb
from database import DB
from handlers.common import (
    answer_callback,
    is_premium_user,
    premium_required_text,
    safe_edit,
)
from states import ConnectStates
from userbot import UserbotManager

logger = logging.getLogger(__name__)

router = Router(name="connect")


@router.callback_query(F.data == "user:account")
async def cb_account_root(cb: CallbackQuery, db: DB, userbot: UserbotManager) -> None:
    user = cb.from_user
    is_prem = is_premium_user(user.id, user.is_premium)

    if not is_prem:
        await safe_edit(
            cb.message,
            premium_required_text(),
            reply_markup=kb.back_to_main(),
        )
        await cb.answer()
        return

    if not userbot.is_configured():
        await safe_edit(
            cb.message,
            (
                f"<b>{em.CROSS} Бот не сконфигурирован</b>\n\n"
                f"Администратор не задал <code>API_ID</code> и "
                f"<code>API_HASH</code>. Без них подключение аккаунта "
                f"невозможно.\n\n"
                f"{em.LINK} Получить ключи: https://my.telegram.org/apps"
            ),
            reply_markup=kb.back_to_main(),
        )
        await cb.answer()
        return

    db_user = await db.get_user(user.id) or {}
    connected = bool(db_user.get("has_session"))

    text = (
        f"<b>{em.LOCK_OPEN} Подключение аккаунта</b>\n\n"
        + (
            f"{em.CHECK} Ваш Telegram-аккаунт подключён."
            if connected
            else (
                f"{em.EYE_HIDDEN} Для работы модулей боту нужна авторизация "
                f"на вашем Telegram-аккаунте.\n"
                f"{em.WRITE} Авторизация выполняется по номеру телефона и "
                f"одноразовому коду — как при входе в новый клиент Telegram.\n\n"
                f"{em.LOCK_CLOSED} Сессия хранится в зашифрованном виде и "
                f"используется только модулями, которые вы включаете сами."
            )
        )
    )
    await safe_edit(cb.message, text, reply_markup=kb.account_root(connected))
    await cb.answer()


# ── start login ─────────────────────────────────────────────────────────────


@router.callback_query(F.data == "connect:start")
async def cb_connect_start(
    cb: CallbackQuery, state: FSMContext, userbot: UserbotManager
) -> None:
    if not userbot.is_configured():
        await cb.answer("API_ID/API_HASH не заданы", show_alert=True)
        return

    await state.set_state(ConnectStates.phone)
    await safe_edit(
        cb.message,
        (
            f"<b>{em.WRITE} Введите номер телефона</b>\n\n"
            f"Формат: <code>+71234567890</code>"
        ),
        reply_markup=kb.cancel_connect(),
    )
    await cb.answer()


@router.message(ConnectStates.phone, F.text)
async def msg_phone(
    message: Message, state: FSMContext, userbot: UserbotManager
) -> None:
    phone = (message.text or "").strip().replace(" ", "")
    if not phone.startswith("+") or len(phone) < 8:
        await message.answer(
            f"{em.CROSS} Неверный формат. Введите номер в виде "
            f"<code>+71234567890</code>",
            parse_mode="HTML",
        )
        return

    try:
        await userbot.send_code(message.from_user.id, phone)
    except Exception as exc:
        logger.warning("send_code failed: %s", exc)
        await state.clear()
        await message.answer(
            f"{em.CROSS} Не удалось отправить код: <code>{type(exc).__name__}</code>.\n"
            f"Попробуйте ещё раз.",
            reply_markup=kb.account_root(False),
            parse_mode="HTML",
        )
        return

    await state.update_data(phone=phone)
    await state.set_state(ConnectStates.code)
    await message.answer(
        (
            f"<b>{em.BELL} Код отправлен</b>\n\n"
            f"Откройте Telegram → официальный чат «Telegram» — там пришёл "
            f"код. Введите его сюда.\n\n"
            f"{em.INFO} Чтобы код не считался скомпрометированным, вводите "
            f"его с разделителем, например: <code>1 2 3 4 5</code>"
        ),
        reply_markup=kb.cancel_connect(),
        parse_mode="HTML",
    )


@router.message(ConnectStates.code, F.text)
async def msg_code(
    message: Message,
    state: FSMContext,
    db: DB,
    userbot: UserbotManager,
) -> None:
    code = "".join(ch for ch in (message.text or "") if ch.isdigit())
    if not code:
        await message.answer(
            f"{em.CROSS} Введите цифры кода.",
            parse_mode="HTML",
        )
        return

    status, session = await userbot.confirm_code(message.from_user.id, code)

    if status == "ok" and session:
        await db.save_session(message.from_user.id, session)
        await _store_base_name(db, userbot, message.from_user.id, session)
        await state.clear()
        await message.answer(
            f"<b>{em.CHECK} Аккаунт подключён</b>\n\n"
            f"{em.APPS} Откройте раздел <b>Модули</b> и включите нужные.",
            reply_markup=kb.back_to_main(),
            parse_mode="HTML",
        )
        return

    if status == "2fa":
        await state.set_state(ConnectStates.password)
        await message.answer(
            f"<b>{em.LOCK_CLOSED} Двухфакторная защита</b>\n\n"
            f"Введите облачный пароль (cloud password).",
            reply_markup=kb.cancel_connect(),
            parse_mode="HTML",
        )
        return

    if status == "expired":
        await state.clear()
        await message.answer(
            f"{em.CROSS} Код просрочен. Начните заново.",
            reply_markup=kb.account_root(False),
            parse_mode="HTML",
        )
        return

    await message.answer(
        f"{em.CROSS} Неверный код. Попробуйте снова.",
        parse_mode="HTML",
    )


@router.message(ConnectStates.password, F.text)
async def msg_password(
    message: Message,
    state: FSMContext,
    db: DB,
    userbot: UserbotManager,
) -> None:
    password = message.text or ""
    status, session = await userbot.confirm_password(message.from_user.id, password)

    if status == "ok" and session:
        await db.save_session(message.from_user.id, session)
        await _store_base_name(db, userbot, message.from_user.id, session)
        await state.clear()
        await message.answer(
            f"<b>{em.CHECK} Аккаунт подключён</b>",
            reply_markup=kb.back_to_main(),
            parse_mode="HTML",
        )
        return

    await message.answer(
        f"{em.CROSS} Неверный пароль. Попробуйте снова.",
        parse_mode="HTML",
    )


# ── контакт через reply-кнопку ──────────────────────────────────────────────


@router.message(ConnectStates.phone, F.contact)
async def msg_phone_contact(
    message: Message, state: FSMContext, userbot: UserbotManager
) -> None:
    if message.contact.user_id != message.from_user.id:
        await message.answer(
            f"{em.CROSS} Это контакт другого пользователя. Отправьте свой номер.",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML",
        )
        return

    phone = message.contact.phone_number
    if not phone.startswith("+"):
        phone = "+" + phone

    try:
        await userbot.send_code(message.from_user.id, phone)
    except Exception as exc:
        logger.warning("send_code failed: %s", exc)
        await state.clear()
        await message.answer(
            f"{em.CROSS} Не удалось отправить код: <code>{type(exc).__name__}</code>.",
            reply_markup=kb.account_root(False),
            parse_mode="HTML",
        )
        return

    await state.update_data(phone=phone)
    await state.set_state(ConnectStates.code)
    await message.answer(
        (
            f"<b>{em.BELL} Код отправлен</b>\n\n"
            f"Откройте Telegram → официальный чат «Telegram» — там пришёл "
            f"код. Введите его сюда с разделителями: <code>1 2 3 4 5</code>"
        ),
        reply_markup=kb.cancel_connect(),
        parse_mode="HTML",
    )


# ── отмена / отключение ────────────────────────────────────────────────────


@router.callback_query(F.data == "connect:cancel")
async def cb_cancel(
    cb: CallbackQuery, state: FSMContext, userbot: UserbotManager
) -> None:
    await userbot.cancel_pending(cb.from_user.id)
    await state.clear()
    await safe_edit(
        cb.message,
        f"{em.CROSS} Подключение отменено.",
        reply_markup=kb.account_root(False),
    )
    await cb.answer()


@router.callback_query(F.data == "connect:disconnect")
async def cb_disconnect(
    cb: CallbackQuery, db: DB, userbot: UserbotManager
) -> None:
    await userbot.stop_timer(cb.from_user.id)
    await db.drop_session(cb.from_user.id)
    await safe_edit(
        cb.message,
        f"<b>{em.CHECK} Аккаунт отключён</b>",
        reply_markup=kb.account_root(False),
    )
    await answer_callback(cb, "Сессия удалена")


# ── вспомогательное ────────────────────────────────────────────────────────


async def _store_base_name(
    db: DB, userbot: UserbotManager, user_id: int, session: str
) -> None:
    """Сохраняет исходный first_name пользователя — потом используется в Таймере."""
    try:
        me = await userbot.get_me_info(session)
        if me.get("first_name"):
            await db.set_base_name(user_id, me["first_name"])
    except Exception as exc:
        logger.warning("get_me_info failed: %s", exc)
