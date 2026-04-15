# meta developer: @Kilka_Young
# meta banner: https://postimg.cc/D8pJMQ9S

"""
████████╗███████╗███╗   ███╗██████╗ ███╗   ███╗ █████╗ ██╗██╗     
╚══██╔══╝██╔════╝████╗ ████║██╔══██╗████╗ ████║██╔══██╗██║██║     
   ██║   █████╗  ██╔████╔██║██████╔╝██╔████╔██║███████║██║██║     
   ██║   ██╔══╝  ██║╚██╔╝██║██╔═══╝ ██║╚██╔╝██║██╔══██║██║██║     
   ██║   ███████╗██║ ╚═╝ ██║██║     ██║ ╚═╝ ██║██║  ██║██║███████╗
   ╚═╝   ╚══════╝╚═╝     ╚═╝╚═╝     ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝╚══════╝

TempMail Module for Hikka Userbot
Created by @Kilka_Young
"""

import asyncio
import aiohttp
import random
import string
import re
import logging
from datetime import datetime
from typing import Optional

from .. import loader, utils

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════

MAIL_API        = "https://api.mail.tm"
EMAIL_LIFETIME  = 10 * 60   # 10 минут
NEW_EMAIL_CD    = 30        # кулдаун создания
EXTEND_MINUTES  = 10
POLL_INTERVAL   = 15        # секунды между проверкой почты
BANNER          = "https://postimg.cc/D8pJMQ9S"

# ── Premium emoji IDs ──
def pe(eid: str, fb: str = "✨") -> str:
    return f'<tg-emoji emoji-id="{eid}">{fb}</tg-emoji>'

PE_MAIL    = pe("6082468779776809582", "📬")
PE_PERSON  = pe("6082512605623098578", "👤")
PE_ARROW   = pe("6082228441996860957", "➡️")
PE_BULB    = pe("6082473581550246236", "💡")
PE_TRASH   = pe("6082184272553189481", "🗑")
PE_STAR    = pe("6082441824562061129", "⭐")
PE_CROSS   = pe("6080368394740178132", "✖️")
PE_OK      = pe("5870633910337015697", "✅")
PE_WARN    = pe("5983150113483134607", "⚠️")
PE_CLOCK   = pe("5879915471817479359", "⏰")
PE_CODE    = pe("5870657884844462243", "💻")
PE_ROCKET  = pe("5870921681735781843", "🚀")
PE_CROWN   = pe("5870982283724328568", "👑")
PE_FILES   = pe("6082403659482668235", "📄")
PE_LOUD    = pe("6039422865189638057", "📢")
PE_AUTO    = pe("5345906554510012647", "🔄")
PE_LOCK    = pe("5379748234830756259", "🔒")
PE_UNLOCK  = pe("5379751603499491805", "🔓")
PE_REPLY   = pe("5440539497383087970", "💬")

AUTHOR = "@Kilka_Young"


# ═══════════════════════════════════════════════
#  MAIL.TM HELPERS
# ═══════════════════════════════════════════════

def rand_str(n: int = 10) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


async def get_domain() -> Optional[str]:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                f"{MAIL_API}/domains",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                if r.status == 200:
                    data = await r.json()
                    members = data.get("hydra:member", [])
                    return members[0]["domain"] if members else None
    except Exception:
        pass
    return None


