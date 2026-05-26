"""
Меню модулей и обработка их включения/выключения.

Модуль «Таймер» имеет собственные шаги настройки (формат, базовое имя)
и обрабатывается в этом же файле — других модулей пока нет.
"""

from __future__ import annotations

import datetime as dt
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import emojis as em
import keyboards as kb
from database import DB
from handlers.common import (
    answer_callback,
    is_premium_user,
    premium_required_text,
    safe_edit,
)
from modules import all_modules, get as get_module
from states import TimerStates
from userbot import UserbotManager

logger = logging.getLogger(__name__)

router = Router(name="modules")


# ── список модулей ──────────────────────────────────────────────────────────


@router.callback_query(F.data == "modules:list")
async def cb_modules_list(cb: CallbackQuery, db: DB) -> None:
    user = cb.from_user
    if not is_premium_user(user.id, user.is_premium):
        await safe_edit(cb.message, premium_required_text(), reply_markup=kb.back_to_main())
        await cb.answer()
        return

    enabled_keys: set[str] = set()
    for mod in all_modules():
        state = await db.get_module(user.id, mod["key"])
        if state and state.get("enabled"):
            enabled_keys.add(mod["key"])

    text = (
        f"<b>{em.APPS} Доступные модули</b>\n\n"
        f"{em.INFO} Включите нужные модули. Для работы требуется "
        f"подключённый аккаунт."
    )
    await safe_edit(
        cb.message,
        text,
        reply_markup=kb.modules_list(all_modules(), enabled_keys),
    )
    await cb.answer()


# ── открытие карточки модуля ───────────────────────────────────────────────


@router.callback_query(F.data.startswith("modules:open:"))
async def cb_module_open(cb: CallbackQuery, db: DB) -> None:
    key = cb.data.split(":", 2)[2]
    mod = get_module(key)
    if not mod:
        await cb.answer("Модуль не найден", show_alert=True)
        return

    user = cb.from_user
    if mod.meta.premium_only and not is_premium_user(user.id, user.is_premium):
        await safe_edit(cb.message, premium_required_text(), reply_markup=kb.back_to_main())
        await cb.answer()
        return

    db_user = await db.get_user(user.id) or {}
    has_session = bool(db_user.get("has_session"))
    state = await db.get_module(user.id, key)
    enabled = bool(state and state.get("enabled"))
    cfg = (state or {}).get("config", {}) if state else {}

    text = _module_text(mod.meta.title, mod.meta.description, has_session, enabled, cfg)
    await safe_edit(
        cb.message,
        text,
        reply_markup=kb.module_card(key, enabled, has_session),
    )
    await cb.answer()


def _module_text(title: str, desc: str, has_session: bool, enabled: bool, cfg: dict) -> str:
    status = (
        f"{em.CHECK} <b>Включён</b>"
        if enabled
        else f"{em.CROSS} <b>Выключен</b>"
    )
    lines = [
        f"<b>{em.CLOCK} Модуль «{title}»</b>",
        "",
        desc,
        "",
        status,
    ]
    if cfg.get("format"):
        lines.append(f"{em.FONT} Формат времени: <code>{cfg['format']}</code>")
    if cfg.get("base_name"):
        lines.append(f"{em.ADD_TEXT} Базовый ник: <code>{cfg['base_name']}</code>")
    if not has_session:
        lines.append("")
        lines.append(
            f"{em.LOCK_CLOSED} Подключите аккаунт, чтобы пользоваться модулем."
        )
    return "\n".join(lines)


# ── включение/выключение ───────────────────────────────────────────────────


@router.callback_query(F.data.startswith("modules:enable:"))
async def cb_enable(
    cb: CallbackQuery,
    state: FSMContext,
    db: DB,
    userbot: UserbotManager,
) -> None:
    key = cb.data.split(":", 2)[2]
    mod = get_module(key)
    if not mod:
        await cb.answer("Модуль не найден", show_alert=True)
        return

    user = cb.from_user
    if mod.meta.premium_only and not is_premium_user(user.id, user.is_premium):
        await safe_edit(cb.message, premium_required_text(), reply_markup=kb.back_to_main())
        await cb.answer()
        return

    session = await db.get_session(user.id)
    if mod.meta.requires_session and not session:
        await cb.answer("Сначала подключите аккаунт", show_alert=True)
        return

    # Особый сценарий для Таймера: настройка перед включением
    if key == "timer":
        existing = await db.get_module(user.id, key)
        cfg = (existing or {}).get("config", {}) if existing else {}
        if not cfg.get("format") or not cfg.get("base_name"):
            await _start_timer_setup(cb, state, db)
            return

    await db.set_module_state(user.id, key, True, (await db.get_module(user.id, key) or {}).get("config", {}))
    try:
        await mod.start(
            user_id=user.id,
            session_string=session or "",
            config=(await db.get_module(user.id, key) or {}).get("config", {}),
            db=db,
            userbot=userbot,
        )
    except Exception as exc:
        logger.exception("module start failed: %s", exc)
        await db.set_module_state(user.id, key, False)
        await cb.answer(f"Не удалось запустить: {type(exc).__name__}", show_alert=True)
        return

    await cb_module_open(cb, db)
    await answer_callback(cb, "Модуль включён")


