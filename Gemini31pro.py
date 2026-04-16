# meta developer: @Kilka_Young
# scope: hikka_only
# scope: hikka_min 1.2.10

import aiohttp
from telethon.tl.types import Message
from .. import loader, utils

@loader.tds
class GeminiAIMod(loader.Module):
    """Модуль для работы с Gemini AI через OnlySQ API"""
    
    strings = {
        "name": "GeminiAI",
        "no_token": "❌ <b>Токен не установлен!</b>\n\n"
                   "Получите токен на https://my.onlysq.ru/api-keys\n"
                   "Установите командой: <code>.config GeminiAI</code>",
        "no_question": "❌ <b>Укажите вопрос!</b>\n"
                      "Использование: <code>.gemini [вопрос]</code>",
        "processing": "🤔 <b>Думаю...</b>",
        "error": "❌ <b>Ошибка:</b> <code>{}</code>",
        "response": "💎 <b>Gemini AI:</b>\n\n{}",
        "token_set": "✅ <b>Токен успешно установлен!</b>",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "api_token",
                None,
                lambda: "API токен с https://my.onlysq.ru/api-keys",
                validator=loader.validators.Hidden()
            ),
            loader.ConfigValue(
                "model",
                "gemini-3.1-pro",
                lambda: "Модель для использования",
            ),
        )

    async def client_ready(self, client, db):
        self.client = client
        self.db = db

    @loader.command()
    async def gemini(self, message: Message):
        """<вопрос> - Спросить у Gemini AI"""
        
        args = utils.get_args_raw(message)
        
        if not args:
            await utils.answer(message, self.strings["no_question"])
            return
        
        if not self.config["api_token"]:
            await utils.answer(message, self.strings["no_token"])
            return
        
        await utils.answer(message, self.strings["processing"])
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.config['api_token']}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": self.config["model"],
                    "messages": [
                        {
                            "role": "user",
                            "content": args
                        }
                    ]
                }
                
                async with session.post(
                    "https://api.onlysq.ru/ai/gemini",
                    json=payload,
                    headers=headers
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        await utils.answer(
                            message, 
                            self.strings["error"].format(f"HTTP {resp.status}: {error_text}")
                        )
                        return
                    
                    data = await resp.json()
                    
                    # Попытка извлечь ответ из разных возможных структур
                    response_text = (
                        data.get("choices", [{}])[0].get("message", {}).get("content") or
                        data.get("response") or
                        data.get("text") or
                        str(data)
                    )
                    
                    await utils.answer(
                        message,
                        self.strings["response"].format(response_text)
                    )
                    
        except Exception as e:
            await utils.answer(
                message,
                self.strings["error"].format(str(e))
            )
