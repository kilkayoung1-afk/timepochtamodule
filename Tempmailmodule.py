# tempmail.py — Модуль временной почты для Hikka / Heroku Loader
# Использует 1secmail.com API (без регистрации, бесплатно)
# Автор: сгенерировано (исправлено для Python 3.10+)

import asyncio
import random
import string
import logging
import re
from datetime import datetime, timedelta

import aiohttp
from telethon import TelegramClient
from telethon.tl.types import Message

# ─── Совместимость с Hikka / Heroku Loader ───────────────────────────────────
try:
    from .. import loader, utils  # Hikka
    HIKKA = True
except ImportError:
    HIKKA = False

logger = logging.getLogger(__name__)

# ─── Константы ────────────────────────────────────────────────────────────────
API_BASE      = "https://www.1secmail.com/api/v1/"
MAIL_LIFETIME = 600          # 10 минут в секундах
CHECK_INTERVAL = 8           # проверять почту каждые 8 сек
DOMAINS = [                  # доступные домены 1secmail
    "1secmail.com",
    "1secmail.net",
    "1secmail.org",
    "wwjmp.com",
    "esiix.com",
]

# ─────────────────────────────────────────────────────────────────────────────
# Класс состояния одной сессии почты
# ─────────────────────────────────────────────────────────────────────────────
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
# Вспомогательные функции API
# ─────────────────────────────────────────────────────────────────────────────
def _random_login(length: int = 10) -> str:
    chars = string.ascii_lowercase + string.digits
    return "".join(random.choices(chars, k=length))

async def _get_messages(session: aiohttp.ClientSession, login: str, domain: str) -> list[dict]:
    url = f"{API_BASE}?action=getMessages&login={login}&domain={domain}"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status == 200:
                return await r.json()
    except Exception as e:
        logger.warning(f"[TempMail] getMessages error: {e}")
    return []

async def _read_message(session: aiohttp.ClientSession, login: str, domain: str, msg_id: int) -> dict | None:
    url = f"{API_BASE}?action=readMessage&login={login}&domain={domain}&id={msg_id}"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status == 200:
                return await r.json()
    except Exception as e:
        logger.warning(f"[TempMail] readMessage error: {e}")
    return None

def _format_mail_status(sess: MailSession) -> str:
    return (
        "📧 <b>Ваша временная почта:</b>\n"
        f"<code>{sess.email}</code>\n\n"
        f"⏳ <b>Осталось:</b> {sess.fmt_remaining()}\n"
        "💡 <i>Письма появятся автоматически</i>"
    )

def _format_letter(msg: dict) -> str:
    sender  = msg.get("from", "—")
    subject = msg.get("subject", "(без темы)")
    body    = (msg.get("body") or msg.get("textBody") or msg.get("htmlBody") or "").strip()

    body = re.sub(r"<[^>]+>", "", body)
    body = body[:1200] + ("…" if len(body) > 1200 else "")

    return (
        "📨 <b>Новое письмо!</b>\n"
        "─────────────────\n"
        f"👤 <b>От:</b> {sender}\n"
        f"📌 <b>Тема:</b> {subject}\n\n"
        f"{body}"
    )