@router.callback_query(F.data.startswith("modules:disable:"))
async def cb_disable(
    cb: CallbackQuery,
    db: DB,
    userbot: UserbotManager,
) -> None:
    key = cb.data.split(":", 2)[2]
    mod = get_module(key)
    if not mod:
        await cb.answer("Модуль не найден", show_alert=True)
        return

    state = await db.get_module(cb.from_user.id, key)
    cfg = (state or {}).get("config", {}) if state else {}
    await db.set_module_state(cb.from_user.id, key, False, cfg)
    try:
        await mod.stop(cb.from_user.id, db=db, userbot=userbot)
    except Exception as exc:
        logger.warning("module stop failed: %s", exc)
    await cb_module_open(cb, db)
    await answer_callback(cb, "Модуль выключен")


# ── настройка ──────────────────────────────────────────────────────────────


@router.callback_query(F.data.startswith("modules:configure:"))
async def cb_configure(cb: CallbackQuery, db: DB) -> None:
    key = cb.data.split(":", 2)[2]
    if key != "timer":
        await cb.answer("Нечего настраивать", show_alert=True)
        return

    state = await db.get_module(cb.from_user.id, key)
    enabled = bool(state and state.get("enabled"))
    cfg = (state or {}).get("config", {}) if state else {}

    text = (
        f"<b>{em.SETTINGS} Настройки модуля «Таймер»</b>\n\n"
        f"{em.FONT} Текущий формат: "
        f"<code>{cfg.get('format', '—')}</code>\n"
        f"{em.ADD_TEXT} Базовый ник: "
        f"<code>{cfg.get('base_name', '—')}</code>\n\n"
        f"{em.INFO} В имя будет подставляться <b>базовый ник + время</b>. "
        f"Пример: <code>{cfg.get('base_name') or 'Имя'} "
        f"{dt.datetime.now().strftime(cfg.get('format') or '%H:%M')}</code>"
    )
    await safe_edit(cb.message, text, reply_markup=kb.timer_settings(enabled))
    await cb.answer()


# ── Timer setup: формат ────────────────────────────────────────────────────


async def _start_timer_setup(cb: CallbackQuery, state: FSMContext, db: DB) -> None:
    await state.set_state(TimerStates.format)
    text = (
        f"<b>{em.CLOCK} Шаг 1 из 2 — выберите формат</b>\n\n"
        f"{em.INFO} Это шаблон по правилам Python (<code>strftime</code>):\n"
        f"  • <code>%H</code> — часы (24)\n"
        f"  • <code>%M</code> — минуты\n"
        f"  • <code>%S</code> — секунды\n"
        f"  • <code>%d</code>, <code>%m</code> — день, месяц\n"
        f"  • <code>%a</code> — короткое название дня"
    )
    await safe_edit(cb.message, text, reply_markup=kb.timer_format_presets())
    await cb.answer()


