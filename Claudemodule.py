# -*- coding: utf-8 -*-

"""
    OnlySQ AI Module
    Владелец: @Kilka_Young
    API: https://my.onlysq.ru/api-keys
    Модель: Claude Opus 4.6
"""

__version__ = (1, 0, 1)

import aiohttp
import logging
from .. import loader, utils

logger = logging.getLogger(__name__)


class OnlySQMod(loader.Module):
    """Модуль для работы с OnlySQ AI (Claude Opus 4.6)"""

    strings = {
        "name": "OnlySQ",
        "no_token": "❌ <b>Токен не установлен!</b>\n\n"
                   "Получите токен: https://my.onlysq.ru/api-keys\n"
                   "Установите: <code>.sqtoken ВАШ_ТОКЕН</code>",
        "token_saved": "✅ <b>Токен успешно сохранен!</b>",
        "no_question": "❌ <b>Укажите запрос!</b>\n"
                      "Пример: <code>.sq Привет, как дела?</code>",
        "thinking": "🤔 <b>Думаю...</b>",
        "error": "❌ <b>Ошибка:</b> <code>{}</code>",
        "response": "💬 <b>Claude Opus 4.6:</b>\n\n{}",
        "api_error": "❌ <b>Ошибка API:</b> {}\n\n"
                    "Проверьте токен: https://my.onlysq.ru/api-keys",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "api_token",
                None,
                lambda: "API токен от https://my.onlysq.ru/api-keys",
                validator=loader.validators.Hidden(),
            ),
            loader.ConfigValue(
                "model",
                "claude-opus-4.6",
                lambda: "Модель AI (по умолчанию: claude-opus-4.6)",
            ),
            loader.ConfigValue(
                "max_tokens",
                4096,
                lambda: "Максимальное количество токенов в ответе",
                validator=loader.validators.Integer(minimum=100),
            ),
        )

    async def client_ready(self, client, db):
        self._db = db
        self._client = client

    @loader.command(ru_doc="Установить API токен")
    async def sqtokencmd(self, message):
        """Установить API токен от OnlySQ"""
        args = utils.get_args_raw(message)
        
        if not args:
            await utils.answer(message, self.strings["no_token"])
            return
        
        self.config["api_token"] = args.strip()
        await utils.answer(message, self.strings["token_saved"])

    @loader.command(ru_doc="Отправить запрос к Claude Opus 4.6")
    async def sqcmd(self, message):
        """<запрос> - Отправить запрос к Claude Opus 4.6"""
        args = utils.get_args_raw(message)
        
        if not args:
            await utils.answer(message, self.strings["no_question"])
            return
        
        if not self.config["api_token"]:
            await utils.answer(message, self.strings["no_token"])
            return
        
        await utils.answer(message, self.strings["thinking"])
        
        try:
            response = await self._make_request(args)
            await utils.answer(
                message,
                self.strings["response"].format(response)
            )
        except Exception as e:
            logger.exception("OnlySQ API error")
            await utils.answer(
                message,
                self.strings["api_error"].format(str(e))
            )

    async def _make_request(self, prompt: str) -> str:
        """Отправка запроса к OnlySQ API"""
        url = "https://api.onlysq.ru/ai/openai"
        
        headers = {
            "Authorization": f"Bearer {self.config['api_token']}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.config["model"],
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": self.config["max_tokens"],
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f"HTTP {resp.status}: {error_text}")
                
                data = await resp.json()
                
                if "choices" not in data or not data["choices"]:
                    raise Exception("Пустой ответ от API")
                
                return data["choices"][0]["message"]["content"]

    @loader.command(ru_doc="Информация о модуле")
    async def sqinfocmd(self, message):
        """Показать информацию о модуле"""
        info = (
            f"📱 <b>OnlySQ AI Module</b>\n\n"
            f"👤 <b>Владелец:</b> @Kilka_Young\n"
            f"🤖 <b>Модель:</b> {self.config['model']}\n"
            f"🔑 <b>Токен:</b> {'✅ Установлен' if self.config['api_token'] else '❌ Не установлен'}\n"
            f"📊 <b>Max tokens:</b> {self.config['max_tokens']}\n"
            f"🌐 <b>API:</b> https://api.onlysq.ru/ai/openai\n\n"
            f"🔗 <b>Получить токен:</b> https://my.onlysq.ru/api-keys\n\n"
            f"<b>Команды:</b>\n"
            f"• <code>.sqtoken [токен]</code> - установить токен\n"
            f"• <code>.sq [запрос]</code> - отправить запрос\n"
            f"• <code>.sqinfo</code> - информация о модуле"
        )
        await utils.answer(message, info)
