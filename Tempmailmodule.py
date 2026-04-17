# meta developer: @Kilka_Young
# description: TempMail module (10 min email)

import aiohttp
import asyncio
import time
import random
import string
from .. import loader, utils

@loader.tds
class TempMailMod(loader.Module):
    """TempMail module (10 min email)"""
    strings = {"name": "TempMail"}

    def __init__(self):
        self.users_mail = {}
        # Маскируемся под обычный браузер, чтобы обойти базовые защиты 1secmail
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    async def _check_mail(self, message):
        user_id = message.sender_id if message.sender_id else message.chat_id
        if user_id not in self.users_mail:
            await utils.answer(message, "❌ У вас нет активной почты. Создайте её командой <code>.mail</code>")
            return None
        
        mail_data = self.users_mail[user_id]
        if time.time() > mail_data['expire_time']:
            del self.users_mail[user_id]
            await utils.answer(message, "❌ Срок действия вашей почты истек (10 минут). Создайте новую командой <code>.mail</code>")
            return None
            
        return mail_data

    @loader.command()
    async def mailcmd(self, message):
        """Создать временную почту"""
        user_id = message.sender_id if message.sender_id else message.chat_id
        await utils.answer(message, "⏳ Создание временной почты...")
        
        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                # Отключаем проверку SSL (ssl=False) для совместимости со старыми серверами
                async with session.get("https://www.1secmail.com/api/v1/?action=getDomainList", ssl=False) as resp:
                    if resp.status != 200:
                        raise Exception(f"HTTP Status {resp.status}")
                    domains = await resp.json(content_type=None) # Игнорируем тип контента на случай кривых заголовков API
            
            domain = random.choice(domains)
            login = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
            email = f"{login}@{domain}"
            
            self.users_mail[user_id] = {
                "email": email,
                "login": login,
                "domain": domain,
                "expire_time": time.time() + 600
            }
            
            print(f"[TempMail] [+] Created email {email} for {user_id}")
            
            await utils.answer(
                message,
                f"📧 <b>Ваша временная почта:</b>\n"
                f"<code>{email}</code>\n\n"
                f"⏱ <i>Действительна 10 минут.</i>\n"
                f"🔄 Проверить письма: <code>.letters</code>"
            )
        except Exception as e:
            print(f"[TempMail] [-] Error creating mail: {type(e).__name__}: {e}")
            await utils.answer(message, f"❌ <b>Ошибка API 1secmail:</b>\n<code>{type(e).__name__}: {e}</code>")

    @loader.command()
    async def letterscmd(self, message):
        """Список писем"""
        mail_data = await self._check_mail(message)
        if not mail_data:
            return
            
        await utils.answer(message, "⏳ Проверка почты...")
        
        try:
            url = f"https://www.1secmail.com/api/v1/?action=getMessages&login={mail_data['login']}&domain={mail_data['domain']}"
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.get(url, ssl=False) as resp:
                    if resp.status != 200:
                        raise Exception(f"HTTP Status {resp.status}")
                    messages = await resp.json(content_type=None)
                    
            if not messages:
                await utils.answer(
                    message,
                    f"📭 <b>Входящие для</b> <code>{mail_data['email']}</code>:\n\n"
                    f"<i>Писем пока нет. Обновите список командой <code>.refresh</code></i>"
                )
                print(f"[TempMail] [i] No new letters for {mail_data['email']}")
                return
            
            text = f"📬 <b>Входящие для</b> <code>{mail_data['email']}</code>:\n\n"
            for msg in messages:
                text += f"🆔 ID: <code>{msg['id']}</code>\n"
                text += f"👤 От: <code>{msg['from']}</code>\n"
                text += f"📝 Тема: <i>{msg['subject']}</i>\n"
                text += "➖➖➖➖➖➖➖➖➖➖\n"
            
            text += "\n📖 Прочитать письмо: <code>.read &lt;id&gt;</code>"
            await utils.answer(message, text)
            print(f"[TempMail] [+] Fetched {len(messages)} letters for {mail_data['email']}")
            
        except Exception as e:
            print(f"[TempMail] [-] Error fetching letters: {type(e).__name__}: {e}")
            await utils.answer(message, f"❌ <b>Ошибка при получении писем:</b>\n<code>{type(e).__name__}: {e}</code>")

    @loader.command()
    async def refreshcmd(self, message):
        """Обновить список писем (повторный запрос)"""
        await self.letterscmd(message)

    @loader.command()
    async def readcmd(self, message):
        """Прочитать письмо"""
        args = utils.get_args_raw(message)
        if not args or not args.isdigit():
            await utils.answer(message, "❌ Укажите корректный ID письма. Пример: <code>.read 12345678</code>")
            return
            
        msg_id = args
        mail_data = await self._check_mail(message)
        if not mail_data:
            return
            
        await utils.answer(message, "⏳ Загрузка письма...")
        
        try:
            url = f"https://www.1secmail.com/api/v1/?action=readMessage&login={mail_data['login']}&domain={mail_data['domain']}&id={msg_id}"
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.get(url, ssl=False) as resp:
                    if resp.status != 200:
                        raise Exception(f"HTTP Status {resp.status}")
                    msg_data = await resp.json(content_type=None)
            
            if "id" not in msg_data:
                await utils.answer(message, "❌ Письмо не найдено. Возможно, неверный ID или оно было удалено.")
                return
            
            body = msg_data.get('textBody', '')
            if not body:
                body = msg_data.get('htmlBody', '<i>Пустое письмо или содержит только HTML/Вложения</i>')
                
            if len(body) > 3000:
                body = body[:3000] + "...\n\n[Текст слишком длинный и был обрезан]"
                
            text = (
                f"📖 <b>Письмо</b> <code>{msg_id}</code>\n"
                f"👤 <b>От:</b> <code>{msg_data['from']}</code>\n"
                f"📝 <b>Тема:</b> <i>{msg_data['subject']}</i>\n"
                f"📅 <b>Дата:</b> {msg_data['date']}\n"
                f"➖➖➖➖➖➖➖➖➖➖\n\n"
                f"{body}"
            )
            
            await utils.answer(message, text)
            print(f"[TempMail] [+] Read letter {msg_id} for {mail_data['email']}")
            
        except Exception as e:
            print(f"[TempMail] [-] Error reading letter: {type(e).__name__}: {e}")
            await utils.answer(message, f"❌ <b>Ошибка при загрузке письма:</b>\n<code>{type(e).__name__}: {e}</code>")

def register(cb):
    cb.add_class(TempMailMod)
