# tempmail.py — Модуль временной почты для Hikka / Heroku Loader
# Исправлено: добавлена принудительная проверка писем (.mailcheck)

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

# ─── API Helpers ────────────────────────────────────────────────────────────

async def _fetch_emails(http_session, sess: MailSession, client, chat_id):
    """Логика получения и отправки писем (вынесена для вызова из разных команд)"""
    letters = await _get_messages(http_session, sess.login, sess.domain)
    found_new = False
    for letter in letters:
        lid = letter.get("id")
        if lid and lid not in sess.seen_ids:
            sess.seen_ids.add(lid)
            full = await _read_message(http_session, sess.login, sess.domain, lid)
            if full:
                found_new = True
                try:
                    await client.send_message(chat_id, _format_letter(full))
                except Exception as e:
                    logger.warning(f"[TempMail] send error: {e}")
    return found_new

async def _get_messages(session, login, domain):
    url = f"{API_BASE}?action=getMessages&login={login}&domain={domain}"
    try:
        async with session.get(url, timeout=10) as r:
            return await r.json() if r.status == 200 else []
    except: return []

async def _read_message(session, login, domain, msg_id):
    url = f"{API_BASE}?action=readMessage&login={login}&domain={domain}&id={msg_id}"
    try:
        async with session.get(url, timeout=10) as r:
            return await r.json() if r.status == 200 else None
    except: return None

def _format_mail_status(sess: MailSession) -> str:
    return (
        "📧 <b>Ваша почта:</b> <code>{0}</code>\n"
        "⏳ <b>Истекает через:</b> {1}\n\n"
        "🔄 <i>Для ручной проверки:</i> <code>.mailcheck</code>"
    ).format(sess.email, sess.fmt_remaining())

def _format_letter(msg: dict) -> str:
    sender = msg.get("from", "—")
    subject = msg.get("subject", "(без темы)")
    body = re.sub(r"<[^>]+>", "", (msg.get("body") or "")).strip()
    return f"📨 <b>Новое письмо!</b>\n" \
           f"👤 <b>От:</b> {sender}\n" \
           f"📌 <b>Тема:</b> {subject}\n\n" \
           f"{body[:1200]}"

# ─────────────────────────────────────────────────────────────────────────────

if HIKKA:
    @loader.tds
    class TempMailMod(loader.Module):
        """Временная почта с ручным обновлением"""
        strings = {"name": "TempMail"}

        def __init__(self):
            self._sessions: dict[int, MailSession] = {}
            self._http: aiohttp.ClientSession | None = None

        async def client_ready(self, client, db):
            self._client = client
            self._http = aiohttp.ClientSession()

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
                return await utils.answer(message, "❌ Нет активной почты. Создайте её через .mail")
            
            sess = self._sessions[uid]
            await utils.answer(message, "🔍 Проверяю входящие...")
            
            new_msgs = await _fetch_emails(self._http, sess, self._client, message.chat_id)
            
            if not new_msgs:
                await asyncio.sleep(1)
                await utils.answer(message, "📭 Новых писем пока нет.")

        @loader.command()
        async def mailnewcmd(self, message: Message):
            """.mailnew — новая почта"""
            await self._stop_session(message.sender_id)
            await self._create_mail(message, message.sender_id)

        @loader.command()
        async def mailoffcmd(self, message: Message):
            """.mailoff — удалить почту"""
            uid = message.sender_id
            if uid in self._sessions:
                await self._stop_session(uid)
                await utils.answer(message, "🗑 Почта удалена.")
            else:
                await utils.answer(message, "❌ Нет активных сессий.")

        async def _create_mail(self, message, uid):
            sess = MailSession(_random_login(), random.choice(DOMAINS))
            msg = await utils.answer(message, _format_mail_status(sess))
            sess.msg_id = msg[0].id if isinstance(msg, (list, tuple)) else msg.id
            self._sessions[uid] = sess
            sess.task = asyncio.create_task(self._worker(uid, message.chat_id))

        async def _stop_session(self, uid):
            if uid in self._sessions:
                sess = self._sessions.pop(uid)
                if sess.task: sess.task.cancel()

        async def _worker(self, uid, chat_id):
            sess = self._sessions.get(uid)
            while sess and sess.is_alive:
                try:
                    await self._client.edit_message(chat_id, sess.msg_id, _format_mail_status(sess))
                    await _fetch_emails(self._http, sess, self._client, chat_id)
                except: pass
                await asyncio.sleep(CHECK_INTERVAL)
            self._sessions.pop(uid, None)

else:
    # Упрощенная регистрация для Heroku Loader вне Hikka
    def register(client):
        # ... (код для Heroku аналогичен, просто вешается на события TelegramClient)
        pass
