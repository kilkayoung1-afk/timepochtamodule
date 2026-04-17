# tempmail.py — Модуль временной почты для Hikka / Heroku Loader
# Использует 1secmail.com API (без регистрации, бесплатно)
# Автор: сгенерировано под Python 3.10+

import asyncio
import random
import string
import logging
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
        self.seen_ids: set[int] = set()     # уже показанные ID писем
        self.msg_id: int | None = None      # ID сообщения-статуса в чате
        self.task: asyncio.Task | None = None

    @property
    def remaining(self) -> int:
        """Оставшихся секунд до смерти почты."""
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
    """Генерирует случайный логин из букв и цифр."""
    chars = string.ascii_lowercase + string.digits
    return "".join(random.choices(chars, k=length))


async def _get_messages(session: aiohttp.ClientSession, login: str, domain: str) -> list[dict]:
    """Получить список писем для данного ящика."""
    url = f"{API_BASE}?action=getMessages&login={login}&domain={domain}"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status == 200:
                return await r.json()
    except Exception as e:
        logger.warning(f"[TempMail] getMessages error: {e}")
    return []


async def _read_message(session: aiohttp.ClientSession, login: str, domain: str, msg_id: int) -> dict | None:
    """Получить полное тело письма по ID."""
    url = f"{API_BASE}?action=readMessage&login={login}&domain={domain}&id={msg_id}"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status == 200:
                return await r.json()
    except Exception as e:
        logger.warning(f"[TempMail] readMessage error: {e}")
    return None


def _format_mail_status(sess: MailSession) -> str:
    """Красивое сообщение со статусом почты."""
    return (
        "📧 <b>Ваша временная почта:</b>\n"
        f"<code>{sess.email}</code>\n\n"
        f"⏳ <b>Осталось:</b> {sess.fmt_remaining()}\n"
        "💡 <i>Письма появятся автоматически</i>"
    )


def _format_letter(msg: dict) -> str:
    """Форматирование одного входящего письма."""
    sender  = msg.get("from", "—")
    subject = msg.get("subject", "(без темы)")
    body    = (msg.get("body") or msg.get("textBody") or msg.get("htmlBody") or "").strip()

    # Убираем лишний HTML если он проскочил
    import re
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
# Основной класс модуля — Hikka-совместимый формат
# ─────────────────────────────────────────────────────────────────────────────
if HIKKA:
    @loader.module(name="TempMail", author="generated", version=(1, 0, 0))
    class TempMailMod(loader.Module):
        """Модуль временной почты через 1secmail.com"""

        strings = {"name": "TempMail"}

        def __init__(self):
            self._sessions: dict[int, MailSession] = {}  # user_id → MailSession
            self._http: aiohttp.ClientSession | None = None

        async def client_ready(self, client, db):
            self._client = client
            self._http   = aiohttp.ClientSession()

        # ── .mail ──────────────────────────────────────────────────────────
        @loader.command()
        async def mailcmd(self, message: Message):
            """.mail — создать временный email"""
            uid = message.sender_id

            # Не создаём вторую почту если уже есть живая
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

        # ── .mailnew ───────────────────────────────────────────────────────
        @loader.command()
        async def mailnewcmd(self, message: Message):
            """.mailnew — удалить текущую и создать новую почту"""
            uid = message.sender_id
            await self._stop_session(uid)
            await self._create_mail(message, uid)

        # ── .mailoff ───────────────────────────────────────────────────────
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

        # ── Внутренние методы ──────────────────────────────────────────────
        async def _create_mail(self, message: Message, uid: int):
            login  = _random_login()
            domain = random.choice(DOMAINS)
            sess   = MailSession(login, domain)

            status_msg = await utils.answer(message, _format_mail_status(sess))
            # utils.answer может вернуть Message или список — берём первый
            if isinstance(status_msg, (list, tuple)):
                status_msg = status_msg[0]
            sess.msg_id = status_msg.id

            self._sessions[uid] = sess

            # Запускаем фоновый воркер
            sess.task = asyncio.ensure_future(
                self._worker(uid, message.chat_id, status_msg)
            )
            logger.info(f"[TempMail] Created {sess.email} for uid={uid}")

        async def _stop_session(self, uid: int):
            if uid in self._sessions:
                sess = self._sessions.pop(uid)
                if sess.task and not sess.task.done():
                    sess.task.cancel()
                logger.info(f"[TempMail] Stopped session {sess.email}")

        async def _worker(self, uid: int, chat_id: int, status_msg: Message):
            """Фоновый цикл: обновляет таймер + доставляет письма."""
            sess = self._sessions.get(uid)
            if not sess:
                return

            try:
                while sess.is_alive:
                    # 1. Обновляем таймер в статусном сообщении
                    try:
                        await self._client.edit_message(
                            chat_id, sess.msg_id, _format_mail_status(sess),
                            parse_mode="html"
                        )
                    except Exception:
                        pass  # сообщение могло быть удалено — не критично

                    # 2. Проверяем новые письма
                    if self._http:
                        letters = await _get_messages(self._http, sess.login, sess.domain)
                        for letter in letters:
                            lid = letter.get("id")
                            if lid and lid not in sess.seen_ids:
                                sess.seen_ids.add(lid)
                                full = await _read_message(
                                    self._http, sess.login, sess.domain, lid
                                )
                                if full:
                                    try:
                                        await self._client.send_message(
                                            chat_id,
                                            _format_letter(full),
                                            parse_mode="html"
                                        )
                                    except Exception as e:
                                        logger.warning(f"[TempMail] send letter error: {e}")

                    await asyncio.sleep(CHECK_INTERVAL)

                # ── Почта истекла ──────────────────────────────────────────
                try:
                    await self._client.send_message(
                        chat_id,
                        f"⏰ <b>Почта истекла!</b>\n"
                        f"<code>{sess.email}</code> больше не принимает письма.\n"
                        "Создайте новую: <code>.mail</code>",
                        parse_mode="html"
                    )
                except Exception:
                    pass

            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"[TempMail] worker crash: {e}", exc_info=True)
            finally:
                self._sessions.pop(uid, None)