# ─────────────────────────────────────────────────────────────────────────────
# Основной класс модуля
# ─────────────────────────────────────────────────────────────────────────────
if HIKKA:
    @loader.tds
    class TempMailMod(loader.Module):
        """Модуль временной почты через 1secmail.com"""
        strings = {"name": "TempMail"}

        def __init__(self):
            self._sessions: dict[int, MailSession] = {}
            self._http: aiohttp.ClientSession | None = None

        async def client_ready(self, client, db):
            self._client = client
            self._http   = aiohttp.ClientSession()

        @loader.command()
        async def mailcmd(self, message: Message):
            """.mail — создать временный email"""
            uid = message.sender_id
            if uid in self._sessions and self._sessions[uid].is_alive:
                sess = self._sessions[uid]
                await utils.answer(
                    message,
                    f"⚠️ У вас уже есть активная почта:\n<code>{sess.email}</code>\n"
                    f"⏳ Осталось: {sess.fmt_remaining()}\n\n"
                    "Используйте <code>.mailnew</code> чтобы заменить её."
                )
                return
            await self._create_mail(message, uid)

        @loader.command()
        async def mailnewcmd(self, message: Message):
            """.mailnew — удалить текущую и создать новую почту"""
            uid = message.sender_id
            await self._stop_session(uid)
            await self._create_mail(message, uid)

        @loader.command()
        async def mailoffcmd(self, message: Message):
            """.mailoff — остановить отслеживание почты"""
            uid = message.sender_id
            if uid not in self._sessions:
                await utils.answer(message, "❌ Нет активной почты.")
                return
            email = self._sessions[uid].email
            await self._stop_session(uid)
            await utils.answer(message, f"🗑 Почта <code>{email}</code> удалена.")

        async def _create_mail(self, message: Message, uid: int):
            login  = _random_login()
            domain = random.choice(DOMAINS)
            sess   = MailSession(login, domain)
            status_msg = await utils.answer(message, _format_mail_status(sess))
            if isinstance(status_msg, (list, tuple)):
                status_msg = status_msg[0]
            sess.msg_id = status_msg.id
            self._sessions[uid] = sess
            sess.task = asyncio.ensure_future(self._worker(uid, message.chat_id))
            logger.info(f"[TempMail] Created {sess.email} for uid={uid}")

        async def _stop_session(self, uid: int):
            if uid in self._sessions:
                sess = self._sessions.pop(uid)
                if sess.task and not sess.task.done():
                    sess.task.cancel()

        async def _worker(self, uid: int, chat_id: int):
            sess = self._sessions.get(uid)
            if not sess: return
            try:
                while sess.is_alive:
                    try:
                        await self._client.edit_message(chat_id, sess.msg_id, _format_mail_status(sess))
                    except Exception: pass

                    if self._http:
                        letters = await _get_messages(self._http, sess.login, sess.domain)
                        for letter in letters:
                            lid = letter.get("id")
                            if lid and lid not in sess.seen_ids:
                                sess.seen_ids.add(lid)
                                full = await _read_message(self._http, sess.login, sess.domain, lid)
                                if full:
                                    try:
                                        await self._client.send_message(chat_id, _format_letter(full))
                                    except Exception as e:
                                        logger.warning(f"[TempMail] send error: {e}")
                    await asyncio.sleep(CHECK_INTERVAL)
                await self._client.send_message(chat_id, f"⏰ <b>Почта истекла!</b>\n<code>{sess.email}</code>")
            except asyncio.CancelledError: pass
            finally: self._sessions.pop(uid, None)

else:
    # Heroku Standalone mode
    from telethon import events
    _sessions: dict[int, MailSession] = {}
    _http_session: aiohttp.ClientSession | None = None
    _client_ref: TelegramClient | None = None

    def register(client: TelegramClient):
        global _client_ref, _http_session
        _client_ref = client
        _http_session = aiohttp.ClientSession()

        @client.on(events.NewMessage(pattern=r"^[./]mail$", outgoing=True))
        async def cmd_mail(event):
            uid = event.sender_id
            if uid in _sessions and _sessions[uid].is_alive:
                return await event.edit(f"⚠️ Активна: `{_sessions[uid].email}`")
            login, domain = _random_login(), random.choice(DOMAINS)
            sess = MailSession(login, domain)
            sent = await event.edit(_format_mail_status(sess))
            sess.msg_id, _sessions[uid] = sent.id, sess
            sess.task = asyncio.ensure_future(_worker(uid, event.chat_id))

        @client.on(events.NewMessage(pattern=r"^[./]mailoff$", outgoing=True))
        async def cmd_mailoff(event):
            uid = event.sender_id
            if uid in _sessions:
                sess = _sessions.pop(uid)
                if sess.task: sess.task.cancel()
                await event.edit(f"🗑 Удалено: `{sess.email}`")

    async def _worker(uid: int, chat_id: int):
        sess = _sessions.get(uid)
        while sess and sess.is_alive:
            try:
                await _client_ref.edit_message(chat_id, sess.msg_id, _format_mail_status(sess), parse_mode="html")
                if _http_session:
                    letters = await _get_messages(_http_session, sess.login, sess.domain)
                    for l in letters:
                        if l['id'] not in sess.seen_ids:
                            sess.seen_ids.add(l['id'])
                            full = await _read_message(_http_session, sess.login, sess.domain, l['id'])
                            if full: await _client_ref.send_message(chat_id, _format_letter(full), parse_mode="html")
            except: pass
            await asyncio.sleep(CHECK_INTERVAL)
        _sessions.pop(uid, None)
