"""
Регистрация всех роутеров.
"""

from aiogram import Dispatcher

from . import admin, connect, modules_h, start


def register_all(dp: Dispatcher) -> None:
    dp.include_router(start.router)
    dp.include_router(connect.router)
    dp.include_router(modules_h.router)
    dp.include_router(admin.router)
