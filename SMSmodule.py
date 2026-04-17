```python
# ©️ Kilka_Young, 2025
# 🔒 Licensed under the MIT License
# 📦 Module: Kilka Number
# 👤 Author: @Kilka_Young
# 📝 Description: Модуль для временных номеров и SMS

# meta developer: @Kilka_Young
# meta banner: https://i.imgur.com/placeholder.png

__version__ = (1, 0, 0)

import asyncio
import logging
import time
from datetime import datetime

import aiohttp
from telethon import TelegramClient
from .. import loader, utils

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Публичный API: sms-activate.org
# Документация: https://sms-activate.org/en/api2
# ─────────────────────────────────────────────

API_BASE = "https://api.sms-activate.org/stubs/handler_api.php"

COUNTRY_MAP = {
    "ru": {"id": "0", "flag": "🇷🇺", "name": "Россия"},
    "de": {"id": "43", "flag": "🇩🇪", "name": "Германия"},
}

NUMBER_LIFETIME = 30 * 60  # 30 минут в секундах


class SmsActivateAPI:
    """Клиент для sms-activate.org API."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session: aiohttp.ClientSession | None = None

    async def _request(self, params: dict) -> str:
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession()
        params["api_key"] = self.api_key
        async with self.session.get(API_BASE, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            text = await resp.text()
            logger.debug("[KilkaNumber] API response: %s", text)
            return text.strip()

    async def get_balance(self) -> float:
        result = await self._request({"action": "getBalance"})
        if result.startswith("ACCESS_BALANCE:"):
            return float(result.split(":")[1])
        raise ValueError(f"Ошибка баланса: {result}")

    async def get_number(self, country_id: str, service: str = "tg") -> tuple[str, str]:
        """Получить номер. Возвращает (activation_id, phone_number)."""
        result = await self._request({
            "action": "getNumber",
            "service": service,
            "country": country_id,
        })
        if result.startswith("ACCESS_NUMBER:"):
            parts = result.split(":")
            activation_id = parts[1]
            phone = parts[2]
            return activation_id, phone
        if result == "NO_NUMBERS":
            raise ValueError("❌ Нет доступных номеров для этой страны")
        if result == "NO_BALANCE":
            raise ValueError("❌ Недостаточно баланса на API-аккаунте")
        raise ValueError(f"Ошибка получения номера: {result}")

    async def get_sms(self, activation_id: str) -> str | None:
        """Получить SMS. None если SMS ещё не пришла."""
        result = await self._request({
            "action": "getStatus",
            "id": activation_id,
        })
        if result.startswith("STATUS_OK:"):
            return result.split(":", 1)[1]
        if result in ("STATUS_WAIT_CODE", "STATUS_WAIT_RESEND"):
            return None
        if result == "STATUS_CANCEL":
            raise ValueError("❌ Активация отменена")
        return None

    async def cancel_number(self, activation_id: str) -> bool:
        """Отменить номер досрочно."""
        result = await self._request({
            "action": "setStatus",
            "id": activation_id,
            "status": "8",
        })
        return result == "ACCESS_CANCEL"

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()


@loader.tds
class KilkaNumberMod(loader.Module):
    """Модуль временных виртуальных номеров и SMS. Автор: @Kilka_Young"""

    strings = {
        "name": "Kilka Number",
        "no_key": (
            "⚙️ <b>API-ключ не настроен!</b>\n\n"
            "Перейди на <a href='https://sms-activate.org'>sms-activate.org</a>, "
            "зарегистрируйся и вставь ключ в конфиг модуля:\n"
            "<code>.config KilkaNumber api_key ВАШ_КЛЮЧ</code>"
        ),
        "invalid_country": (
            "❌ <b>Неверная страна.</b>\n"
            "Доступные: <code>ru</code> 🇷🇺, <code>de</code> 🇩🇪\n\n"
            "Пример: <code>.number ru</code>"
        ),
        "already_active": (
            "⚠️ <b>У тебя уже есть активный номер!</b>\n\n"
            "📱 <code>+{phone}</code>\n"
            "⏳ Истекает через: <b>{remaining}</b>\n\n"
            "Используй <code>.cancel</code> для досрочного удаления."
        ),
        "creating": "⏳ <b>Создаём номер для {flag} {name}...</b>",
        "created": (
            "✅ <b>Номер успешно создан!</b>\n\n"
            "📱 Номер: <code>+{phone}</code>\n"
            "{flag} Страна: <b>{name}</b>\n"
            "⏳ Действует: <b>30 минут</b>\n"
            "🕐 Истекает: <b>{expires}</b>\n\n"
            "💬 Для проверки SMS: <code>.sms</code>\n"
            "🔄 Обновить SMS: <code>.refresh</code>\n"
            "❌ Отменить: <code>.cancel</code>"
        ),
        "no_active": (
            "❌ <b>Нет активного номера.</b>\n\n"
            "Создай новый: <code>.number ru</code> или <code>.number de</code>"
        ),
        "sms_wait": (
            "📭 <b>SMS ещё не получены.</b>\n\n"
            "📱 Номер: <code>+{phone}</code>\n"
            "⏳ Осталось: <b>{remaining}</b>\n\n"
            "🔄 Обновить: <code>.refresh</code>"
        ),
        "sms_received": (
            "📬 <b>SMS получена!</b>\n\n"
            "📱 Номер: <code>+{phone}</code>\n"
            "💬 Сообщение:\n<code>{sms}</code>\n\n"
            "🕐 Получено: <b>{time}</b>"
        ),
        "cancelled": "✅ <b>Номер <code>+{phone}</code> успешно отменён.</b>",
        "cancel_fail": "⚠️ <b>Не удалось отменить номер. Он истечёт автоматически.</b>",
        "expired": "⌛ <b>Номер <code>+{phone}</code> автоматически удалён (истёк срок жизни).</b>",
        "api_error": "❌ <b>Ошибка API:</b> {error}",
        "balance": "💰 <b>Баланс API:</b> <code>{balance} ₽</code>",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "api_key",
                "",
                "API-ключ от sms-activate.org",
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "default_service",
                "tg",
                "Сервис для номера (tg, wa, vk, go, etc.)",
                validator=loader.validators.String(),
            ),
        )
        self._active: dict = {}   # {user_id: {activation_id, phone, country, created_at, sms}}
        self._api: SmsActivateAPI | None = None
        self._cleanup_tasks: dict = {}

    def _get_api(self) -> SmsActivateAPI | None:
        key = self.config["api_key"]
        if not key:
            return None
        if self._api is None or self._api.api_key != key:
            self._api = SmsActivateAPI(key)
        return self._api

    def _format_remaining(self, created_at: float) -> str:
        elapsed = time.time() - created_at
        remaining = max(0, NUMBER_LIFETIME - elapsed)
        minutes = int(remaining // 60)
        seconds = int(remaining % 60)
        return f"{minutes:02d}:{seconds:02d}"

    def _format_expires(self, created_at: float) -> str:
        expires_ts = created_at + NUMBER_LIFETIME
        return datetime.fromtimestamp(expires_ts).strftime("%H:%M:%S")

    async def _schedule_cleanup(self, user_id: int, activation_id: str, phone: str, delay: float):
        """Автоудаление номера через delay секунд."""
        await asyncio.sleep(delay)
        if user_id in self._active and self._active[user_id]["activation_id"] == activation_id:
            api = self._get_api()
            if api:
                try:
                    await api.cancel_number(activation_id)
                except Exception:
                    pass
            del self._active[user_id]
            logger.info("[KilkaNumber] Номер +%s для user %s автоматически удалён", phone, user_id)

    @loader.command(ru_doc="Создать временный номер: .number ru / .number de")
    async def numbercmd(self, message):
        """Создать временный номер. Использование: .number ru | .number de"""
        api = self._get_api()
        if not api:
            await utils.answer(message, self.strings["no_key"])
            return

        args = utils.get_args_raw(message).strip().lower()
        if args not in COUNTRY_MAP:
            await utils.answer(message, self.strings["invalid_country"])
            return

        user_id = message.sender_id

        if user_id in self._active:
            data = self._active[user_id]
            remaining = self._format_remaining(data["created_at"])
            await utils.answer(
                message,
                self.strings["already_active"].format(
                    phone=data["phone"],
                    remaining=remaining,
                ),
            )
            return

        country = COUNTRY_MAP[args]
        await utils.answer(
            message,
            self.strings["creating"].format(flag=country["flag"], name=country["name"]),
        )

        try:
            activation_id, phone = await api.get_number(
                country_id=country["id"],
                service=self.config["default_service"],
            )
        except ValueError as e:
            await utils.answer(message, self.strings["api_error"].format(error=str(e)))
            return
        except Exception as e:
            logger.exception("[KilkaNumber] Ошибка get_number")
            await utils.answer(message, self.strings["api_error"].format(error=str(e)))
            return

        created_at = time.time()
        self._active[user_id] = {
            "activation_id": activation_id,
            "phone": phone,
            "country": args,
            "created_at": created_at,
            "sms": None,
        }

        task = asyncio.create_task(
            self._schedule_cleanup(user_id, activation_id, phone, NUMBER_LIFETIME)
        )
        self._cleanup_tasks[user_id] = task

        logger.info("[KilkaNumber] Создан номер +%s (id=%s) для user %s", phone, activation_id, user_id)

        await utils.answer(
            message,
            self.strings["created"].format(
                phone=phone,
                flag=country["flag"],
                name=country["name"],
                expires=self._format_expires(created_at),
            ),
        )

    @loader.command(ru_doc="Показать входящие SMS для активного номера")
    async def smscmd(self, message):
        """Показать входящие SMS."""
        api = self._get_api()
        if not api:
            await utils.answer(message, self.strings["no_key"])
            return

        user_id = message.sender_id
        if user_id not in self._active:
            await utils.answer(message, self.strings["no_active"])
            return

        data = self._active[user_id]
        await self._fetch_and_show_sms(message, api, data, user_id)

    @loader.command(ru_doc="Обновить список SMS")
    async def refreshcmd(self, message):
        """Обновить SMS (то же, что .sms, но с пометкой «обновлено»)."""
        await self.smscmd(message)

    @loader.command(ru_doc="Досрочно отменить активный номер")
    async def cancelcmd(self, message):
        """Отменить активный номер досрочно."""
        api = self._get_api()
        if not api:
            await utils.answer(message, self.strings["no_key"])
            return

        user_id = message.sender_id
        if user_id not in self._active:
            await utils.answer(message, self.strings["no_active"])
            return

        data = self._active[user_id]
        phone = data["phone"]
        activation_id = data["activation_id"]

        if user_id in self._cleanup_tasks:
            self._cleanup_tasks[user_id].cancel()
            del self._cleanup_tasks[user_id]

        try:
            success = await api.cancel_number(activation_id)
        except Exception:
            success = False

        del self._active[user_id]
        logger.info("[KilkaNumber] Номер +%s (id=%s) отменён пользователем %s", phone, activation_id, user_id)

        if success:
            await utils.answer(message, self.strings["cancelled"].format(phone=phone))
        else:
            await utils.answer(message, self.strings["cancel_fail"])

    @loader.command(ru_doc="Проверить баланс API аккаунта sms-activate")
    async def smsbalancecmd(self, message):
        """Проверить баланс sms-activate.org."""
        api = self._get_api()
        if not api:
            await utils.answer(message, self.strings["no_key"])
            return
        try:
            balance = await api.get_balance()
            await utils.answer(message, self.strings["balance"].format(balance=f"{balance:.2f}"))
        except Exception as e:
            await utils.answer(message, self.strings["api_error"].format(error=str(e)))

    async def _fetch_and_show_sms(self, message, api: SmsActivateAPI, data: dict, user_id: int):
        phone = data["phone"]
        activation_id = data["activation_id"]
        remaining = self._format_remaining(data["created_at"])

        # Если SMS уже была получена ранее — показываем кэш
        if data.get("sms"):
            await utils.answer(
                message,
                self.strings["sms_received"].format(
                    phone=phone,
                    sms=data["sms"],
                    time=data.get("sms_time", "—"),
                ),
            )
            return

        try:
            sms = await api.get_sms(activation_id)
        except ValueError as e:
            await utils.answer(message, self.strings["api_error"].format(error=str(e)))
            return
        except Exception as e:
            logger.exception("[KilkaNumber] Ошибка get_sms")
            await utils.answer(message, self.strings["api_error"].format(error=str(e)))
            return

        if sms:
            sms_time = datetime.now().strftime("%H:%M:%S")
            self._active[user_id]["sms"] = sms
            self._active[user_id]["sms_time"] = sms_time
            await utils.answer(
                message,
                self.strings["sms_received"].format(
                    phone=phone,
                    sms=sms,
                    time=sms_time,
                ),
            )
        else:
            await utils.answer(
                message,
                self.strings["sms_wait"].format(phone=phone, remaining=remaining),
            )

    async def on_unload(self):
        """Очистка при выгрузке модуля."""
        for task in self._cleanup_tasks.values():
            task.cancel()
        self._cleanup_tasks.clear()
        if self._api:
            await self._api.close()
        logger.info("[KilkaNumber] Модуль выгружен, ресурсы освобождены")


def register(cb):
    cb(KilkaNumberMod())
```
