#              _   _ _ _     _             
#             | | | (_) |   | |            
#             | |_| |_| | __| | __ _       
#             |  _  | | |/ _` |/ _` |      
#             | | | | | | (_| | (_| |      
#             \_| |_/_|_|\__,_|\__,_|      
#                                          
#        Hikka SMS Receiver Module (Anti-Block)
#        Author: @Kilka_Young              
#        API: Hero-SMS.com                 

import aiohttp
import asyncio
import time
from .. import loader, utils

# === НАСТРОЙКИ ===
API_KEY = "1b45Ac5f32776e26412b85c980c467fc"
SERVICE = "tg"
COUNTRY = "ru"
BASE_URL = "https://api.hero-sms.com/stubs/handler_api.php"

# Если без VPN не работает, вставь сюда адрес прокси (например "http://user:pass@ip:port")
# Если оставить None, будет пытаться соединиться напрямую
PROXY = None 

@loader.tds
class HeroSMSMod(loader.Module):
    """Модуль для получения номеров через Hero-SMS (с обходом блокировок)"""
    strings = {
        "name": "HeroSMS",
        "no_money": "❌ <b>Недостаточно средств.</b>",
        "no_number": "❌ <b>Нет свободных номеров.</b>",
        "active_exists": "⚠️ <b>Уже есть активный номер:</b> <code>{}</code>",
        "no_active": "❌ <b>Нет активных заказов.</b>",
        "num_info": "📱 <b>Номер:</b> <code>{}</code>\n🆔 <b>ID:</b> <code>{}</code>\n\n<i>Используйте .sms для проверки</i>",
        "sms_wait": "⏳ <b>SMS еще не пришло...</b>",
        "sms_res": "📩 <b>Код:</b> <code>{}</code>",
        "canceled": "🗑 <b>Заказ #{} отменен.</b>",
        "conn_error": "🌐 <b>Ошибка подключения!</b> Сервис заблокирован или недоступен без VPN/Proxy.",
        "error": "❗ <b>Ошибка API:</b> <code>{}</code>"
    }

    async def api_call(self, action, params=None):
        p = {"api_key": API_KEY, "action": action}
        if params: p.update(params)
        
        try:
            async with aiohttp.ClientSession() as session:
                # Используем proxy, если он указан
                async with session.get(BASE_URL, params=p, proxy=PROXY, timeout=15) as resp:
                    return await resp.text()
        except Exception:
            return "CONNECTION_ERROR"

    async def numbercmd(self, message):
        """Получить номер"""
        uid = str(message.sender_id)
        if self.get(uid):
            return await utils.answer(message, self.strings("active_exists").format(self.get(uid)['phone']))

        res = await self.api_call("getNumber", {"service": SERVICE, "country": COUNTRY})
        
        if res == "CONNECTION_ERROR":
            return await utils.answer(message, self.strings("conn_error"))
            
        if "ACCESS_NUMBER" in res:
            _, aid, phone = res.split(":")
            self.set(uid, {"id": aid, "phone": phone, "time": time.time()})
            await utils.answer(message, self.strings("num_info").format(phone, aid))
        elif "NO_NUMBERS" in res:
            await utils.answer(message, self.strings("no_number"))
        elif "NO_BALANCE" in res:
            await utils.answer(message, self.strings("no_money"))
        else:
            await utils.answer(message, self.strings("error").format(res))

    async def smscmd(self, message):
        """Проверить SMS"""
        uid = str(message.sender_id)
        active = self.get(uid)
        if not active:
            return await utils.answer(message, self.strings("no_active"))

        res = await self.api_call("getStatus", {"id": active["id"]})

        if res == "CONNECTION_ERROR":
            return await utils.answer(message, self.strings("conn_error"))

        if "STATUS_OK" in res:
            code = res.split(":")[1]
            await utils.answer(message, self.strings("sms_res").format(code))
        elif "STATUS_WAIT_CODE" in res:
            await utils.answer(message, self.strings("sms_wait"))
        elif "STATUS_CANCEL" in res:
            self.set(uid, None)
            await utils.answer(message, "❌ Номер отменен сервисом.")
        else:
            await utils.answer(message, self.strings("error").format(res))

    async def refreshcmd(self, message):
        """Обновить статус"""
        await self.smscmd(message)

    async def cancelcmd(self, message):
        """Отменить номер"""
        uid = str(message.sender_id)
        active = self.get(uid)
        if not active:
            return await utils.answer(message, self.strings("no_active"))

        await self.api_call("setStatus", {"id": active["id"], "status": 8})
        self.set(uid, None)
        await utils.answer(message, self.strings("canceled").format(active['id']))
