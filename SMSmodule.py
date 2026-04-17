#              _   _ _ _     _             
#             | | | (_) |   | |            
#             | |_| |_| | __| | __ _       
#             |  _  | | |/ _` |/ _` |      
#             | | | | | | (_| | (_| |      
#             \_| |_/_|_|\__,_|\__,_|      
#                                          
#        Hikka SMS Receiver (RU/DE)
#        Author: @Kilka_Young              

import aiohttp
import asyncio
from .. import loader, utils

# === НАСТРОЙКИ ===
API_KEY = "1b45Ac5f32776e26412b85c980c467fc"
SERVICE = "tg"
BASE_URL = "https://hero-sms.com/stubs/handler_api.php"

# Коды стран для Hero-SMS:
# 0 - Россия, 43 - Германия
COUNTRIES = {
    "ru": "0",
    "de": "43"
}

@loader.tds
class HeroSMSMultiMod(loader.Module):
    """Модуль SMS с выбором страны (Россия/Германия)"""
    strings = {
        "name": "HeroSMS_Multi",
        "no_active": "❌ Нет активного номера.",
        "usage": "ℹ️ <b>Использование:</b> <code>.number ru</code> или <code>.number de</code>",
        "error": "❗ Ошибка API: <code>{}</code>"
    }

    async def api_call(self, action, params=None):
        p = {"api_key": API_KEY, "action": action}
        if params: p.update(params)
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "*/*"
        }
        
        try:
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
                async with session.get(BASE_URL, params=p, timeout=15) as resp:
                    return await resp.text()
        except Exception as e:
            return f"NET_ERROR: {str(e)}"

    async def numbercmd(self, message):
        """Взять номер: .number ru или .number de"""
        args = utils.get_args_raw(message).lower().strip()
        
        if not args or args not in COUNTRIES:
            return await utils.answer(message, self.strings("usage"))
        
        country_id = COUNTRIES[args]
        country_name = "🇷🇺 Россия" if args == "ru" else "🇩🇪 Германия"

        res = await self.api_call("getNumber", {"service": SERVICE, "country": country_id})
        
        if "ACCESS_NUMBER" in res:
            parts = res.split(":")
            aid = parts[1]
            phone = parts[2]
            self.set("active", {"id": aid, "phone": phone})
            await utils.answer(message, 
                f"📱 <b>Номер ({country_name}):</b> <code>{phone}</code>\n"
                f"🆔 <b>ID:</b> <code>{aid}</code>\n\n"
                f"<i>Ожидайте SMS и пишите .sms</i>")
        elif "NO_NUMBERS" in res:
            await utils.answer(message, f"❌ В стране {country_name} сейчас нет свободных номеров.")
        elif "NO_BALANCE" in res:
            await utils.answer(message, "❌ Недостаточно средств на балансе.")
        else:
            await utils.answer(message, self.strings("error").format(res))

    async def smscmd(self, message):
        """Проверить SMS (.sms)"""
        active = self.get("active")
        if not active: 
            return await utils.answer(message, self.strings("no_active"))
        
        res = await self.api_call("getStatus", {"id": active["id"]})
        if "STATUS_OK" in res:
            code = res.split(":")[1]
            await utils.answer(message, f"📩 <b>Ваш код:</b> <code>{code}</code>")
        elif "STATUS_WAIT_CODE" in res:
            await utils.answer(message, "⏳ SMS еще не получено. Ожидайте...")
        elif "STATUS_CANCEL" in res:
            self.set("active", None)
            await utils.answer(message, "❌ Номер отменен сервисом.")
        else:
            await utils.answer(message, self.strings("error").format(res))

    async def cancelcmd(self, message):
        """Отменить номер (.cancel)"""
        active = self.get("active")
        if not active: return
        await self.api_call("setStatus", {"id": active["id"], "status": 8})
        self.set("active", None)
        await utils.answer(message, "🗑 Номер успешно отменен.")

    async def refreshcmd(self, message):
        """Обновить статус (.refresh)"""
        await self.smscmd(message)
                                       