@router.callback_query(F.data == "timer:setfmt")
async def cb_set_format(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(TimerStates.format)
    await safe_edit(
        cb.message,
        (
            f"<b>{em.FONT} Выберите формат времени</b>\n\n"
            f"Или отправьте свой шаблон (Python <code>strftime</code>)."
        ),
        reply_markup=kb.timer_format_presets(),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("timer:fmt:"))
async def cb_fmt_preset(
    cb: CallbackQuery,
    state: FSMContext,
    db: DB,
    userbot: UserbotManager,
) -> None:
    raw = cb.data.split(":", 2)[2]
    if raw == "custom":
        await safe_edit(
            cb.message,
            (
                f"<b>{em.PENCIL} Свой формат</b>\n\n"
                f"Отправьте шаблон <code>strftime</code>, например: "
                f"<code>%H:%M:%S</code>"
            ),
            reply_markup=kb.timer_format_presets(),
        )
        await cb.answer()
        return

    if not _is_valid_format(raw):
        await cb.answer("Неверный формат", show_alert=True)
        return

    cfg = await db.update_module_config(cb.from_user.id, "timer", {"format": raw})
    if not cfg.get("base_name"):
        await _ask_base_name(cb, state)
        return

    await _finalize_timer(cb, db, userbot)


@router.message(TimerStates.format, F.text)
async def msg_custom_format(
    message: Message,
    state: FSMContext,
    db: DB,
    userbot: UserbotManager,
) -> None:
    raw = (message.text or "").strip()
    if not _is_valid_format(raw):
        await message.answer(
            f"{em.CROSS} Неверный формат. Пример: <code>%H:%M</code>",
            parse_mode="HTML",
        )
        return
    cfg = await db.update_module_config(message.from_user.id, "timer", {"format": raw})

    if not cfg.get("base_name"):
        await state.set_state(TimerStates.base_name)
        base = await db.get_base_name(message.from_user.id)
        await message.answer(
            _base_name_prompt(base),
            reply_markup=kb.back_to_main(),
            parse_mode="HTML",
        )
        return

    await state.clear()
    await message.answer(
        f"{em.CHECK} Формат сохранён.",
        reply_markup=kb.back_to_main(),
        parse_mode="HTML",
    )


def _is_valid_format(fmt: str) -> bool:
    if not fmt or len(fmt) > 64:
        return False
    try:
        dt.datetime.now().strftime(fmt)
        return True
    except Exception:
        return False


# ── Timer setup: базовый ник ───────────────────────────────────────────────


@router.callback_query(F.data == "timer:setbase")
async def cb_set_base(cb: CallbackQuery, state: FSMContext, db: DB) -> None:
    await _ask_base_name(cb, state)


async def _ask_base_name(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(TimerStates.base_name)
    await safe_edit(
        cb.message,
        _base_name_prompt(None),
        reply_markup=kb.back_to_main(),
    )
    await cb.answer()


def _base_name_prompt(default: str | None) -> str:
    extra = (
        f"\n\n{em.INFO} По умолчанию возьмём ваш текущий ник: <code>{default}</code>. "
        f"Отправьте <code>-</code>, чтобы оставить его."
        if default
        else ""
    )
    return (
        f"<b>{em.ADD_TEXT} Шаг 2 из 2 — базовый ник</b>\n\n"
        f"Что должно стоять перед временем? Пример: <code>Kilka</code> → "
        f"<code>Kilka 14:32</code>.{extra}"
    )


@router.message(TimerStates.base_name, F.text)
async def msg_base_name(
    message: Message,
    state: FSMContext,
    db: DB,
    userbot: UserbotManager,
) -> None:
    raw = (message.text or "").strip()
    if raw == "-":
        raw = await db.get_base_name(message.from_user.id) or ""
    if not raw:
        await message.answer(
            f"{em.CROSS} Пустой ник недопустим.",
            parse_mode="HTML",
        )
        return
    if len(raw) > 40:
        await message.answer(
            f"{em.CROSS} Длина базового ника не больше 40 символов.",
            parse_mode="HTML",
        )
        return

    await db.set_base_name(message.from_user.id, raw)
    await db.update_module_config(message.from_user.id, "timer", {"base_name": raw})
    await state.clear()

    # Запускаем модуль
    await _finalize_timer_message(message, db, userbot)


# ── финал: запуск таймера ──────────────────────────────────────────────────


async def _finalize_timer(cb: CallbackQuery, db: DB, userbot: UserbotManager) -> None:
    user_id = cb.from_user.id
    session = await db.get_session(user_id)
    if not session:
        await cb.answer("Аккаунт не подключён", show_alert=True)
        return

    cfg = (await db.get_module(user_id, "timer") or {}).get("config", {})
    if not cfg.get("format") or not cfg.get("base_name"):
        await cb.answer("Сначала заполните настройки", show_alert=True)
        return

    await db.set_module_state(user_id, "timer", True, cfg)
    mod = get_module("timer")
    if mod:
        await mod.start(user_id, session, cfg, db, userbot)

    text = (
        f"<b>{em.CHECK} Таймер запущен</b>\n\n"
        f"{em.FONT} Формат: <code>{cfg['format']}</code>\n"
        f"{em.ADD_TEXT} Базовый ник: <code>{cfg['base_name']}</code>\n\n"
        f"{em.INFO} Бот будет обновлять ваш ник примерно раз в минуту."
    )
    await safe_edit(cb.message, text, reply_markup=kb.timer_settings(True))
    await cb.answer("Запущено")


async def _finalize_timer_message(
    message: Message, db: DB, userbot: UserbotManager
) -> None:
    user_id = message.from_user.id
    session = await db.get_session(user_id)
    if not session:
        await message.answer(
            f"{em.CROSS} Сначала подключите аккаунт.",
            reply_markup=kb.back_to_main(),
            parse_mode="HTML",
        )
        return

    cfg = (await db.get_module(user_id, "timer") or {}).get("config", {})
    if not cfg.get("format") or not cfg.get("base_name"):
        await message.answer(
            f"{em.CROSS} Не все настройки заданы.",
            reply_markup=kb.back_to_main(),
            parse_mode="HTML",
        )
        return

    await db.set_module_state(user_id, "timer", True, cfg)
    mod = get_module("timer")
    if mod:
        await mod.start(user_id, session, cfg, db, userbot)

    text = (
        f"<b>{em.CHECK} Таймер запущен</b>\n\n"
        f"{em.FONT} Формат: <code>{cfg['format']}</code>\n"
        f"{em.ADD_TEXT} Базовый ник: <code>{cfg['base_name']}</code>\n\n"
        f"{em.INFO} Бот будет обновлять ваш ник примерно раз в минуту."
    )
    await message.answer(text, reply_markup=kb.timer_settings(True), parse_mode="HTML")
