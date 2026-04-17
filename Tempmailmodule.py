#              © Kilka_Young Development
#              Telegram Temporary Mail Module (Hikka Compatible)
#              Powered by 1secmail API

import asyncio
import aiohttp
import random
import string
import time
from telethon import events
from telethon.tl.types import Message

# Метаданные для Hikka/Heroku лоадеров
# info: {"category": "Tools", "description": "Temporary 10-minute mail via 1secmail API"}

class TempMailMod:
    """Модуль временной почты на 10 минут"""
    
    def __init__(self):
        self.active_mail = None
        self.last_check_id = 0
        self.is_running = False
        self.api_url = "https://www.1secmail.com/api/v1/"
        self.domains = ["1secmail.com", "1secmail.org", "1secmail.net"]

    async def _request(self, params):
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(self.api_url, params=params, timeout=10) as response:
                    return await response.json()
            except Exception as e:
                print(f"[TempMail] Error: {e}")
                return None

    def _generate_login(self):
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))

    async def mail_cmd(self, message: Message):
        """ .mail - Создать временную почту """
        if self.is_running:
            return await message.edit("❌ **У вас уже есть активная почта.**\nИспользуйте `.mailnew` для обновления или `.mailoff` для удаления.")

        login = self._generate_login()
        domain = random.choice(self.domains)
        self.active_mail = f"{login}@{domain}"
        self.is_running = True
        self.last_check_id = 0
        
        start_time = time.time()
        expiry_time = 600 # 10 минут
        
        await message.edit(
            f"📧 **Ваша временная почта:**\n`{self.active_mail}`\n\n"
            f"⏳ **Статус:** Мониторинг запущен (10 мин)\n"
            f"📥 *Письма будут приходить ответом на это сообщение.*"
        )

        # Фоновая задача проверки почты
        asyncio.create_task(self._mail_listener(message, login, domain, start_time, expiry_time))

    async def mailnew_cmd(self, message: Message):
        """ .mailnew - Сбросить и создать новую почту """
        self.is_running = False
        await asyncio.sleep(1)
        await self.mail_cmd(message)

    async def mailoff_cmd(self, message: Message):
        """ .mailoff - Остановить мониторинг """
        if not self.is_running:
            return await message.edit("🔘 **Активных сессий почты нет.**")
        
        self.is_running = False
        self.active_mail = None
        await message.edit("🗑 **Временная почта удалена. Мониторинг остановлен.**")

    async def _mail_listener(self, message, login, domain, start_time, duration):
        """Цикл проверки входящих писем"""
        while self.is_running:
            elapsed = time.time() - start_time
            if elapsed >= duration:
                self.is_running = False
                await message.respond(f"⏰ **Время жизни почты `{self.active_mail}` истекло.**")
                break

            # Получаем список сообщений
            params = {
                "action": "getMessages",
                "login": login,
                "domain": domain
            }
            
            data = await self._request(params)
            
            if data:
                for mail in data:
                    mail_id = mail.get("id")
                    if mail_id > self.last_check_id:
                        # Получаем полное содержимое письма
                        detail_params = {
                            "action": "readMessage",
                            "login": login,
                            "domain": domain,
                            "id": mail_id
                        }
                        full_mail = await self._request(detail_params)
                        
                        if full_mail:
                            sender = full_mail.get("from")
                            subject = full_mail.get("subject")
                            content = full_mail.get("textBody") or full_mail.get("body")
                            # Очистка текста от лишних HTML тегов если нужно (базово 1secmail отдает textBody)
                            
                            text = (
                                f"📩 **Новое письмо!**\n"
                                f"👤 **От:** `{sender}`\n"
                                f"📝 **Тема:** `{subject}`\n"
                                f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
                                f"{content[:3000]}" # Ограничение длины Telegram
                            )
                            await message.respond(text)
                            self.last_check_id = mail_id

            await asyncio.sleep(7) # Интервал проверки

# Регистрация команд для разных типов загрузчиков
# Если используется кастомный Hikka-like лоадер:
async def setup(client):
    mod = TempMailMod()
    client.add_event_handler(mod.mail_cmd, events.NewMessage(pattern=r"\.mail$", outgoing=True))
    client.add_event_handler(mod.mailnew_cmd, events.NewMessage(pattern=r"\.mailnew$", outgoing=True))
    client.add_event_handler(mod.mailoff_cmd, events.NewMessage(pattern=r"\.mailoff$", outgoing=True))

# Для стандартных модулей:
class TempMailModule:
    """Hikka compatibility wrapper"""
    strings = {"name": "TempMail"}
    
    def __init__(self):
        self.handler = TempMailMod()

    async def mailcmd(self, message):
        """Создать временную почту"""
        await self.handler.mail_cmd(message)

    async def mailnewcmd(self, message):
        """Обновить почту"""
        await self.handler.mailnew_cmd(message)

    async def mailoffcmd(self, message):
        """Удалить почту"""
        await self.handler.mailoff_cmd(message)
