#              _   _ _ _     _             
#             | | | (_) |   | |            
#             | |_| |_| | __| | __ _       
#             |  _  | | |/ _` |/ _` |      
#             | | | | | | (_| | (_| |      
#             \_| |_/_|_|\__,_|\__,_|      
#                                          
#        Hikka SMS Receiver (Fixed Int)
#        Author: @Kilka_Young              

import aiohttp
import asyncio
from .. import loader, utils

# === НАСТРОЙКИ ===
API_KEY = "1b45Ac5f32776e26412b85c980c467fc"
SERVICE = "tg"
BASE_URL = "https://hero-sms.com/stubs/handler_api.php"

# Коды стран (строго числа)
COUNTRIES = {
    "ru": 0,
    "de": 43,
    "by": 13
}

@loader.tds
class HeroSMSFixedMod(loader.Module):
    """Модуль SMS с исправлением передачи чисел в API"""
    strings = {
        "name": "HeroSMS_Fixed",
        "no_active": "❌ Нет активного номера.",
        "usage": "ℹ️ <b>Использование:</b> <code>.number ru</code> или <code>.number de</code>",
        "error": "❗ Ошибка API: <code>{}</code>"
    }

    async def api_call(self, action, params=None):
        # Формируем параметры, гарантируя, что ID страны — это число без кавычек в URL
        p = f"api_key={API_KEY}&action={action}"
        if params:
            for k, v in params.items():
                p += f"&{k}={v}"
        
        url = f"{BASE_URL}?{p}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        
        try:
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
                async with session.get(url, timeout=15) as resp:
                    return await resp.text()
        except Exception as e:
            return f"NET_ERROR: {str(e)}"

    async def numbercmd(self, message):
        """Взять номер: .number ru или .number de"""
        args = utils.get_args_raw(message).lower().strip()
        
        if not args or args not in COUNTRIES:
            return await utils.answer(message, self.strings("usage"))
        
        cid = COUNTRIES[args]
        res = await self.api_call("getNumber", {"service": SERVICE, "country": cid})
        
        if "ACCESS_NUMBER" in res:
            parts = res.split(":")
            aid, phone = parts[1], parts[2]
            self.set("active", {"id": aid, "phone": phone})
            await utils.answer(message, 
                f"📱 <b>Номер ({args.upper()}):</b> <code>{phone}</code>\n"
                f"🆔 <b>ID:</b> <code>{aid}</code>\n\n"
                f"<i>Ожидайте SMS и пишите .sms</i>")
        elif "NO_NUMBERS" in res:
            await utils.answer(message, "❌ Нет свободных номеров в этой локации.")
        elif "NO_BALANCE" in res:
            await utils.answer(message, "❌ Пополните баланс на Hero-SMS.")
        else:
            await utils.answer(message, self.strings("error").format(res))

    async def smscmd(self, message):
        """Проверить SMS (.sms)"""
        active = self.get("active")
        if not active: return await utils.answer(message, self.strings("no_active"))
        
        res = await self.api_call("getStatus", {"id": active["id"]})
        if "STATUS_OK" in res:
            await utils.answer(message, f"📩 <b>Код:</b> <code>{res.split(':')[1]}</code>")
        elif "STATUS_WAIT_CODE" in res:
            await utils.answer(message, "⏳ Ожидаем поступления SMS...")
        else:
            await utils.answer(message, self.strings("error").format(res))

    async def cancelcmd(self, message):
        """Отменить (.cancel)"""
        active = self.get("active")
        if not active: return
        await self.api_call("setStatus", {"id": active["id"], "status": 8})
        self.set("active", None)
        await utils.answer(message, "🗑 Заказ отменен.")

    async def refreshcmd(self, message):
        """Обновить (.refresh)"""
        await self.smscmd(message)
