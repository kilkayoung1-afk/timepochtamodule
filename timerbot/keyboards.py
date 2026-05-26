"""
Конструкторы клавиатур с премиум-эмодзи.

Премиум-эмодзи в кнопках указываются через icon_custom_emoji_id
(поле принимается aiogram 3.x благодаря model_config extra="allow").
В тексте кнопки не используем обычные эмодзи — это требование заказчика.
"""

from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from emojis import (
    ID_ADD_TEXT,
    ID_APPS,
    ID_BELL,
    ID_BOT,
    ID_CALENDAR,
    ID_CHECK,
    ID_CLOCK,
    ID_CODE,
    ID_CROSS,
    ID_DOWN,
    ID_FONT,
    ID_GIFT,
    ID_INFO,
    ID_LINK,
    ID_LOADING,
    ID_LOCK_CLOSED,
    ID_LOCK_OPEN,
    ID_MEGAPHONE,
    ID_PEOPLE,
    ID_PENCIL,
    ID_PROFILE,
    ID_SEND,
    ID_SETTINGS,
    ID_STATS,
    ID_TIME_PASSED,
    ID_TRASH,
    ID_WRITE,
)


def _btn(text: str, *, custom_emoji_id: str | None = None, **kwargs) -> InlineKeyboardButton:
    """InlineKeyboardButton + icon_custom_emoji_id (aiogram extra='allow')."""
    if custom_emoji_id:
        kwargs["icon_custom_emoji_id"] = custom_emoji_id
    return InlineKeyboardButton(text=text, **kwargs)


# ─── Главное меню ───────────────────────────────────────────────────────────

def main_menu(is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            _btn(
                "Модули",
                callback_data="modules:list",
                custom_emoji_id=ID_APPS,
            )
        ],
        [
            _btn(
                "Профиль",
                callback_data="user:profile",
                custom_emoji_id=ID_PROFILE,
            ),
            _btn(
                "Аккаунт",
                callback_data="user:account",
                custom_emoji_id=ID_LOCK_OPEN,
            ),
        ],
        [
            _btn(
                "Информация",
                callback_data="user:info",
                custom_emoji_id=ID_INFO,
            ),
        ],
    ]
    if is_admin:
        rows.append(
            [
                _btn(
                    "Админ-панель",
                    callback_data="admin:menu",
                    custom_emoji_id=ID_SETTINGS,
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("Назад", callback_data="user:menu", custom_emoji_id=ID_DOWN)]
        ]
    )


# ─── Модули ─────────────────────────────────────────────────────────────────

