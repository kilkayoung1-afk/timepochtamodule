"""
Базовый интерфейс модуля и реестр модулей.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from database import DB
    from userbot import UserbotManager


@dataclass
class ModuleMeta:
    key: str        # машинный ключ ("timer")
    title: str      # отображаемое имя ("Таймер")
    description: str
    requires_session: bool = True   # модуль работает на юзер-сессии
    premium_only: bool = True       # только Premium-пользователи


class Module:
    """Базовый класс модуля. Подкласс реализует start/stop."""

    meta: ModuleMeta

    async def start(
        self,
        user_id: int,
        session_string: str,
        config: dict,
        db: "DB",
        userbot: "UserbotManager",
    ) -> None:
        raise NotImplementedError

    async def stop(
        self,
        user_id: int,
        db: "DB",
        userbot: "UserbotManager",
    ) -> None:
        raise NotImplementedError


# Реестр заполняется в modules/__init__.py
REGISTRY: dict[str, Module] = {}


def register(module: Module) -> Module:
    REGISTRY[module.meta.key] = module
    return module


def get(key: str) -> Module | None:
    return REGISTRY.get(key)


def all_modules() -> list[dict]:
    return [
        {
            "key": m.meta.key,
            "title": m.meta.title,
            "description": m.meta.description,
            "requires_session": m.meta.requires_session,
            "premium_only": m.meta.premium_only,
        }
        for m in REGISTRY.values()
    ]