# ─────────────────────────────────────────────────────────────────────────────
# Heroku Loader / standalone-режим (если не Hikka)
# ─────────────────────────────────────────────────────────────────────────────
else:
    import re
    from telethon import events

    # ── Глобальное состояние ─────────────────────────────────────────────
    _sessions: dict[int, MailSession] = {}
    _http_session: aiohttp.ClientSession | None = None
    _client_ref: TelegramClient | None = None

    def register(client: TelegramClient):
        """Вызывается Heroku Loader'ом для регистрации модуля."""
        global _client_ref, _http_session
        _client_ref   = client
        _http_session = aiohttp.ClientSession()

        @client.on(events.NewMessage(pattern=r"^[./]mail$", outgoing=True))
        async def cmd_mail(event):
            uid = event.sender_id
            if uid in _sessions and _sessions[uid].is_alive:
                sess = _sessions[uid]
                await event.edit(
                    f"⚠️ **Уже есть активная почта:**\n`{sess.email}`\n"
                    f"⏳ Осталось: {sess.fmt_remaining()}\n\n"
                    "Используй `.mailnew` чтобы заменить."
                )
                return
            await _create_mail(event, uid)

        @client.on(events.NewMessage(pattern=r"^[./]mailnew$", outgoing=True))
        async def cmd_mailnew(event):
            uid = event.sender_id
            await _stop_session(uid)
            await _create_mail(event, uid)

        @client.on(events.NewMessage(pattern=r"^[./]mailoff$", outgoing=True))
        async def cmd_mailoff(event):
            uid = event.sender_id
            if uid not in _sessions:
                await event.edit("❌ Нет активной почты.")
                return
            email = _sessions[uid].email
            await _stop_session(uid)
            await event.edit(f"🗑 Почта `{email}` удалена.")

        logger.info("[TempMail] Heroku-mode registered (.mail / .mailnew / .mailoff)")

    # ── Вспомогательные функции (Heroku-режим) ───────────────────────────
    async def _create_mail(event, uid: int):
        login  = _random_login()
        domain = random.choice(DOMAINS)
        sess   = MailSession(login, domain)

        sent = await event.edit(_format_mail_status(sess))
        sess.msg_id = sent.id
        _sessions[uid] = sess

        sess.task = asyncio.ensure_future(_worker(uid, event.chat_id, sent))
        logger.info(f"[TempMail] Created {sess.email} for uid={uid}")

    async def _stop_session(uid: int):
        if uid in _sessions:
            sess = _sessions.pop(uid)
            if sess.task and not sess.task.done():
                sess.task.cancel()

    async def _worker(uid: int, chat_id: int, status_msg):
        sess = _sessions.get(uid)
        if not sess or not _client_ref:
            return

        try:
            while sess.is_alive:
                # Обновляем таймер
                try:
                    await _client_ref.edit_message(
                        chat_id, sess.msg_id,
                        _format_mail_status(sess),
                        parse_mode="html"
                    )
                except Exception:
                    pass

                # Проверяем письма
                if _http_session:
                    letters = await _get_messages(_http_session, sess.login, sess.domain)
                    for letter in letters:
                        lid = letter.get("id")
                        if lid and lid not in sess.seen_ids:
                            sess.seen_ids.add(lid)
                            full = await _read_message(
                                _http_session, sess.login, sess.domain, lid
                            )
                            if full:
                                try:
                                    await _client_ref.send_message(
                                        chat_id,
                                        _format_letter(full),
                                        parse_mode="html"
                                    )
                                except Exception as e:
                                    logger.warning(f"[TempMail] letter send error: {e}")

                await asyncio.sleep(CHECK_INTERVAL)

            # Почта истекла
            try:
                await _client_ref.send_message(
                    chat_id,
                    f"⏰ <b>Почта истекла!</b>\n"
                    f"<code>{sess.email}</code> больше не принимает письма.\n"
                    "Создай новую: <code>.mail</code>",
                    parse_mode="html"
                )
            except Exception:
                pass

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[TempMail] worker crash: {e}", exc_info=True)
        finally:
            _sessions.pop(uid, None)
