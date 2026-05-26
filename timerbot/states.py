"""
FSM-состояния пользовательских сценариев.
"""

from aiogram.fsm.state import State, StatesGroup


class ConnectStates(StatesGroup):
    """Подключение Pyrogram-сессии (телефон → код → 2FA)."""

    phone = State()
    code = State()
    password = State()


class TimerStates(StatesGroup):
    """Настройка модуля «Таймер»."""

    format = State()
    base_name = State()


class AdminStates(StatesGroup):
    broadcast = State()
    grant_premium = State()
    revoke_premium = State()