def modules_list(modules: list[dict], enabled_keys: set[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for mod in modules:
        key = mod["key"]
        title = mod["title"]
        if key in enabled_keys:
            label = f"{title} • вкл"
            cem = ID_CHECK
        else:
            label = title
            cem = ID_BOT
        rows.append(
            [
                _btn(
                    label,
                    callback_data=f"modules:open:{key}",
                    custom_emoji_id=cem,
                )
            ]
        )
    rows.append(
        [_btn("Назад", callback_data="user:menu", custom_emoji_id=ID_DOWN)]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def module_card(key: str, enabled: bool, has_session: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    if not has_session:
        rows.append(
            [
                _btn(
                    "Подключить аккаунт",
                    callback_data="user:account",
                    custom_emoji_id=ID_LOCK_OPEN,
                )
            ]
        )
    else:
        if enabled:
            rows.append(
                [
                    _btn(
                        "Выключить",
                        callback_data=f"modules:disable:{key}",
                        custom_emoji_id=ID_CROSS,
                    )
                ]
            )
        else:
            rows.append(
                [
                    _btn(
                        "Включить",
                        callback_data=f"modules:enable:{key}",
                        custom_emoji_id=ID_CHECK,
                    )
                ]
            )
        rows.append(
            [
                _btn(
                    "Настроить",
                    callback_data=f"modules:configure:{key}",
                    custom_emoji_id=ID_SETTINGS,
                ),
            ]
        )

    rows.append(
        [_btn("Назад", callback_data="modules:list", custom_emoji_id=ID_DOWN)]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─── Таймер: пресеты формата ────────────────────────────────────────────────

TIMER_FORMAT_PRESETS = [
    ("%H:%M",                "HH:MM"),
    ("%H:%M:%S",             "HH:MM:SS"),
    ("%d.%m %H:%M",          "DD.MM HH:MM"),
    ("%a %H:%M",             "ПН 13:45"),
]


def timer_format_presets() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for fmt, label in TIMER_FORMAT_PRESETS:
        rows.append(
            [
                _btn(
                    label,
                    callback_data=f"timer:fmt:{fmt}",
                    custom_emoji_id=ID_CLOCK,
                )
            ]
        )
    rows.append(
        [
            _btn(
                "Свой формат",
                callback_data="timer:fmt:custom",
                custom_emoji_id=ID_PENCIL,
            )
        ]
    )
    rows.append(
        [_btn("Отмена", callback_data="modules:open:timer", custom_emoji_id=ID_DOWN)]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def timer_settings(enabled: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            _btn(
                "Сменить формат",
                callback_data="timer:setfmt",
                custom_emoji_id=ID_FONT,
            )
        ],
        [
            _btn(
                "Изменить базовый ник",
                callback_data="timer:setbase",
                custom_emoji_id=ID_ADD_TEXT,
            )
        ],
    ]
    if enabled:
        rows.append(
            [
                _btn(
                    "Остановить таймер",
                    callback_data="modules:disable:timer",
                    custom_emoji_id=ID_CROSS,
                )
            ]
        )
    else:
        rows.append(
            [
                _btn(
                    "Запустить таймер",
                    callback_data="modules:enable:timer",
                    custom_emoji_id=ID_CHECK,
                )
            ]
        )
    rows.append(
        [_btn("Назад", callback_data="modules:open:timer", custom_emoji_id=ID_DOWN)]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─── Подключение аккаунта ──────────────────────────────────────────────────

def account_root(connected: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if connected:
        rows.append(
            [
                _btn(
                    "Отключить аккаунт",
                    callback_data="connect:disconnect",
                    custom_emoji_id=ID_LOCK_CLOSED,
                )
            ]
        )
        rows.append(
            [
                _btn(
                    "Переподключить",
                    callback_data="connect:start",
                    custom_emoji_id=ID_LOADING,
                )
            ]
        )
    else:
        rows.append(
            [
                _btn(
                    "Подключить аккаунт",
                    callback_data="connect:start",
                    custom_emoji_id=ID_LOCK_OPEN,
                )
            ]
        )
    rows.append(
        [_btn("Назад", callback_data="user:menu", custom_emoji_id=ID_DOWN)]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cancel_connect() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("Отмена", callback_data="connect:cancel", custom_emoji_id=ID_CROSS)]
        ]
    )


# ─── Админка ────────────────────────────────────────────────────────────────

def admin_menu() -> InlineKeyboardMarkup:
    rows = [
        [
            _btn(
                "Статистика",
                callback_data="admin:stats",
                custom_emoji_id=ID_STATS,
            )
        ],
        [
            _btn(
                "Список юзеров",
                callback_data="admin:users",
                custom_emoji_id=ID_PEOPLE,
            ),
            _btn(
                "Активные таймеры",
                callback_data="admin:timers",
                custom_emoji_id=ID_TIME_PASSED,
            ),
        ],
        [
            _btn(
                "Рассылка",
                callback_data="admin:broadcast",
                custom_emoji_id=ID_MEGAPHONE,
            )
        ],
        [
            _btn(
                "Выдать Premium",
                callback_data="admin:grant",
                custom_emoji_id=ID_GIFT,
            ),
            _btn(
                "Снять Premium",
                callback_data="admin:revoke",
                custom_emoji_id=ID_TRASH,
            ),
        ],
        [_btn("Назад", callback_data="user:menu", custom_emoji_id=ID_DOWN)],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_admin() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("Назад", callback_data="admin:menu", custom_emoji_id=ID_DOWN)]
        ]
    )


def broadcast_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("Отмена", callback_data="admin:menu", custom_emoji_id=ID_CROSS)]
        ]
    )


# ─── Reply-клавиатура: запрос номера телефона ───────────────────────────────

def request_phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Отправить номер", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
