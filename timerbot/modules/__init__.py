"""
Реестр модулей. Импорт здесь подключает модуль в систему.
"""

from .base import Module, ModuleMeta, REGISTRY, all_modules, get, register
from . import timer  # noqa: F401  — регистрирует TimerModule

__all__ = ["Module", "ModuleMeta", "REGISTRY", "all_modules", "get", "register"]
