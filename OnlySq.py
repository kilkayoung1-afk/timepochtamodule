# meta developer: @Kilka_Young
# scope: hikka_only
# scope: hikka_min 1.6.2

import aiohttp
from .. import loader, utils

@loader.tds
class OnlySQMod(loader.Module):
    """Модуль для работы с Claude Opus 4.6 через OnlySQ API"""
    
    strings = {
        "name": "OnlySQ",
        "no_token": "🔑 <b>Укажите API токен!</b>\n\nПолучите его на: https://my.onlysq.ru/api-keys\n\nИспользуйте: <code>.sqtoken ВАШ_ТОКЕН</code>",
        "token_saved": "✅ <b>Токен успешно сохранён!</b>",
        "no_question": "❓ <b>Укажите вопрос для Claude!</b>\n\nПример: <code>.claude Привет, как дела?</code>",
        "thinking": "🤔 <b>Claude думает...</b>",
        "error": "❌ <b>Ошибка:</b> <code>{}</code>",
        "owner": "👤 <b>Владелец модуля:</b> @Kilka_Young"
    }
    
    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "api_token",
                "",
                "API токен от https://my.onlysq.ru/api-keys",
                validator=loader.validators.String()
            ),
            loader.ConfigValue(
                "api_url",
                "https://api.onlysq.ru/v1/chat/completions",
                "URL API endpoint",
                validator=loader.validators.String()
            ),
            loader.ConfigValue(
                "model",
                "claude-opus-4",
                "Модель Claude для использования",
                validator=loader.validators.String()
            ),
            loader.ConfigValue(
                "max_tokens",
                4096,
                "Максимальное количество токенов в ответе",
                validator=loader.validators.Integer(minimum=1)
            )
        )
    
    async def client_ready(self, client, db):
        self.client = client
        self.db = db
    
    @loader.command()
    async def sqtoken(self, message):
        """<токен> - Установить API токен OnlySQ"""
        args = utils.get_args_raw(message)
        if not args:
            await utils.answer(message, self.strings["no_token"])
            return
        
        self.config["api_token"] = args.strip()
        await utils.answer(message, self.strings["token_saved"])
    
    @loader.command()
    async def claude(self, message):
        """<вопрос> - Задать вопрос Claude Opus"""
        args = utils.get_args_raw(message)
        
        if not args:
            await utils.answer(message, self.strings["no_question"])
            return
        
        if not self.config["api_token"]:
            await utils.answer(message, self.strings["no_token"])
            return
        
        await utils.answer(message, self.strings["thinking"])
        
        try:
            response = await self._ask_claude(args)
            await utils.answer(message, f"🤖 <b>Claude:</b>\n\n{response}")
        except Exception as e:
            await utils.answer(message, self.strings["error"].format(str(e)))
    
    async def _ask_claude(self, question: str) -> str:
        """Отправка запроса к Claude через OnlySQ API"""
        
        headers = {
            "Authorization": f"Bearer {self.config['api_token']}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.config["model"],
            "messages": [
                {
                    "role": "user",
                    "content": question
                }
            ],
            "max_tokens": self.config["max_tokens"],
            "stream": False
        }
        
        # Пробуем разные URL
        urls = [
            self.config["api_url"],
            "https://api.onlysq.ru/v1/chat/completions",
            "https://my.onlysq.ru/api/v1/chat/completions",
            "https://onlysq.ru/v1/chat/completions",
        ]
        
        async with aiohttp.ClientSession() as session:
            for url in urls:
                try:
                    async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            # Сохраняем рабочий URL
                            self.config["api_url"] = url
                            return data["choices"][0]["message"]["content"]
                        elif resp.status != 405:  # Если не 405, пробуем обработать другие ошибки
                            error_text = await resp.text()
                            raise Exception(f"API Error {resp.status}: {error_text}")
                except aiohttp.ClientError:
                    continue
            
            raise Exception("Не удалось найти рабочий API endpoint. Проверьте токен и доступность сервиса.")
    
    @loader.command()
    async def sqinfo(self, message):
        """Информация о модуле OnlySQ"""
        info = (
            f"📋 <b>OnlySQ Claude Module</b>\n\n"
            f"{self.strings['owner']}\n"
            f"🤖 <b>Модель:</b> <code>{self.config['model']}</code>\n"
            f"🔑 <b>Токен:</b> {'✅ Установлен' if self.config['api_token'] else '❌ Не установлен'}\n"
            f"🌐 <b>API URL:</b> <code>{self.config['api_url']}</code>\n"
            f"🌐 <b>Сайт:</b> https://my.onlysq.ru/api-keys\n\n"
            f"<b>Команды:</b>\n"
            f"• <code>.sqtoken</code> - установить токен\n"
            f"• <code>.claude</code> - спросить Claude\n"
            f"• <code>.sqinfo</code> - информация о модуле\n\n"
            f"<b>Доступные модели:</b>\n"
            f"• claude-opus-4\n"
            f"• claude-sonnet-3.5\n"
            f"• claude-3-opus\n\n"
            f"Измените модель: <code>.config OnlySQ</code>"
        )
        await utils.answer(message, info)
