#              _   _ _ _     _             
#             | | | (_) |   | |            
#             | |_| |_| | __| | __ _       
#             |  _  | | |/ _` |/ _` |      
#             | | | | | | (_| | (_| |      
#             \_| |_/_|_|\__,_|\__,_|      
#                                          
#        Hikka SMS Receiver (SSL-Secure)
#        Author: @Kilka_Young              

import aiohttp
import asyncio
import time
from .. import loader, utils

# === НАСТРОЙКИ ===
API_KEY = "1b45Ac5f32776e26412b85c980c467fc"
SERVICE = "tg"
COUNTRY = "ru"
# Используем HTTPS и полный путь
BASE_URL = "https://hero-sms.com/stubs/handler_api.php"

@loader.tds
class HeroSMSSecureMod(loader.Module):
    """Модуль SMS с обходом блокировок через заголовки"""
    strings = {
        "name": "HeroSMS_New",
        "no_active": "❌ Нет активного номера.",
        "error": "❗ Ошибка: <code>{}</code>"
    }

    async def api_call(self, action, params=None):
        p = {"api_key": API_KEY, "action": action}
        if params: p.update(params)
        
        # Маскируемся под обычный браузер
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "*/*"
        }
        
        try:
            # Отключаем проверку SSL (иногда Heroku блокирует из-за этого)
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
                async with session.get(BASE_URL, params=p, timeout=15) as resp:
                    text = await resp.text()
                    return text
        except Exception as e:
            return f"NET_ERROR: {str(e)}"

    async def numbercmd(self, message):
        """Взять номер (.number)"""
        res = await self.api_call("getNumber", {"service": SERVICE, "country": COUNTRY})
        
        if "ACCESS_NUMBER" in res:
            _, aid, phone = res.split(":")
            self.set("active", {"id": aid, "phone": phone})
            await utils.answer(message, f"📱 <b>Номер:</b> <code>{phone}</code>\n🆔 <b>ID:</b> <code>{aid}</code>")
        else:
            await utils.answer(message, f"❗ <b>Ответ сервиса:</b> {res}")

    async def smscmd(self, message):
        """Проверить SMS (.sms)"""
        active = self.get("active")
        if not active: return await utils.answer(message, self.strings["no_active"])
        
        res = await self.api_call("getStatus", {"id": active["id"]})
        if "STATUS_OK" in res:
            await utils.answer(message, f"📩 <b>Код:</b> <code>{res.split(':')[1]}</code>")
        elif "STATUS_WAIT_CODE" in res:
            await utils.answer(message, "⏳ SMS еще не пришло.")
        else:
            await utils.answer(message, f"📝 Статус: {res}")

    async def cancelcmd(self, message):
        """Отменить номер (.cancel)"""
        active = self.get("active")
        if not active: return
        await self.api_call("setStatus", {"id": active["id"], "status": 8})
        self.set("active", None)
        await utils.answer(message, "🗑 Номер отменен.")

    async def refreshcmd(self, message):
        """Обновить (.refresh)"""
        await self.smscmd(message)
