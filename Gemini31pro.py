# target: @Kilka_Young
# meta developer: @Kilka_Young
# scope: gemini_onlysq

import aiohttp
from .. import loader, utils

@loader.tds
class OnlySQGeminiMod(loader.Module):
    """Модуль для работы с Gemini-3.1-pro через сервис OnlySQ"""
    
    strings = {
        "name": "OnlySQGemini",
        "no_token": "<b>❌ Токен не установлен!</b>\nПолучи его на <a href='https://my.onlysq.ru/api-keys'>OnlySQ</a> и установи командой <code>.setgemini [токен]</code>",
        "set_token": "<b>✅ Токен успешно сохранен!</b>",
        "no_args": "<b>❌ Введи текст запроса или ответь на сообщение!</b>",
        "loading": "<b>🤔 Gemini думает...</b>",
        "error": "<b>❌ Ошибка API:</b> <code>{}</code>"
    }

    async def client_ready(self, client, db):
        self.db = db

    @loader.command()
    async def setgemini(self, message):
        """Установить API токен OnlySQ: .setgemini [token]"""
        args = utils.get_args_raw(message)
        if not args:
            return await utils.answer(message, self.strings("no_token"))
        
        self.db.set("OnlySQGemini", "token", args)
        await utils.answer(message, self.strings("set_token"))

    @loader.command()
    async def gemini(self, message):
        """Задать вопрос Gemini: .gemini [текст]"""
        token = self.db.get("OnlySQGemini", "token")
        if not token:
            return await utils.answer(message, self.strings("no_token"))

        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()
        
        prompt = args or (reply.text if reply else None)
        
        if not prompt:
            return await utils.answer(message, self.strings("no_args"))

        message = await utils.answer(message, self.strings("loading"))

        url = "https://api.onlysq.ru/ai/gemini"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        payload = {
            "model": "gemini-3.1-pro",
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    data = await response.json()
                    
                    if response.status == 200:
                        # Обычно ответ лежит в data['answer'] или data['choices'][0]['message']['content']
                        # Для OnlySQ часто структура упрощена:
                        answer = data.get("answer") or data.get("response") or data.get("result")
                        
                        if not answer and "choices" in data:
                            answer = data["choices"][0]["message"]["content"]
                            
                        await utils.answer(message, f"<b>♊ Gemini 3.1 Pro:</b>\n\n{answer}")
                    else:
                        error_msg = data.get("message") or data.get("error") or response.reason
                        await utils.answer(message, self.strings("error").format(error_msg))
        
        except Exception as e:
            await utils.answer(message, self.strings("error").format(str(e)))
