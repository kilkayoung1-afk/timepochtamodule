# meta developer: @Kilka_Young
# scope: hikka_only
# scope: hikka_min 1.6.2

import aiohttp
import json
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
                "Модель для использования (claude-opus-4, gemini-2.0-flash и т.д.)",
                validator=loader.validators.String()
            ),
            loader.ConfigValue(
                "max_tokens",
                4096,
                "Максимальное количество токенов в ответе",
                validator=loader.validators.Integer(minimum=1)
            )
        )
        self.conversation_history = {}
    
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
        """<вопрос> - Задать вопрос Claude/AI"""
        args = utils.get_args_raw(message)
        
        if not args:
            await utils.answer(message, self.strings["no_question"])
            return
        
        if not self.config["api_token"]:
            await utils.answer(message, self.strings["no_token"])
            return
        
        await utils.answer(message, self.strings["thinking"])
        
        try:
            response = await self._ask_ai(args)
            await utils.answer(message, f"🤖 <b>{self.config['model']}:</b>\n\n{response}")
        except Exception as e:
            await utils.answer(message, self.strings["error"].format(str(e)))
    
    @loader.command()
    async def sqclear(self, message):
        """Очистить историю диалога"""
        chat_id = message.chat_id
        if chat_id in self.conversation_history:
            del self.conversation_history[chat_id]
        await utils.answer(message, "✅ <b>История диалога очищена</b>")
    
    async def _ask_ai(self, question: str, chat_id: int = None) -> str:
        """Отправка запроса к AI через OnlySQ API"""
        
        headers = {
            "Authorization": f"Bearer {self.config['api_token']}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Формируем сообщения
        messages = [
            {
                "role": "user",
                "content": question
            }
        ]
        
        payload = {
            "model": self.config["model"],
            "messages": messages,
            "max_tokens": self.config["max_tokens"],
            "temperature": 0.7
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.config["api_url"], 
                json=payload, 
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f"API Error {resp.status}: {error_text}")
                
                data = await resp.json()
                
                # Извлекаем ответ
                if "choices" in data and len(data["choices"]) > 0:
                    return data["choices"][0]["message"]["content"]
                else:
                    raise Exception(f"Неожиданный формат ответа: {data}")
    
    @loader.command()
    async def sqinfo(self, message):
        """Информация о модуле OnlySQ"""
        info = (
            f"📋 <b>OnlySQ AI Module</b>\n\n"
            f"{self.strings['owner']}\n"
            f"🤖 <b>Модель:</b> <code>{self.config['model']}</code>\n"
            f"🔑 <b>Токен:</b> {'✅ Установлен' if self.config['api_token'] else '❌ Не установлен'}\n"
            f"🌐 <b>API URL:</b> <code>{self.config['api_url']}</code>\n"
            f"🌐 <b>Сайт:</b> https://my.onlysq.ru/api-keys\n\n"
            f"<b>Команды:</b>\n"
            f"• <code>.sqtoken [токен]</code> - установить токен\n"
            f"• <code>.claude [вопрос]</code> - спросить AI\n"
            f"• <code>.sqclear</code> - очистить историю\n"
            f"• <code>.sqinfo</code> - информация о модуле\n\n"
            f"<b>Примеры моделей:</b>\n"
            f"• claude-opus-4\n"
            f"• claude-sonnet-3.5\n"
            f"• gemini-2.0-flash\n"
            f"• gpt-4\n\n"
            f"Измените модель: <code>.config OnlySQ</code>"
        )
        await utils.answer(message, info)
    
    @loader.command()
    async def sqtest(self, message):
        """Тестовый запрос к API для проверки"""
        if not self.config["api_token"]:
            await utils.answer(message, self.strings["no_token"])
            return
        
        await utils.answer(message, "🔍 <b>Тестирую подключение к API...</b>")
        
        try:
            headers = {
                "Authorization": f"Bearer {self.config['api_token']}",
                "Content-Type": "application/json",
            }
            
            payload = {
                "model": self.config["model"],
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 50
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.config["api_url"],
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    status = resp.status
                    text = await resp.text()
                    
                    result = (
                        f"📊 <b>Результат теста:</b>\n\n"
                        f"<b>Status:</b> <code>{status}</code>\n"
                        f"<b>URL:</b> <code>{self.config['api_url']}</code>\n"
                        f"<b>Model:</b> <code>{self.config['model']}</code>\n\n"
                        f"<b>Response:</b>\n<code>{text[:500]}</code>"
                    )
                    await utils.answer(message, result)
        except Exception as e:
            await utils.answer(message, self.strings["error"].format(str(e)))
