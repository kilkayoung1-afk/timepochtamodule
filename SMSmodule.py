#              _   _ _ _     _             
#             | | | (_) |   | |            
#             | |_| |_| | __| | __ _       
#             |  _  | | |/ _` |/ _` |      
#             | | | | | | (_| | (_| |      
#             \_| |_/_|_|\__,_|\__,_|      
#                                          
#        Hikka SMS Receiver (POST Method)
#        Author: @Kilka_Young              

import aiohttp
import asyncio
from .. import loader, utils

# === НАСТРОЙКИ ===
API_KEY = "1b45Ac5f32776e26412b85c980c467fc"
SERVICE = "tg"
BASE_URL = "https://hero-sms.com/stubs/handler_api.php"

# Коды стран
COUNTRIES = {
    "ru": 0,
    "de": 43,
    "by": 13
}

@loader.tds
class HeroSMSPostMod(loader.Module):
    """Модуль SMS с использованием POST запроса для обхода ошибки 'must be a number'"""
    strings = {
        "name": "HeroSMS_Post",
        "no_active": "❌ Нет активного номера.",
        "usage": "ℹ️ <b>Использование:</b> <code>.number ru</code> или <code>.number de</code>",
        "error": "❗ Ошибка API: <code>{}</code>"
    }

    async def api_call(self, action, params=None):
        # Собираем данные. Важно: API_KEY и ACTION всегда нужны
        data = {
            "api_key": API_KEY,
            "action": action
        }
        if params:
            data.update(params)
        
        headers = {
            "User-Agent": "Mozilla/5.0",
            # Пробуем отправить как обычную форму, это часто решает проблему с типами данных
        }
        
        try:
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
                # Пробуем POST вместо GET, так как GET-параметры сервер почему-то видит как строки
                async with session.post(BASE_URL, data=data, timeout=15) as resp:
                    res_text = await resp.text()
                    # Если POST не поддерживается (ошибка 405), пробуем GET с жестким форматированием
                    if "405" in res_text or "Method Not Allowed" in res_text:
                        async with session.get(BASE_URL, params=data) as resp_get:
                            return await resp_get.text()
                    return res_text
        except Exception as e:
            return f"NET_ERROR: {str(e)}"

    async def numbercmd(self, message):
        """Взять номер: .number ru или .number de"""
        args = utils.get_args_raw(message).lower().strip()
        
        if not args or args not in COUNTRIES:
            return await utils.answer(message, self.strings("usage"))
        
        cid = COUNTRIES[args]
        
        # Передаем country именно как объект int
        res = await self.api_call("getNumber", {"service": SERVICE, "country": cid})
        
        if "ACCESS_NUMBER" in res:
            parts = res.split(":")
            aid = parts[1]
            phone = parts[2]
            self.set("active", {"id": aid, "phone": phone})
            await utils.answer(message, 
                f"📱 <b>Номер ({args.upper()}):</b> <code>{phone}</code>\n"
                f"🆔 <b>ID:</b> <code>{aid}</code>\n\n"
                f"<i>Ожидайте SMS и пишите .sms</i>")
        elif "NO_NUMBERS" in res:
            await utils.answer(message, "❌ Нет свободных номеров.")
        elif "NO_BALANCE" in res:
            await utils.answer(message, "❌ Баланс на нуле.")
        else:
            await utils.answer(message, self.strings("error").format(res))

    async def smscmd(self, message):
        """Проверить SMS (.sms)"""
        active = self.get("active")
        if not active: return await utils.answer(message, self.strings("no_active"))
        
        res = await self.api_call("getStatus", {"id": active["id"]})
        if "STATUS_OK" in res:
            code = res.split(":")[1]
            await utils.answer(message, f"📩 <b>Код:</b> <code>{code}</code>")
        elif "STATUS_WAIT_CODE" in res:
            await utils.answer(message, "⏳ Ждем код...")
        else:
            await utils.answer(message, self.strings("error").format(res))

    async def cancelcmd(self, message):
        """Отменить (.cancel)"""
        active = self.get("active")
        if not active: return
        # Для отмены обычно статус 8
        await self.api_call("setStatus", {"id": active["id"], "status": 8})
        self.set("active", None)
        await utils.answer(message, "🗑 Заказ отменен.")

    async def refreshcmd(self, message):
        """Обновить (.refresh)"""
        await self.smscmd(message)
