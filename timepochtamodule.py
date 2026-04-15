# temp_mail_module.py
"""
Модуль временных почт для Heroku Userbot
Бесплатные почты на 10 минут с автоматической доставкой писем

Установка:
1. Скачай файл в папку modules/ твоего юзербота
2. Перезапусти бота командой .restart
3. Готово! Используй .mailhelp для списка команд

Создано @Kilka_Young
"""

import asyncio
import aiohttp
import aiosqlite
import random
import string
import os
import re
import logging
from datetime import datetime
from typing import Optional

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════
# КОНФИГУРАЦИЯ
# ══════════════════════════════════════════════════════════════

DB_PATH = "data/temp_emails.db"
MAIL_API = "https://api.mail.tm"
CHANNEL_URL = "https://t.me/mypigAI"
CHANNEL_USERNAME = "mypigAI"

EMAIL_LIFETIME = 10 * 60  # 10 минут
NEW_EMAIL_COOLDOWN = 30   # 30 секунд
CREATOR_TAG = "@Kilka_Young"

# Авто-ответ на сообщения
auto_reply_enabled = True

# Премиум эмодзи ID
PE_MAIL     = "5472146952816515593"   # 📧
PE_PERSON   = "6082512605623098578"   # 👤
PE_TIME     = "6082441824562061129"   # ⏱
PE_CHECK    = "5870633910337015697"   # ✅
PE_CROSS    = "5870657884844462243"   # ❌
PE_INBOX    = "6082468779776809582"   # 📥
PE_TRASH    = "6082184272553189481"   # 🗑
PE_BULB     = "6082473581550246236"   # 💡
PE_FIRE     = "5983150113483134607"   # 🔥
PE_CHART    = "5870921681735781843"   # 📊
PE_MEGAPH   = "6039422865189638057"   # 📣
PE_CLOCK    = "5890937706803894250"   # 🕐
PE_BOOK     = "5870676941614354370"   # 📖
PE_LOCK     = "5879770184122289761"   # 🔒
PE_STAR     = "5985015646509725811"   # ⭐

# ══════════════════════════════════════════════════════════════
# ПРОВЕРКА ПОДПИСКИ
# ══════════════════════════════════════════════════════════════

async def check_subscription(client, user_id: int) -> bool:
    """Проверка подписки на канал @mypigAI"""
    try:
        member = await client.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)
        return member.status not in ["left", "kicked"]
    except Exception as e:
        log.error(f"Subscription check error: {e}")
        return False


async def send_subscription_required(client, chat_id: int, is_reply: bool = False):
    """Отправить сообщение о необходимости подписки"""
    text = (
        f"{pe(PE_LOCK)} **Требуется подписка!**\n\n"
        f"{pe(PE_STAR)} Чтобы пользоваться модулем временных почт,\n"
        f"подпишись на наш канал:\n\n"
        f"👉 {CHANNEL_URL}\n\n"
        f"{pe(PE_BULB)} После подписки используй команды снова!\n\n"
        f"_Создано {CREATOR_TAG}_"
    )
    
    if is_reply:
        return text
    else:
        try:
            await client.send_message(chat_id, text)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════
# DATABASE
# ══════════════════════════════════════════════════════════════

