# tempmail.py — Модуль временной почты для Hikka / Heroku Loader
# Использует 1secmail.com API
# Владелец: @Kilka_Young

import asyncio
import random
import string
import logging
import re
from datetime import datetime, timedelta

import aiohttp
from telethon import TelegramClient
from telethon.tl.types import Message

try:
    from .. import loader, utils 
    HIKKA = True
except ImportError:
    HIKKA = False

logger = logging.getLogger(__name__)

# ─── Константы ────────────────────────────────────────────────────────────────
API_BASE      = "https://www.1secmail.com/api/v1/"
MAIL_LIFETIME = 600
CHECK_INTERVAL = 8
DOMAINS = ["1secmail.com", "1secmail.net", "1secmail.org", "wwjmp.com", "esiix.com"]

class MailSession:
    def __init__(self, login: str, domain: str):
        self.login   = login
        self.domain  = domain
        self.email   = f"{login}@{domain}"
        self.created = datetime.utcnow()
        self.expires = self.created + timedelta(seconds=MAIL_LIFETIME)
        self.seen_ids: set[int] = set()     
        self.msg_id: int | None = None      
        self.task: asyncio.Task | None = None

    @property
    def remaining(self) -> int:
        delta = (self.expires - datetime.utcnow()).total_seconds()
        return max(0, int(delta))

    @property
    def is_alive(self) -> bool:
        return self.remaining > 0

    def fmt_remaining(self) -> str:
        s = self.remaining
        return f"{s // 60:02d}:{s % 60:02d}"

# ─────────────────────────────────────────────────────────────────────────────

@loader.tds
class TempMailMod(loader.Module):
    """Временная почта. Владелец: @Kilka_Young"""
    
    strings = {"name": "TempMail"}

    def __init__(self):
        self._sessions: dict[int, MailSession] = {}
        self._http: aiohttp.ClientSession | None = None

    async def client_ready(self, client, db):
        self._client = client
        self._http = aiohttp.ClientSession()

    # ── Команды ─────────────────────────────────────────────────────────────

    @loader.command()
    async def mailcmd(self, message: Message):
        """.mail — создать временный email"""
        uid = message.sender_id
        if uid in self._sessions and self._sessions[uid].is_alive:
            sess = self._sessions[uid]
            return await utils.answer(message, f"✅ Активна: <code>{sess.email}</code>\n⏳ {sess.fmt_remaining()}")
        await self._create_mail(message, uid)

    @loader.command()
    async def mailcheckcmd(self, message: Message):
        """.mailcheck — проверить почту вручную"""
        uid = message.sender_id
        if uid not in self._sessions or not self._sessions[uid].is_alive:
            return await utils.answer(message, "❌ Нет активной почты. Напиши .mail")
        
        sess = self._sessions[uid]
        await utils.answer(message, "🔍 <b>Проверяю новые письма...</b>")
        
        received = await self._fetch_emails(sess, message.chat_id)
        if not received:
            await asyncio.sleep(1)
            await utils.answer(message, "📭 <b>Новых писем нет.</b>")

    @loader.command()
    async def mailnewcmd(self, message: Message):
        """.mailnew — удалить текущую и создать новую почту"""
        await self._stop_session(message.sender_id)
        await self._create_mail(message, message.sender_id)

    @loader.command()
    async def mailoffcmd(self, message: Message):
        """.mailoff — удалить текущую почту"""
        uid = message.sender_id
        if uid in self._sessions:
            email = self._sessions[uid].email
            await self._stop_session(uid)
            await utils.answer(message, f"🗑 Почта <code>{email}</code> удалена.\n👑 Владелец: @Kilka_Young")
        else:
            await utils.answer(message, "❌ У тебя нет активной почты.")

    # ── Внутренняя логика ──────────────────────────────────────────────────

    async def _create_mail(self, message, uid):
        # Исправлено: генерация логина напрямую в методе
        login = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
        domain = random.choice(DOMAINS)
        sess = MailSession(login, domain)
        
        status_text = (
            f"📧 <b>Временная почта:</b> <code>{sess.email}</code>\n"
            f"⏳ <b>Осталось:</b> {sess.fmt_remaining()}\n\n"
            f"🔄 <i>Жду письма... (или нажми <code>.mailcheck</code>)</i>\n"
            f"👑 <b>Dev:</b> @Kilka_Young"
        )
        
        msg = await utils.answer(message, status_text)
        sess.msg_id = msg[0].id if isinstance(msg, (list, tuple)) else msg.id
        self._sessions[uid] = sess
        sess.task = asyncio.create_task(self._worker(uid, message.chat_id))

    async def _fetch_emails(self, sess: MailSession, chat_id):
        if not self._http: return False
        
        url = f"{API_BASE}?action=getMessages&login={sess.login}&domain={sess.domain}"
        found_any = False
        try:
            async with self._http.get(url, timeout=10) as r:
                if r.status == 200:
                    data = await r.json()
                    for m in data:
                        mid = m.get("id")
                        if mid and mid not in sess.seen_ids:
                            sess.seen_ids.add(mid)
                            # Запрашиваем содержимое письма
                            read_url = f"{API_BASE}?action=readMessage&login={sess.login}&domain={sess.domain}&id={mid}"
                            async with self._http.get(read_url, timeout=10) as rr:
                                if rr.status == 200:
                                    content = await rr.json()
                                    found_any = True
                                    await self._client.send_message(chat_id, self._format_msg(content))
        except Exception as e:
            logger.error(f"Error fetching mail: {e}")
        return found_any

    def _format_msg(self, m: dict) -> str:
        sender = m.get("from", "Неизвестно")
        subject = m.get("subject", "(Без темы)")
        body = m.get("textBody") or m.get("body") or ""
        body = re.sub(r"<[^>]+>", "", body).strip()
        return (
            f"📨 <b>Новое письмо!</b>\n"
            f"👤 <b>От:</b> <code>{sender}</code>\n"
            f"📌 <b>Тема:</b> {subject}\n"
            f"─────────────────\n"
            f"{body[:1500]}"
        )

    async def _stop_session(self, uid):
        if uid in self._sessions:
            sess = self._sessions.pop(uid)
            if sess.task: sess.task.cancel()

    async def _worker(self, uid, chat_id):
        while uid in self._sessions:
            sess = self._sessions[uid]
            if not sess.is_alive: break
            try:
                # Обновляем сообщение со статусом (таймер)
                status_text = (
                    f"📧 <b>Временная почта:</b> <code>{sess.email}</code>\n"
                    f"⏳ <b>Осталось:</b> {sess.fmt_remaining()}\n\n"
                    f"🔄 <i>Проверка каждые {CHECK_INTERVAL}с...</i>\n"
                    f"👑 <b>Dev:</b> @Kilka_Young"
                )
                await self._client.edit_message(chat_id, sess.msg_id, status_text)
                await self._fetch_emails(sess, chat_id)
            except: pass
            await asyncio.sleep(CHECK_INTERVAL)
        
        if uid in self._sessions:
            self._sessions.pop(uid)
