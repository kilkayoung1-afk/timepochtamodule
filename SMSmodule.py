#              _   _ _ _     _             
#             | | | (_) |   | |            
#             | |_| |_| | __| | __ _       
#             |  _  | | |/ _` |/ _` |      
#             | | | | | | (_| | (_| |      
#             \_| |_/_|_|\__,_|\__,_|      
#                                          
#        Hikka SMS Receiver Module         
#        Author: @Kilka_Young              
#        API: 5sim.net                     

import aiohttp
import asyncio
import time
from .. import loader, utils

# === НАСТРОЙКИ ===
API_KEY = "YOUR_API_KEY"
SERVICE = "telegram"
COUNTRY = "russia"
BASE_URL = "https://api5sim.net/v1/user"

@loader.tds
class SMSReceiverMod(loader.Module):
    """Модуль для получения временных номеров через 5sim"""
    strings = {
        "name": "SMSReceiver",
        "no_key": "❌ <b>API ключ не установлен в коде!</b>",
        "no_money": "❌ <b>Недостаточно средств на балансе.</b>",
        "no_number": "❌ <b>Нет доступных номеров для этого сервиса/страны.</b>",
        "active_exists": "⚠️ <b>У вас уже есть активный номер:</b> <code>{}</code>",
        "no_active": "❌ <b>У вас нет активного номера.</b>",
        "num_info": "📱 <b>Номер:</b> <code>{}</code>\n🕒 <b>ID:</b> <code>{}</code>\n⌛️ <b>Истекает через:</b> 15 мин.\n\n<i>Используйте .sms для проверки кода</i>",
        "sms_wait": "⏳ <b>SMS еще не пришло. Попробуйте позже или .refresh</b>",
        "sms_res": "📩 <b>Ваш код:</b> <code>{}</code>\n📝 <b>Текст:</b> <code>{}</code>",
        "canceled": "🗑 <b>Заказ #{} отменен.</b>",
        "error": "❗ <b>Ошибка API:</b> <code>{}</code>"
    }

    async def client_get(self, path):
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Accept": "application/json"
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(f"{BASE_URL}{path}") as resp:
                if resp.status == 401:
                    return "no_key"
                return await resp.json()

    async def numbercmd(self, message):
        """Получить временный номер"""
        if API_KEY == "YOUR_API_KEY":
            return await utils.answer(message, self.strings("no_key"))

        uid = str(message.sender_id)
        active = self.get(uid, None)
        
        if active:
            # Проверка на просрочку (15 минут)
            if time.time() - active['time'] < 900:
                return await utils.answer(message, self.strings("active_exists").format(active['phone']))
            else:
                self.set(uid, None)

        data = await self.client_get(f"/buy/activation/{COUNTRY}/{SERVICE}")
        
        if isinstance(data, str): return await utils.answer(message, self.strings(data))
        if "id" not in data:
            if "no free" in str(data).lower():
                return await utils.answer(message, self.strings("no_number"))
            return await utils.answer(message, self.strings("error").format(data))

        self.set(uid, {
            "id": data["id"],
            "phone": data["phone"],
            "time": time.time()
        })

        await utils.answer(message, self.strings("num_info").format(data["phone"], data["id"]))

    async def smscmd(self, message):
        """Посмотреть SMS"""
        uid = str(message.sender_id)
        active = self.get(uid, None)
        if not active:
            return await utils.answer(message, self.strings("no_active"))

        data = await self.client_get(f"/check/{active['id']}")
        
        if "sms" in data and data["sms"]:
            sms_data = data["sms"][-1]
            await utils.answer(message, self.strings("sms_res").format(sms_data["code"], sms_data["text"]))
        else:
            await utils.answer(message, self.strings("sms_wait"))

    async def refreshcmd(self, message):
        """Обновить статус SMS"""
        await self.smscmd(message)

    async def cancelcmd(self, message):
        """Отменить текущий номер"""
        uid = str(message.sender_id)
        active = self.get(uid, None)
        if not active:
            return await utils.answer(message, self.strings("no_active"))

        data = await self.client_get(f"/cancel/{active['id']}")
        self.set(uid, None)
        await utils.answer(message, self.strings("canceled").format(active['id']))

    async def on_unload(self):
        # Очистка не требуется, так как используется встроенный db
        pass