async def init_db():
    os.makedirs("data", exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS emails (
                user_id     INTEGER PRIMARY KEY,
                email       TEXT,
                password    TEXT,
                token       TEXT,
                expires_at  REAL,
                created_at  REAL,
                last_created REAL DEFAULT 0
            )
        """)
        await db.commit()


async def get_email_data(user_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM emails WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def upsert_email(user_id: int, **kwargs):
    data = await get_email_data(user_id)
    if not data:
        await _insert_email(user_id, **kwargs)
    else:
        await _update_email(user_id, **kwargs)


async def _insert_email(user_id: int, **kwargs):
    kwargs["user_id"] = user_id
    cols = ", ".join(kwargs.keys())
    placeholders = ", ".join("?" * len(kwargs))
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"INSERT OR REPLACE INTO emails ({cols}) VALUES ({placeholders})",
            list(kwargs.values())
        )
        await db.commit()


async def _update_email(user_id: int, **kwargs):
    if not kwargs:
        return
    sets = ", ".join(f"{k}=?" for k in kwargs)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE emails SET {sets} WHERE user_id=?",
            list(kwargs.values()) + [user_id]
        )
        await db.commit()


async def clear_email_data(user_id: int):
    await _update_email(
        user_id,
        email=None,
        password=None,
        token=None,
        expires_at=None,
        created_at=None
    )


async def get_all_users() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM emails") as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]


async def count_active_emails() -> int:
    now = datetime.now().timestamp()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM emails WHERE email IS NOT NULL AND expires_at > ?",
            (now,)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


# ══════════════════════════════════════════════════════════════
# MAIL.TM API
# ══════════════════════════════════════════════════════════════

def rand_str(n=10) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


async def get_domain() -> Optional[str]:
    async with aiohttp.ClientSession() as s:
        try:
            async with s.get(f"{MAIL_API}/domains", timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    data = await r.json()
                    domains = data.get("hydra:member", [])
                    if domains:
                        return domains[0]["domain"]
        except Exception:
            pass
    return None


async def create_email() -> Optional[dict]:
    domain = await get_domain()
    if not domain:
        return None
    address = f"{rand_str(10)}@{domain}"
    password = rand_str(16)
    
    async with aiohttp.ClientSession() as s:
        try:
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
                token_data = await r.json()
                return {
                    "address": address,
                    "password": password,
                    "token": token_data.get("token")
                }
        except Exception:
            return None


async def get_messages(token: str) -> list:
    async with aiohttp.ClientSession() as s:
        try:
            async with s.get(
                f"{MAIL_API}/messages",
                headers={"Authorization": f"Bearer {token}"},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                if r.status == 200:
                    data = await r.json()
                    return data.get("hydra:member", [])
        except Exception:
            pass
    return []


async def get_message_content(token: str, msg_id: str) -> Optional[dict]:
    async with aiohttp.ClientSession() as s:
        try:
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


# ══════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════

def pe(emoji_id: str, fallback: str = "🔹") -> str:
    """Premium emoji tag"""
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


def progress_bar(seconds_left: float, total: float = EMAIL_LIFETIME, length: int = 15) -> str:
    pct = max(0.0, min(1.0, seconds_left / total))
    filled = int(pct * length)
    bar = "█" * filled + "░" * (length - filled)
    mins = int(seconds_left) // 60
    secs = int(seconds_left) % 60
    return f"{bar}  {mins}:{secs:02d}"


def highlight_codes(text: str) -> str:
    """Подсветка кодов верификации"""
    text = re.sub(
        r'(?<!\d)(\d{4,8})(?!\d)',
        lambda m: f"<code>{m.group(1)}</code>",
        text
    )
    text = re.sub(
        r'\b([A-Za-z0-9]{6,32})\b',
        lambda m: (
            f"<code>{m.group(1)}</code>"
            if re.search(r'[A-Za-z]', m.group(1)) and re.search(r'\d', m.group(1))
            else m.group(0)
        ),
        text
    )
    return text


def escape_html(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ══════════════════════════════════════════════════════════════
# ХРАНИЛИЩЕ
# ══════════════════════════════════════════════════════════════

seen_messages: dict = {}


# ══════════════════════════════════════════════════════════════
# КОМАНДЫ ДЛЯ ВЛАДЕЛЬЦА
# ══════════════════════════════════════════════════════════════

async def newemail_cmd(client, message):
    """Создать новую временную почту на 10 минут"""
    user_id = message.from_user.id
    
    # Проверка подписки для владельца
    if not await check_subscription(client, user_id):
        await message.edit(await send_subscription_required(client, user_id, is_reply=True))
        return
    
    data = await get_email_data(user_id)
    now = datetime.now().timestamp()

    last = (data.get("last_created", 0) or 0) if data else 0
    if now - last < NEW_EMAIL_COOLDOWN:
        wait = int(NEW_EMAIL_COOLDOWN - (now - last))
        await message.edit(
            f"{pe(PE_TIME)} **Подожди ещё {wait} сек.**\n\n"
            f"_Создано {CREATOR_TAG}_"
        )
        return

    await message.edit(f"{pe(PE_BULB)} Создаю почту...")

    result = await create_email()
    if not result:
        await message.edit(
            f"{pe(PE_CROSS)} **Ошибка создания почты**\n"
            f"Попробуй позже.\n\n"
            f"_Создано {CREATOR_TAG}_"
        )
        return

    expires_at = now + EMAIL_LIFETIME
    created_at = now

    await upsert_email(
        user_id,
        email=result["address"],
        password=result["password"],
        token=result["token"],
        expires_at=expires_at,
        created_at=created_at,
        last_created=now
    )

    expire_str = datetime.fromtimestamp(expires_at).strftime("%H:%M:%S")
    bar = progress_bar(EMAIL_LIFETIME, EMAIL_LIFETIME)

    await message.edit(
        f"{pe(PE_MAIL)} **Временная почта создана!**\n\n"
        f"{pe(PE_PERSON)} **Адрес:**\n"
        f"`{result['address']}`\n\n"
        f"{pe(PE_TIME)} {bar}\n"
        f"Действует до: **{expire_str}**\n\n"
        f"{pe(PE_INBOX)} _Письма придут автоматически_\n\n"
        f"_Создано {CREATOR_TAG}_"
    )


async def checkmail_cmd(client, message):
    """Проверить входящие письма"""
    user_id = message.from_user.id
    
    if not await check_subscription(client, user_id):
        await message.edit(await send_subscription_required(client, user_id, is_reply=True))
        return
    
    data = await get_email_data(user_id)

    if not data or not data.get("email"):
        await message.edit(
            f"{pe(PE_CROSS)} **Нет активной почты**\n"
            f"Создай новую: `.newemail`\n\n"
            f"_Создано {CREATOR_TAG}_"
        )
        return

    now = datetime.now().timestamp()
    if data.get("expires_at") and now > data["expires_at"]:
        await clear_email_data(user_id)
        await message.edit(
            f"{pe(PE_FIRE)} **Почта истекла**\n"
            f"Создай новую: `.newemail`\n\n"
            f"_Создано {CREATOR_TAG}_"
        )
        return

    await message.edit(f"{pe(PE_INBOX)} Проверяю письма...")

    try:
        messages_list = await get_messages(data["token"])
    except Exception:
        messages_list = []

    if not messages_list:
        await message.edit(
            f"{pe(PE_INBOX)} **Входящих нет**\n"
            f"Письма придут автоматически.\n\n"
            f"_Создано {CREATOR_TAG}_"
        )
        return

    text = f"{pe(PE_INBOX)} **Входящие — {len(messages_list)} шт.**\n\n"
    
    for idx, msg in enumerate(messages_list[:10], 1):
        sender = msg.get("from", {}).get("address", "???")
        subject = msg.get("subject", "(без темы)")
        text += f"{idx}. **{subject}**\n   От: `{sender}`\n\n"

    text += f"_Создано {CREATOR_TAG}_"
    await message.edit(text)


async def myemail_cmd(client, message):
    """Показать текущую почту и время жизни"""
    user_id = message.from_user.id
    
    if not await check_subscription(client, user_id):
        await message.edit(await send_subscription_required(client, user_id, is_reply=True))
        return
    
    data = await get_email_data(user_id)

    if not data or not data.get("email"):
        await message.edit(
            f"{pe(PE_CROSS)} **Нет активной почты**\n"
            f"Создай новую: `.newemail`\n\n"
            f"_Создано {CREATOR_TAG}_"
        )
        return

    now = datetime.now().timestamp()
    expires_at = data.get("expires_at", 0) or 0
    left = expires_at - now

    if left <= 0:
        await clear_email_data(user_id)
        await message.edit(
            f"{pe(PE_FIRE)} **Почта истекла**\n"
            f"Создай новую: `.newemail`\n\n"
            f"_Создано {CREATOR_TAG}_"
        )
        return

    bar = progress_bar(left, EMAIL_LIFETIME)
    expire_str = datetime.fromtimestamp(expires_at).strftime("%H:%M:%S")
    mins = int(left) // 60
    secs = int(left) % 60

    await message.edit(
        f"{pe(PE_MAIL)} **Твоя временная почта**\n\n"
        f"{pe(PE_PERSON)} `{data['email']}`\n\n"
        f"{pe(PE_TIME)} Осталось: **{mins}:{secs:02d}**\n"
        f"{bar}\n\n"
        f"Удалится в **{expire_str}**\n\n"
        f"_Создано {CREATOR_TAG}_"
    )


async def delmail_cmd(client, message):
    """Удалить текущую почту"""
    user_id = message.from_user.id
    
    if not await check_subscription(client, user_id):
        await message.edit(await send_subscription_required(client, user_id, is_reply=True))
        return
    
    data = await get_email_data(user_id)

    if not data or not data.get("email"):
        await message.edit(
            f"{pe(PE_CROSS)} **Нет активной почты**\n\n"
            f"_Создано {CREATOR_TAG}_"
        )
        return

    await clear_email_data(user_id)
    await message.edit(
        f"{pe(PE_TRASH)} **Почта удалена**\n\n"
        f"_Создано {CREATOR_TAG}_"
    )


async def autoreply_cmd(client, message):
    """Включить/выключить авто-ответ на сообщения в ЛС"""
    global auto_reply_enabled
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        status = "включен" if auto_reply_enabled else "выключен"
        await message.edit(
            f"{pe(PE_BULB)} **Авто-ответ:** `{status}`\n\n"
            f"Использование:\n"
            f"`.autoreply on` — включить\n"
            f"`.autoreply off` — выключить\n\n"
            f"_Создано {CREATOR_TAG}_"
        )
        return
    
    action = args[1].lower()
    if action in ("on", "вкл", "включить"):
        auto_reply_enabled = True
        await message.edit(
            f"{pe(PE_CHECK)} **Авто-ответ включен**\n\n"
            f"_Создано {CREATOR_TAG}_"
        )
    elif action in ("off", "выкл", "выключить"):
        auto_reply_enabled = False
        await message.edit(
            f"{pe(PE_CROSS)} **Авто-ответ выключен**\n\n"
            f"_Создано {CREATOR_TAG}_"
        )
    else:
        await message.edit(
            f"{pe(PE_CROSS)} Неизвестная команда.\n"
            f"Используй: `.autoreply on` или `.autoreply off`\n\n"
            f"_Создано {CREATOR_TAG}_"
        )


async def mailstats_cmd(client, message):
    """Статистика по почтам"""
    total_users = len(await get_all_users())
    active_mails = await count_active_emails()
    
    await message.edit(
        f"{pe(PE_CHART)} **Статистика временных почт**\n\n"
        f"{pe(PE_PERSON)} Всего пользователей: **{total_users}**\n"
        f"{pe(PE_MAIL)} Активных почт: **{active_mails}**\n\n"
        f"_Создано {CREATOR_TAG}_"
    )


async def mailhelp_cmd(client, message):
    """Список всех команд модуля"""
    help_text = (
        f"{pe(PE_BOOK)} **Команды модуля временных почт**\n\n"
        f"{pe(PE_MAIL)} `.newemail` — создать новую почту (10 мин)\n"
        f"{pe(PE_INBOX)} `.checkmail` — проверить входящие\n"
        f"{pe(PE_PERSON)} `.myemail` — показать текущую почту\n"
        f"{pe(PE_TRASH)} `.delmail` — удалить почту\n"
        f"{pe(PE_BULB)} `.autoreply <on/off>` — авто-ответ в ЛС\n"
        f"{pe(PE_CHART)} `.mailstats` — статистика\n"
        f"{pe(PE_BOOK)} `.mailhelp` — этот список\n\n"
        f"{pe(PE_TIME)} **Почты живут 10 минут**\n"
        f"{pe(PE_FIRE)} **Письма приходят автоматически**\n"
        f"{pe(PE_CHECK)} **Полностью бесплатно**\n\n"
        f"{pe(PE_LOCK)} **Требуется подписка:** {CHANNEL_URL}\n\n"
        f"_Создано {CREATOR_TAG}_"
    )
    await message.edit(help_text)


# ══════════════════════════════════════════════════════════════
# ОБРАБОТЧИКИ ДЛЯ ДРУГИХ ПОЛЬЗОВАТЕЛЕЙ
# ══════════════════════════════════════════════════════════════

async def handle_user_newemail(client, message):
    """Другой пользователь создаёт почту"""
    user_id = message.from_user.id
    
    # Проверка подписки
    if not await check_subscription(client, user_id):
        await message.reply(await send_subscription_required(client, user_id, is_reply=True))
        return
    
    data = await get_email_data(user_id)
    now = datetime.now().timestamp()

    last = (data.get("last_created", 0) or 0) if data else 0
    if now - last < NEW_EMAIL_COOLDOWN:
        wait = int(NEW_EMAIL_COOLDOWN - (now - last))
        await message.reply(
            f"{pe(PE_TIME)} **Подожди ещё {wait} сек.**\n\n"
            f"_Создано {CREATOR_TAG}_"
        )
        return

    reply_msg = await message.reply(f"{pe(PE_BULB)} Создаю почту...")

    result = await create_email()
    if not result:
        await reply_msg.edit(
            f"{pe(PE_CROSS)} **Ошибка создания почты**\n"
            f"Попробуй позже.\n\n"
            f"_Создано {CREATOR_TAG}_"
        )
        return

    expires_at = now + EMAIL_LIFETIME
    await upsert_email(
        user_id,
        email=result["address"],
        password=result["password"],
        token=result["token"],
        expires_at=expires_at,
        created_at=now,
        last_created=now
    )

    expire_str = datetime.fromtimestamp(expires_at).strftime("%H:%M:%S")
    bar = progress_bar(EMAIL_LIFETIME, EMAIL_LIFETIME)

    await reply_msg.edit(
        f"{pe(PE_MAIL)} **Временная почта создана!**\n\n"
        f"{pe(PE_PERSON)} **Адрес:**\n"
        f"`{result['address']}`\n\n"
        f"{pe(PE_TIME)} {bar}\n"
        f"Действует до: **{expire_str}**\n\n"
        f"{pe(PE_INBOX)} _Письма придут автоматически_\n\n"
        f"_Создано {CREATOR_TAG}_"
    )


async def handle_user_checkmail(client, message):
    """Другой пользователь проверяет почту"""
    user_id = message.from_user.id
    
    if not await check_subscription(client, user_id):
        await message.reply(await send_subscription_required(client, user_id, is_reply=True))
        return
    
    data = await get_email_data(user_id)

    if not data or not data.get("email"):
        await message.reply(
            f"{pe(PE_CROSS)} **Нет активной почты**\n"
            f"Создай новую: `.newemail`\n\n"
            f"_Создано {CREATOR_TAG}_"
        )
        return

    now = datetime.now().timestamp()
    if data.get("expires_at") and now > data["expires_at"]:
        await clear_email_data(user_id)
        await message.reply(
            f"{pe(PE_FIRE)} **Почта истекла**\n"
            f"Создай новую: `.newemail`\n\n"
            f"_Создано {CREATOR_TAG}_"
        )
        return

    reply_msg = await message.reply(f"{pe(PE_INBOX)} Проверяю письма...")

    try:
        messages_list = await get_messages(data["token"])
    except Exception:
        messages_list = []

    if not messages_list:
        await reply_msg.edit(
            f"{pe(PE_INBOX)} **Входящих нет**\n"
            f"Письма придут автоматически.\n\n"
            f"_Создано {CREATOR_TAG}_"
        )
        return

    text = f"{pe(PE_INBOX)} **Входящие — {len(messages_list)} шт.**\n\n"
    
    for idx, msg in enumerate(messages_list[:10], 1):
        sender = msg.get("from", {}).get("address", "???")
        subject = msg.get("subject", "(без темы)")
        text += f"{idx}. **{subject}**\n   От: `{sender}`\n\n"

    text += f"_Создано {CREATOR_TAG}_"
    await reply_msg.edit(text)


async def handle_user_myemail(client, message):
    """Другой пользователь проверяет свою почту"""
    user_id = message.from_user.id
    
    if not await check_subscription(client, user_id):
        await message.reply(await send_subscription_required(client, user_id, is_reply=True))
        return
    
    data = await get_email_data(user_id)

    if not data or not data.get("email"):
        await message.reply(
            f"{pe(PE_CROSS)} **Нет активной почты**\n"
            f"Создай новую: `.newemail`\n\n"
            f"_Создано {CREATOR_TAG}_"
        )
        return

    now = datetime.now().timestamp()
    expires_at = data.get("expires_at", 0) or 0
    left = expires_at - now

    if left <= 0:
        await clear_email_data(user_id)
        await message.reply(
            f"{pe(PE_FIRE)} **Почта истекла**\n"
            f"Создай новую: `.newemail`\n\n"
            f"_Создано {CREATOR_TAG}_"
        )
        return

    bar = progress_bar(left, EMAIL_LIFETIME)
    expire_str = datetime.fromtimestamp(expires_at).strftime("%H:%M:%S")
    mins = int(left) // 60
    secs = int(left) % 60

    await message.reply(
        f"{pe(PE_MAIL)} **Твоя временная почта**\n\n"
        f"{pe(PE_PERSON)} `{data['email']}`\n\n"
        f"{pe(PE_TIME)} Осталось: **{mins}:{secs:02d}**\n"
        f"{bar}\n\n"
        f"Удалится в **{expire_str}**\n\n"
        f"_Создано {CREATOR_TAG}_"
    )


async def handle_user_delmail(client, message):
    """Другой пользователь удаляет почту"""
    user_id = message.from_user.id
    
    if not await check_subscription(client, user_id):
        await message.reply(await send_subscription_required(client, user_id, is_reply=True))
        return
    
    data = await get_email_data(user_id)

    if not data or not data.get("email"):
        await message.reply(
            f"{pe(PE_CROSS)} **Нет активной почты**\n\n"
            f"_Создано {CREATOR_TAG}_"
        )
        return

    await clear_email_data(user_id)
    await message.reply(
        f"{pe(PE_TRASH)} **Почта удалена**\n\n"
        f"_Создано {CREATOR_TAG}_"
    )


async def handle_user_mailhelp(client, message):
    """Справка для других пользователей"""
    help_text = (
        f"{pe(PE_BOOK)} **Команды временных почт**\n\n"
        f"{pe(PE_MAIL)} `.newemail` — создать почту (10 мин)\n"
        f"{pe(PE_INBOX)} `.checkmail` — проверить входящие\n"
        f"{pe(PE_PERSON)} `.myemail` — показать почту\n"
        f"{pe(PE_TRASH)} `.delmail` — удалить почту\n\n"
        f"{pe(PE_BULB)} **Ответь на моё сообщение** с командой!\n\n"
        f"{pe(PE_LOCK)} **Требуется подписка:** {CHANNEL_URL}\n\n"
        f"_Создано {CREATOR_TAG}_"
    )
    await message.reply(help_text)


# ══════════════════════════════════════════════════════════════
# АВТО-ОТВЕТ
# ══════════════════════════════════════════════════════════════

async def auto_reply_handler(client, message):
    """Авто-ответ на входящие сообщения"""
    if not auto_reply_enabled:
        return
    
    text = message.text or message.caption or ""
    
    # Если пользователь отвечает на наше сообщение командой
    if message.reply_to_message and message.reply_to_message.from_user.id == (await client.get_me()).id:
        if text.startswith(".newemail"):
            await handle_user_newemail(client, message)
        elif text.startswith(".checkmail"):
            await handle_user_checkmail(client, message)
        elif text.startswith(".myemail"):
            await handle_user_myemail(client, message)
        elif text.startswith(".delmail"):
            await handle_user_delmail(client, message)
        elif text.startswith(".mailhelp"):
            await handle_user_mailhelp(client, message)
        else:
            await message.reply(
                f"{pe(PE_BULB)} **Авто-ответ:**\n"
                f"Я сейчас недоступен. Попробуй позже!\n\n"
                f"Хочешь временную почту? Ответь мне:\n"
                f"`.mailhelp` — список команд\n\n"
                f"_Создано {CREATOR_TAG}_"
            )
    else:
        # Первое сообщение от пользователя
        await message.reply(
            f"{pe(PE_MAIL)} **Привет! Я временно недоступен.**\n\n"
            f"{pe(PE_BULB)} Но ты можешь получить бесплатную временную почту!\n"
            f"Просто **ответь на это сообщение** командой:\n\n"
            f"`.newemail` — создать почту\n"
            f"`.mailhelp` — все команды\n\n"
            f"{pe(PE_LOCK)} **Требуется подписка:** {CHANNEL_URL}\n\n"
            f"_Создано {CREATOR_TAG}_"
        )


# ══════════════════════════════════════════════════════════════
# ФОНОВЫЕ ЗАДАЧИ
# ══════════════════════════════════════════════════════════════

async def expiry_task(client):
    """Авто-удаление истёкших почт"""
    while True:
        await asyncio.sleep(30)
        try:
            now = datetime.now().timestamp()
            async with aiosqlite.connect(DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT user_id FROM emails WHERE email IS NOT NULL "
                    "AND expires_at IS NOT NULL AND expires_at < ?",
                    (now,)
                ) as cur:
                    rows = await cur.fetchall()
            
            for row in rows:
                uid = row["user_id"]
                await clear_email_data(uid)
                log.info(f"Auto-expired email for user {uid}")
                
                try:
                    await client.send_message(
                        uid,
                        f"{pe(PE_FIRE)} **Время вышло! Почта удалена.**\n\n"
                        f"Создай новую: `.newemail`\n\n"
                        f"_Создано {CREATOR_TAG}_"
                    )
                except Exception:
                    pass
        except Exception as e:
            log.error(f"Expiry task error: {e}")


async def mail_poll_task(client):
    """Авто-доставка новых писем"""
    while True:
        await asyncio.sleep(15)
        try:
            now = datetime.now().timestamp()
            async with aiosqlite.connect(DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT user_id, email, token, expires_at FROM emails "
                    "WHERE email IS NOT NULL AND token IS NOT NULL AND expires_at > ?",
                    (now,)
                ) as cur:
                    rows = await cur.fetchall()

            for row in rows:
                uid = row["user_id"]
                user_email = row["email"]
                token = row["token"]

                try:
                    messages_list = await get_messages(token)
                except Exception:
                    continue

                if uid not in seen_messages:
                    seen_messages[uid] = set()

                for msg in messages_list:
                    msg_id = msg.get("id")
                    if not msg_id or msg_id in seen_messages[uid]:
                        continue

                    seen_messages[uid].add(msg_id)

                    try:
                        full = await get_message_content(token, msg_id)
                    except Exception:
                        full = None

                    sender = msg.get("from", {}).get("address", "???")
                    subject = msg.get("subject", "(без темы)")

                    raw_date = msg.get("createdAt", "")
                    try:
                        dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                        date_str = dt.strftime("%d.%m.%Y %H:%M:%S")
                    except Exception:
                        date_str = raw_date or "—"

                    body = ""
                    if full:
                        body = full.get("text", "") or ""
                        if not body:
                            html_body = full.get("html", [""])[0] if isinstance(full.get("html"), list) else full.get("html", "")
                            body = re.sub(r"<[^>]+>", " ", html_body or "")
                            body = re.sub(r"\s+", " ", body).strip()

                    body = body.strip()[:2000] or "(тело письма пусто)"
                    body_escaped = escape_html(body)
                    body_with_codes = highlight_codes(body_escaped)

                    text = (
                        f"{pe(PE_INBOX)} **Новое письмо!**\n\n"
                        f"{pe(PE_PERSON)} **На почту:** `{user_email}`\n"
                        f"{pe(PE_MAIL)} **От:** `{sender}`\n"
                        f"{pe(PE_CLOCK)} **Дата:** {date_str}\n"
                        f"{pe(PE_BOOK)} **Тема:** {escape_html(subject)}\n\n"
                        f"**Текст:**\n{body_with_codes}\n\n"
                        f"_Создано {CREATOR_TAG}_"
                    )

                    try:
                        await client.send_message(uid, text)
                    except Exception as e:
                        log.warning(f"Could not deliver mail to user {uid}: {e}")

        except Exception as e:
            log.error(f"Mail poll task error: {e}")


# ══════════════════════════════════════════════════════════════
# РЕГИСТРАЦИЯ МОДУЛЯ
# ══════════════════════════════════════════════════════════════

async def load(client):
    """Загрузка модуля в Heroku Userbot"""
    await init_db()
    log.info("✅ Temp Mail Module loaded by @Kilka_Young")
    
    # Запуск фоновых задач
    asyncio.create_task(expiry_task(client))
    asyncio.create_task(mail_poll_task(client))
    
    # Регистрация команд для владельца
    client.add_handler(newemail_cmd, command="newemail")
    client.add_handler(checkmail_cmd, command="checkmail")
    client.add_handler(myemail_cmd, command="myemail")
    client.add_handler(delmail_cmd, command="delmail")
    client.add_handler(autoreply_cmd, command="autoreply")
    client.add_handler(mailstats_cmd, command="mailstats")
    client.add_handler(mailhelp_cmd, command="mailhelp")
    
    # Регистрация авто-ответа
    client.add_handler(auto_reply_handler, message_type="private")
