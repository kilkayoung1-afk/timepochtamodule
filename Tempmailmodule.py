# tempmail.py — Модуль временной почты для Hikka / Heroku Loader
# Исправлено: ошибки NameError и логика ручной проверки
#Developer: @Kilka_Young
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
    """Временная почта с ручным обновлением (.mailcheck)"""
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
            return await utils.answer(message, f"✅ Активна: <code>{self._sessions[uid].email}</code>")
        await self._create_mail(message, uid)

    @loader.command()
    async def mailcheckcmd(self, message: Message):
        """.mailcheck — проверить почту вручную"""
        uid = message.sender_id
        if uid not in self._sessions or not self._sessions[uid].is_alive:
            return await utils.answer(message, "❌ Нет активной почты. Используйте .mail")
        
        sess = self._sessions[uid]
        await utils.answer(message, "🔍 Проверяю входящие...")
        
        new_msgs = await self._fetch_emails(sess, message.chat_id)
        if not new_msgs:
            await asyncio.sleep(1)
            await utils.answer(message, "📭 Новых писем пока нет.")

    @loader.command()
    async def mailnewcmd(self, message: Message):
        """.mailnew — удалить текущую и создать новую почту"""
        await self._stop_session(message.sender_id)
        await self._create_mail(message, message.sender_id)

    @loader.command()
    async def mailoffcmd(self, message: Message):
        """.mailoff — остановить сессию почты"""
        uid = message.sender_id
        if uid in self._sessions:
            email = self._sessions[uid].email
            await self._stop_session(uid)
            await utils.answer(message, f"🗑 Почта <code>{email}</code> удалена.")
        else:
            await utils.answer(message, "❌ Нет активных сессий.")

    # ── Внутренняя логика ──────────────────────────────────────────────────

    async def _create_mail(self, message, uid):
        login = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
        domain = random.choice(DOMAINS)
        sess = MailSession(login, domain)
        
        status_text = (
            f"📧 <b>Ваша почта:</b> <code>{sess.email}</code>\n"
            f"⏳ <b>Истекает через:</b> {sess.fmt_remaining()}\n\n"
            f"🔄 <i>Для проверки:</i> <code>.mailcheck</code>"
        )
        
        msg = await utils.answer(message, status_text)
        sess.msg_id = msg[0].id if isinstance(msg, (list, tuple)) else msg.id
        self._sessions[uid] = sess
        sess.task = asyncio.create_task(self._worker(uid, message.chat_id))

    async def _fetch_emails(self, sess: MailSession, chat_id):
        if not self._http: return False
        
        url = f"{API_BASE}?action=getMessages&login={sess.login}&domain={sess.domain}"
        found_new = False
        try:
            async with self._http.get(url, timeout=10) as r:
                if r.status == 200:
                    letters = await r.json()
                    for letter in letters:
                        lid = letter.get("id")
                        if lid and lid not in sess.seen_ids:
                            sess.seen_ids.add(lid)
                            # Читаем полное письмо
                            read_url = f"{API_BASE}?action=readMessage&login={sess.login}&domain={sess.domain}&id={lid}"
                            async with self._http.get(read_url, timeout=10) as rr:
                                if rr.status == 200:
                                    full = await rr.json()
                                    found_new = True
                                    await self._client.send_message(chat_id, self._format_letter(full))
        except Exception as e:
            logger.warning(f"[TempMail] Fetch error: {e}")
        return found_new

    def _format_letter(self, msg: dict) -> str:
        sender = msg.get("from", "—")
        subject = msg.get("subject", "(без темы)")
        body = re.sub(r"<[^>]+>", "", (msg.get("body") or "")).strip()
        return (
            f"📨 <b>Новое письмо!</b>\n"
            f"─────────────────\n"
            f"👤 <b>От:</b> {sender}\n"
            f"📌 <b>Тема:</b> {subject}\n\n"
            f"{body[:1200]}"
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
                # Обновляем статус (таймер)
                status_text = (
                    f"📧 <b>Ваша почта:</b> <code>{sess.email}</code>\n"
                    f"⏳ <b>Истекает через:</b> {sess.fmt_remaining()}\n\n"
                    f"🔄 <i>Для проверки:</i> <code>.mailcheck</code>"
                )
                await self._client.edit_message(chat_id, sess.msg_id, status_text)
                await self._fetch_emails(sess, chat_id)
            except: pass
            await asyncio.sleep(CHECK_INTERVAL)
        self._sessions.pop(uid, None)