async def create_email() -> Optional[dict]:
    domain = await get_domain()
    if not domain:
        return None
    address  = f"{rand_str(10)}@{domain}"
    password = rand_str(16)
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                f"{MAIL_API}/accounts",
                json={"address": address, "password": password},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                if r.status not in (200, 201):
                    return None
            async with s.post(
                f"{MAIL_API}/token",
                json={"address": address, "password": password},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                if r.status != 200:
                    return None
                td = await r.json()
                return {
                    "address":  address,
                    "password": password,
                    "token":    td.get("token"),
                }
    except Exception:
        return None


async def get_messages(token: str) -> list:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                f"{MAIL_API}/messages",
                headers={"Authorization": f"Bearer {token}"},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                if r.status == 200:
                    return (await r.json()).get("hydra:member", [])
    except Exception:
        pass
    return []


async def get_message_content(token: str, msg_id: str) -> Optional[dict]:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                f"{MAIL_API}/messages/{msg_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                if r.status == 200:
                    return await r.json()
    except Exception:
        pass
    return None


# ═══════════════════════════════════════════════
#  TEXT HELPERS
# ═══════════════════════════════════════════════

def progress_bar(left: float, total: float = EMAIL_LIFETIME, length: int = 15) -> str:
    pct    = max(0.0, min(1.0, left / total))
    filled = int(pct * length)
    bar    = "█" * filled + "░" * (length - filled)
    m, s   = divmod(int(left), 60)
    return f"{bar}  {m}:{s:02d}"


def highlight_codes(text: str) -> str:
    text = re.sub(
        r'(?<!\d)(\d{4,8})(?!\d)',
        lambda m: f"<code>{m.group(1)}</code>",
        text,
    )
    text = re.sub(
        r'\b([A-Za-z0-9]{6,32})\b',
        lambda m: (
            f"<code>{m.group(1)}</code>"
            if re.search(r'[A-Za-z]', m.group(1)) and re.search(r'\d', m.group(1))
            else m.group(0)
        ),
        text,
    )
    return text


def escape_html(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def footer() -> str:
    return f"\n\n{PE_CROWN} Создано {AUTHOR}"


# ═══════════════════════════════════════════════
#  MODULE
# ═══════════════════════════════════════════════

@loader.tds
class TempMailMod(loader.Module):
    """
    📬 Временные почты на 10 минут прямо в Hikka.
    Автопроверка входящих, авто-ответ другим пользователям.
    Создано @Kilka_Young
    """

    strings = {
        "name": "TempMail",

        # ── статусы ──
        "no_email":      f"{PE_WARN} <b>Нет активной почты.</b> Используй <code>.newmail</code>",
        "expired":       f"{PE_WARN} <b>Почта истекла.</b> Создай новую: <code>.newmail</code>",
        "creating":      f"{PE_ROCKET} <b>Создаю почту…</b>",
        "create_err":    f"{PE_CROSS} <b>Ошибка создания почты.</b> Попробуй позже.",
        "cooldown":      f"{PE_CLOCK} <b>Подожди {{sec}} сек.</b> перед созданием новой почты.",
        "deleted":       f"{PE_TRASH} <b>Почта удалена.</b>",
        "extended":      f"{PE_BULB} <b>+{{m}} минут добавлено!</b>",
        "ar_on":         f"{PE_UNLOCK} <b>Авто-ответ включён.</b>",
        "ar_off":        f"{PE_LOCK} <b>Авто-ответ отключён.</b>",
        "ar_set":        f"{PE_OK} <b>Текст авто-ответа установлен.</b>",
        "checking":      f"{PE_AUTO} <b>Проверяю почту…</b>",
        "no_letters":    f"{PE_MAIL} <b>Входящих нет.</b>",
        "poll_on":       f"{PE_OK} <b>Авто-мониторинг почты запущен.</b>",
        "poll_off":      f"{PE_WARN} <b>Авто-мониторинг остановлен.</b>",
    }

    # ── жизненный цикл ──────────────────────────────

    async def client_ready(self, client, db):
        self._client  = client
        self._db      = db
        self._me      = await client.get_me()

        # текущая почта
        self._email:      Optional[str]   = db.get("TempMail", "email",      None)
        self._password:   Optional[str]   = db.get("TempMail", "password",   None)
        self._token:      Optional[str]   = db.get("TempMail", "token",      None)
        self._expires_at: float           = db.get("TempMail", "expires_at", 0.0)
        self._created_at: float           = db.get("TempMail", "created_at", 0.0)
        self._last_cd:    float           = db.get("TempMail", "last_cd",    0.0)

        # авто-ответ
        self._ar_enabled: bool            = db.get("TempMail", "ar_enabled", False)
        self._ar_text:    str             = db.get("TempMail", "ar_text",
            f"{PE_MAIL} Привет! Сейчас меня нет. Создано {AUTHOR}")

        # уже обработанные письма
        seen_raw = db.get("TempMail", "seen_ids", [])
        self._seen_ids: set = set(seen_raw) if isinstance(seen_raw, list) else set()

        # мониторинг
        self._poll_enabled: bool = db.get("TempMail", "poll_enabled", True)
        self._poll_task: Optional[asyncio.Task] = None

        if self._poll_enabled:
            self._poll_task = asyncio.create_task(self._mail_poll_loop())

        logger.info("[TempMail] ready | poll=%s | ar=%s", self._poll_enabled, self._ar_enabled)

    # ── сохранение состояния ──────────────────────────

    def _save(self):
        d = self._db
        d.set("TempMail", "email",        self._email)
        d.set("TempMail", "password",     self._password)
        d.set("TempMail", "token",        self._token)
        d.set("TempMail", "expires_at",   self._expires_at)
        d.set("TempMail", "created_at",   self._created_at)
        d.set("TempMail", "last_cd",      self._last_cd)
        d.set("TempMail", "ar_enabled",   self._ar_enabled)
        d.set("TempMail", "ar_text",      self._ar_text)
        d.set("TempMail", "seen_ids",     list(self._seen_ids)[-500:])
        d.set("TempMail", "poll_enabled", self._poll_enabled)

    def _clear_email(self):
        self._email = self._password = self._token = None
        self._expires_at = self._created_at = 0.0
        self._seen_ids.clear()
        self._save()

    def _is_alive(self) -> bool:
        return bool(self._email) and datetime.now().timestamp() < self._expires_at

    # ════════════════════════════════════════════════
    #  КОМАНДЫ
    # ════════════════════════════════════════════════

    # ── .newmail ─────────────────────────────────────
    @loader.command(ru_doc="Создать новую временную почту на 10 минут")
    async def newmailcmd(self, message):
        """Создать новую временную почту на 10 минут"""
        now = datetime.now().timestamp()
        wait = NEW_EMAIL_CD - (now - self._last_cd)
        if wait > 0:
            await utils.answer(
                message,
                self.strings["cooldown"].format(sec=int(wait)) + footer()
            )
            return

        await utils.answer(message, self.strings["creating"] + footer())

        result = await create_email()
        if not result:
            await utils.answer(message, self.strings["create_err"] + footer())
            return

        now               = datetime.now().timestamp()
        self._email       = result["address"]
        self._password    = result["password"]
        self._token       = result["token"]
        self._expires_at  = now + EMAIL_LIFETIME
        self._created_at  = now
        self._last_cd     = now
        self._seen_ids.clear()
        self._save()

        bar        = progress_bar(EMAIL_LIFETIME)
        expire_str = datetime.fromtimestamp(self._expires_at).strftime("%H:%M:%S")

        text = (
            f"{PE_MAIL} <b>Временная почта создана!</b>\n\n"
            f"{PE_PERSON} <b>Адрес:</b>\n"
            f"<code>{self._email}</code>\n\n"
            f"{PE_STAR} {bar}\n"
            f"{PE_CLOCK} Действует до: <b>{expire_str}</b>\n\n"
            f"{PE_ARROW} <i>Письма придут автоматически</i>\n"
            f"{PE_OK} <i>Нажми на адрес чтобы скопировать</i>"
            + footer()
        )
        await utils.answer(message, text)

    # ── .mymail ───────────────────────────────────────
    @loader.command(ru_doc="Показать текущую почту и оставшееся время")
    async def mymailcmd(self, message):
        """Показать текущую почту и оставшееся время"""
        if not self._email:
            await utils.answer(message, self.strings["no_email"] + footer())
            return

        now = datetime.now().timestamp()
        if not self._is_alive():
            self._clear_email()
            await utils.answer(message, self.strings["expired"] + footer())
            return

        left       = self._expires_at - now
        bar        = progress_bar(left)
        expire_str = datetime.fromtimestamp(self._expires_at).strftime("%H:%M:%S")
        m, s       = divmod(int(left), 60)

        text = (
            f"{PE_MAIL} <b>Твоя временная почта</b>\n\n"
            f"{PE_PERSON} <b>Адрес:</b>\n"
            f"<code>{self._email}</code>\n\n"
            f"{PE_STAR} {bar}\n"
            f"{PE_CLOCK} До удаления: <b>{m}:{s:02d}</b>\n"
            f"Удалится в: <b>{expire_str}</b>\n\n"
            f"{PE_ARROW} <i>Нажми на адрес чтобы скопировать</i>"
            + footer()
        )
        await utils.answer(message, text)

    # ── .checkmail ────────────────────────────────────
    @loader.command(ru_doc="Проверить входящие письма вручную")
    async def checkmailcmd(self, message):
        """Проверить входящие письма вручную"""
        if not self._is_alive():
            self._clear_email()
            await utils.answer(
                message,
                self.strings["no_email" if not self._email else "expired"] + footer()
            )
            return

        await utils.answer(message, self.strings["checking"] + footer())

        msgs = await get_messages(self._token)
        if not msgs:
            await utils.answer(message, self.strings["no_letters"] + footer())
            return

        text_parts = [
            f"{PE_MAIL} <b>Входящие ({len(msgs)} шт.)</b>\n"
            + footer() + "\n"
        ]
        for idx, msg in enumerate(msgs[:10], 1):
            sender  = msg.get("from", {}).get("address", "???")
            subject = msg.get("subject", "(без темы)")
            text_parts.append(
                f"{PE_FILES} <b>#{idx}</b> От: <code>{sender}</code>\n"
                f"   Тема: <i>{escape_html(subject)}</i>"
            )
        await utils.answer(message, "\n".join(text_parts))

    # ── .readmail ─────────────────────────────────────
    @loader.command(ru_doc="Прочитать письмо: .readmail <номер> (из .checkmail)")
    async def readmailcmd(self, message):
        """Прочитать письмо: .readmail <номер>"""
        if not self._is_alive():
            self._clear_email()
            await utils.answer(message, self.strings["no_email"] + footer())
            return

        args = utils.get_args_raw(message).strip()
        if not args.isdigit():
            await utils.answer(
                message,
                f"{PE_WARN} Укажи номер письма: <code>.readmail 1</code>" + footer()
            )
            return

        idx  = int(args) - 1
        msgs = await get_messages(self._token)
        if not msgs or idx < 0 or idx >= len(msgs):
            await utils.answer(message, f"{PE_WARN} Письмо не найдено." + footer())
            return

        msg    = msgs[idx]
        msg_id = msg.get("id", "")
        full   = await get_message_content(self._token, msg_id)
        src    = full or msg

        sender  = (src.get("from") or {}).get("address", "???")
        subject = src.get("subject", "(без темы)")

        raw_date = src.get("createdAt", "")
        try:
            dt       = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            date_str = dt.strftime("%d.%m.%Y %H:%M:%S")
        except Exception:
            date_str = raw_date or "—"

        body = ""
        if full:
            body = full.get("text", "") or ""
            if not body:
                html_b = full.get("html", [""])[0] if isinstance(full.get("html"), list) else full.get("html", "")
                body   = re.sub(r"<[^>]+>", " ", html_b or "")
                body   = re.sub(r"\s+", " ", body).strip()
        body = (body.strip()[:3000] or "(тело письма пусто)")

        body_safe  = escape_html(body)
        body_final = highlight_codes(body_safe)

        text = (
            f"{PE_MAIL} <b>Письмо #{idx + 1}</b>\n\n"
            f"{PE_PERSON} <b>На почту:</b> <code>{self._email}</code>\n"
            f"{PE_ARROW} <b>От:</b> <code>{sender}</code>\n"
            f"{pe('5890937706803894250', '🗓')} <b>Дата:</b> {date_str}\n"
            f"{pe('5870676941614354370', '📝')} <b>Тема:</b> {escape_html(subject)}\n\n"
            f"<blockquote expandable>{body_final}</blockquote>"
            + footer()
        )
        await utils.answer(message, text)

    # ── .delmail ──────────────────────────────────────
    @loader.command(ru_doc="Удалить текущую временную почту")
    async def delmailcmd(self, message):
        """Удалить текущую временную почту"""
        if not self._email:
            await utils.answer(message, self.strings["no_email"] + footer())
            return
        self._clear_email()
        await utils.answer(message, self.strings["deleted"] + footer())

    # ── .extmail ──────────────────────────────────────
    @loader.command(ru_doc="Продлить почту на 10 минут")
    async def extmailcmd(self, message):
        """Продлить почту на 10 минут"""
        if not self._is_alive():
            self._clear_email()
            await utils.answer(message, self.strings["no_email"] + footer())
            return

        now             = datetime.now().timestamp()
        self._expires_at = max(self._expires_at, now) + EXTEND_MINUTES * 60
        self._save()

        left       = self._expires_at - now
        bar        = progress_bar(left)
        expire_str = datetime.fromtimestamp(self._expires_at).strftime("%H:%M:%S")

        text = (
            f"{PE_BULB} <b>+{EXTEND_MINUTES} минут добавлено!</b>\n\n"
            f"{PE_STAR} {bar}\n"
            f"{PE_CLOCK} Новое время: <b>{expire_str}</b>\n\n"
            f"{PE_PERSON} <code>{self._email}</code>"
            + footer()
        )
        await utils.answer(message, text)

    # ── .aron / .aroff ────────────────────────────────
    @loader.command(ru_doc="Включить авто-ответ на входящие сообщения (реплай)")
    async def aroncmd(self, message):
        """Включить авто-ответ на чужие сообщения (reply)"""
        self._ar_enabled = True
        self._save()
        await utils.answer(
            message,
            self.strings["ar_on"]
            + f"\n{PE_REPLY} Текст: <i>{escape_html(self._ar_text)}</i>"
            + footer()
        )

    @loader.command(ru_doc="Отключить авто-ответ")
    async def aroffcmd(self, message):
        """Отключить авто-ответ"""
        self._ar_enabled = False
        self._save()
        await utils.answer(message, self.strings["ar_off"] + footer())

    # ── .artext ───────────────────────────────────────
    @loader.command(ru_doc="Задать текст авто-ответа: .artext <текст>")
    async def artextcmd(self, message):
        """Задать текст авто-ответа: .artext <текст>"""
        text = utils.get_args_raw(message).strip()
        if not text:
            await utils.answer(
                message,
                f"{PE_WARN} Укажи текст: <code>.artext Привет!</code>" + footer()
            )
            return
        self._ar_text = text
        self._save()
        await utils.answer(
            message,
            self.strings["ar_set"]
            + f"\n{PE_REPLY} Новый текст: <i>{escape_html(text)}</i>"
            + footer()
        )

    # ── .pollon / .polloff ────────────────────────────
    @loader.command(ru_doc="Запустить авто-мониторинг входящих писем")
    async def polloncmd(self, message):
        """Запустить авто-мониторинг входящих писем"""
        self._poll_enabled = True
        self._save()
        if self._poll_task is None or self._poll_task.done():
            self._poll_task = asyncio.create_task(self._mail_poll_loop())
        await utils.answer(message, self.strings["poll_on"] + footer())

    @loader.command(ru_doc="Остановить авто-мониторинг входящих писем")
    async def polloffcmd(self, message):
        """Остановить авто-мониторинг"""
        self._poll_enabled = False
        self._save()
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
        await utils.answer(message, self.strings["poll_off"] + footer())

    # ── .mailhelp ─────────────────────────────────────
    @loader.command(ru_doc="Список всех команд модуля TempMail")
    async def mailhelpcmd(self, message):
        """Список всех команд модуля"""
        text = (
            f"{PE_CROWN} <b>TempMail — команды</b>\n"
            f"{PE_ROCKET} Создано <b>{AUTHOR}</b>\n\n"

            f"{PE_MAIL} <code>.newmail</code> — создать почту на 10 мин\n"
            f"{PE_PERSON} <code>.mymail</code> — показать текущую почту\n"
            f"{PE_FILES} <code>.checkmail</code> — список входящих\n"
            f"{PE_ARROW} <code>.readmail 1</code> — прочитать письмо №1\n"
            f"{PE_BULB} <code>.extmail</code> — +10 мин к времени почты\n"
            f"{PE_TRASH} <code>.delmail</code> — удалить почту\n\n"

            f"{PE_OK} <code>.pollon</code> — вкл авто-мониторинг писем\n"
            f"{PE_WARN} <code>.polloff</code> — выкл авто-мониторинг\n\n"

            f"{PE_UNLOCK} <code>.aron</code> — вкл авто-ответ\n"
            f"{PE_LOCK} <code>.aroff</code> — выкл авто-ответ\n"
            f"{PE_REPLY} <code>.artext текст</code> — задать текст ответа\n\n"

            f"{PE_STAR} <code>.mailhelp</code> — эта справка\n"
            + footer()
        )
        await utils.answer(message, text)

    # ════════════════════════════════════════════════
    #  АВТО-ОТВЕТ (watcher)
    # ════════════════════════════════════════════════

    async def watcher(self, message):
        """Автоматически отвечает другим пользователям, если включён авто-ответ."""
        if not self._ar_enabled:
            return

        # Только чужие сообщения, адресованные мне (reply на моё или упоминание)
        try:
            me_id = self._me.id

            # Игнорируем свои сообщения
            if message.sender_id == me_id:
                return

            # Реагируем только если это reply на моё сообщение
            reply = await message.get_reply_message()
            if reply is None or reply.sender_id != me_id:
                return

            text = (
                f"{PE_REPLY} <b>Авто-ответ</b>\n\n"
                f"{self._ar_text}"
                + footer()
            )
            await message.reply(text, parse_mode="html")
        except Exception as e:
            logger.debug("[TempMail] watcher error: %s", e)

    # ════════════════════════════════════════════════
    #  АВТО-МОНИТОРИНГ ПОЧТЫ
    # ════════════════════════════════════════════════

    async def _mail_poll_loop(self):
        while self._poll_enabled:
            await asyncio.sleep(POLL_INTERVAL)
            try:
                await self._poll_once()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("[TempMail] poll error: %s", e)

    async def _poll_once(self):
        if not self._is_alive():
            if self._email:
                self._clear_email()
                await self._client.send_message(
                    "me",
                    f"{PE_WARN} <b>Почта истекла и удалена.</b>\n"
                    f"Создай новую: <code>.newmail</code>"
                    + footer(),
                    parse_mode="html"
                )
            return

        msgs = await get_messages(self._token)
        for msg in msgs:
            msg_id = msg.get("id")
            if not msg_id or msg_id in self._seen_ids:
                continue

            self._seen_ids.add(msg_id)
            self._save()

            # Полное содержимое
            try:
                full = await get_message_content(self._token, msg_id)
            except Exception:
                full = None

            sender  = msg.get("from", {}).get("address", "???")
            subject = msg.get("subject", "(без темы)")
            raw_date = msg.get("createdAt", "")
            try:
                dt       = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                date_str = dt.strftime("%d.%m.%Y %H:%M:%S")
            except Exception:
                date_str = raw_date or "—"

            body = ""
            if full:
                body = full.get("text", "") or ""
                if not body:
                    html_b = full.get("html", [""])[0] if isinstance(full.get("html"), list) else full.get("html", "")
                    body   = re.sub(r"<[^>]+>", " ", html_b or "")
                    body   = re.sub(r"\s+", " ", body).strip()
            body = body.strip()[:3000] or "(тело письма пусто)"

            body_safe  = escape_html(body)
            body_final = highlight_codes(body_safe)

            text = (
                f"{PE_MAIL} <b>Новое письмо!</b>\n\n"
                f"{PE_PERSON} <b>На почту:</b> <code>{self._email}</code>\n"
                f"{PE_ARROW} <b>От:</b> <code>{sender}</code>\n"
                f"{pe('5890937706803894250', '🗓')} <b>Дата:</b> {date_str}\n"
                f"{pe('5870676941614354370', '📝')} <b>Тема:</b> {escape_html(subject)}\n\n"
                f"<blockquote expandable>{body_final}</blockquote>"
                + footer()
            )

            await self._client.send_message(
                "me",
                text,
                parse_mode="html"
            )
