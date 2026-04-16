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
                "Модель для использования",
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
    async def sqfind(self, message):
        """Автоматически найти правильный API endpoint"""
        if not self.config["api_token"]:
            await utils.answer(message, self.strings["no_token"])
            return
        
        await utils.answer(message, "🔍 <b>Ищу правильный API endpoint...</b>")
        
        # Список возможных URL для проверки
        possible_urls = [
            "https://api.onlysq.ru/v1/chat/completions",
            "https://my.onlysq.ru/v1/chat/completions",
            "https://onlysq.ru/v1/chat/completions",
            "https://api.onlysq.ru/chat/completions",
            "https://my.onlysq.ru/api/v1/chat/completions",
            "https://my.onlysq.ru/api/chat/completions",
            "https://api.onlysq.ru/api/v1/chat/completions",
        ]
        
        headers = {
            "Authorization": f"Bearer {self.config['api_token']}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.config["model"],
            "messages": [{"role": "user", "content": "test"}],
            "max_tokens": 10
        }
        
        results = []
        
        async with aiohttp.ClientSession() as session:
            for url in possible_urls:
                try:
                    async with session.post(
                        url,
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as resp:
                        status = resp.status
                        results.append(f"✅ {url}\nСтатус: {status}")
                        
                        if status == 200:
                            self.config["api_url"] = url
                            await utils.answer(
                                message,
                                f"✅ <b>Найден рабочий endpoint!</b>\n\n"
                                f"<code>{url}</code>\n\n"
                                f"Сохранён в конфиг. Теперь можно использовать <code>.claude</code>"
                            )
                            return
                        elif status not in [404, 405]:
                            results.append(f"⚠️ Возможный вариант: {url} (статус {status})")
                except Exception as e:
                    results.append(f"❌ {url}\nОшибка: {str(e)[:50]}")
        
        result_text = "📊 <b>Результаты поиска:</b>\n\n" + "\n\n".join(results[:5])
        result_text += "\n\n❌ <b>Рабочий endpoint не найден</b>\n\nПожалуйста, проверьте документацию OnlySQ или укажите URL вручную через <code>.config OnlySQ</code>"
        await utils.answer(message, result_text)
    
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
    
    async def _ask_ai(self, question: str) -> str:
        """Отправка запроса к AI через OnlySQ API"""
        
        headers = {
            "Authorization": f"Bearer {self.config['api_token']}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.config["model"],
            "messages": [
                {
                    "role": "user",
                    "content": question
                }
            ],
            "max_tokens": self.config["max_tokens"]
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
                    raise Exception(f"API Error {resp.status}. Используйте .sqfind для поиска правильного URL")
                
                data = await resp.json()
                
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
            f"🌐 <b>API URL:</b> <code>{self.config['api_url']}</code>\n\n"
            f"<b>Команды:</b>\n"
            f"• <code>.sqtoken [токен]</code> - установить токен\n"
            f"• <code>.sqfind</code> - найти правильный API URL\n"
            f"• <code>.claude [вопрос]</code> - спросить AI\n"
            f"• <code>.sqinfo</code> - информация\n\n"
            f"🌐 <b>Получить токен:</b> https://my.onlysq.ru/api-keys"
        )
        await utils.answer(message, info)
