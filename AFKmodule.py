# meta developer: @Kilka_Young
# meta desc: Продвинутая AFK-система с умными автоответами, статистикой и настройками

from .. import loader, utils
from telethon import types
from datetime import datetime, timezone
import time

__version__ = (1, 2, 0)


@loader.tds
class SmartAFK(loader.Module):
    """Продвинутая AFK-система с умными автоответами, таймером и статистикой."""

    strings = {
        "name": "SmartAFK",
        "afk_enabled": "⏳ <b>AFK включён</b>\nПричина: <code>{reason}</code>",
        "afk_disabled": (
            "✅ <b>AFK выключен</b>\n"
            "⏱ Ты был AFK <b>{duration}</b>\n"
            "💬 Написали: <b>{users} чел.</b>, <b>{msgs} сообщ.</b>"
        ),
        "not_afk": "🚫 Ты сейчас не в AFK.",
        "already_afk": "⏳ AFK уже включён.",
        "afk_reply": (
            "⏳ <b>Пользователь сейчас AFK</b>\n"
            "📌 Причина: <code>{reason}</code>\n"
            "🕐 Отсутствует: <b>{duration}</b>\n"
            "{custom}"
        ),
        "stats": (
            "📊 <b>AFK Статистика</b>\n\n"
            "🔘 Статус: {status}\n"
            "⏱ Длительность: <b>{duration}</b>\n"
            "📌 Причина: <code>{reason}</code>\n"
            "💬 Написали: <b>{users} чел.</b>, <b>{msgs} сообщ.</b>"
        ),
        "ignored": "🚫 <b>{user}</b> добавлен в игнор-лист AFK.",
        "unignored": "✅ <b>{user}</b> удалён из игнор-листа AFK.",
        "not_in_ignore": "❌ Этого пользователя нет в игнор-листе.",
        "ignore_list_empty": "📋 Игнор-лист пуст.",
        "ignore_list": "📋 <b>Игнор-лист AFK:</b>\n{users}",
        "settings_updated": "✅ Настройка <code>{key}</code> обновлена: <code>{val}</code>",
        "settings_show": (
            "⚙️ <b>Настройки SmartAFK</b>\n\n"
            "⏱ Задержка автоответа: <b>{delay} сек.</b>\n"
            "💬 Кастомный текст: <code>{text}</code>"
        ),
        "invalid_delay": "❌ Укажи число секунд. Пример: <code>.afkset delay 120</code>",
        "unknown_cmd": "❓ Неизвестная команда. Используй: <code>delay</code>, <code>text</code>, <code>status</code>",
        "need_reply_or_arg": "❌ Укажи @username или ответь на сообщение пользователя.",
    }

    # ──────────────────────────────────────────────
    # Lifecycle
    # ──────────────────────────────────────────────

    async def client_ready(self, client, db):
        self._client = client
        self._db = db
        self._me = await client.get_me()

        # runtime caches (не сохраняются между перезапусками)
        self._replied: dict[int, float] = {}  # uid -> last reply timestamp

    # ──────────────────────────────────────────────
    # DB helpers
    # ──────────────────────────────────────────────

    def _afk_on(self) -> bool:
        return self.db.get("SmartAFK", "enabled", False)

    def _afk_since(self) -> float:
        return self.db.get("SmartAFK", "since", 0.0)

    def _reason(self) -> str:
        return self.db.get("SmartAFK", "reason", "AFK")

    def _delay(self) -> int:
        return int(self.db.get("SmartAFK", "delay", 180))

    def _custom_text(self) -> str:
        return self.db.get("SmartAFK", "custom_text", "")

    def _ignore_list(self) -> list:
        return self.db.get("SmartAFK", "ignore_list", [])

    def _stats(self) -> dict:
        return self.db.get("SmartAFK", "stats", {"users": set(), "msgs": 0})

    def _set_stats(self, stats: dict):
        # sets не сериализуются в JSON — храним список
        self.db.set("SmartAFK", "stats", stats)

    # ──────────────────────────────────────────────
    # Utilities
    # ──────────────────────────────────────────────

    @staticmethod
    def _fmt_duration(seconds: float) -> str:
        seconds = int(seconds)
        if seconds < 60:
            return f"{seconds} сек."
        minutes, seconds = divmod(seconds, 60)
        if minutes < 60:
            return f"{minutes} мин. {seconds} сек."
        hours, minutes = divmod(minutes, 60)
        parts = f"{hours} ч. {minutes} мин."
        if seconds:
            parts += f" {seconds} сек."
        return parts

    # ──────────────────────────────────────────────
    # Commands
    # ──────────────────────────────────────────────

    @loader.command(ru_doc="[причина] — Включить AFK режим")
    async def afkcmd(self, message):
        """[причина] — Включить AFK режим"""
        if self._afk_on():
            await utils.answer(message, self.strings["already_afk"])
            return

        args = utils.get_args_raw(message)
        reason = args.strip() if args.strip() else "AFK"

        self.db.set("SmartAFK", "enabled", True)
        self.db.set("SmartAFK", "since", time.time())
        self.db.set("SmartAFK", "reason", reason)
        self._set_stats({"users": [], "msgs": 0})
        self._replied.clear()

        await utils.answer(
            message,
            self.strings["afk_enabled"].format(reason=reason),
        )

    @loader.command(ru_doc="Выключить AFK режим")
    async def unafkcmd(self, message):
        """Выключить AFK режим"""
        if not self._afk_on():
            await utils.answer(message, self.strings["not_afk"])
            return

        duration = self._fmt_duration(time.time() - self._afk_since())
        stats = self._stats()
        users_count = len(stats.get("users", []))
        msgs_count = stats.get("msgs", 0)

        self.db.set("SmartAFK", "enabled", False)
        self._replied.clear()

        await utils.answer(
            message,
            self.strings["afk_disabled"].format(
                duration=duration,
                users=users_count,
                msgs=msgs_count,
            ),
        )

    @loader.command(ru_doc="Показать AFK статистику")
    async def afkstatscmd(self, message):
        """Показать AFK статистику"""
        on = self._afk_on()
        duration = (
            self._fmt_duration(time.time() - self._afk_since())
            if on
            else "—"
        )
        stats = self._stats()
        await utils.answer(
            message,
            self.strings["stats"].format(
                status="🟢 Включён" if on else "🔴 Выключен",
                duration=duration,
                reason=self._reason() if on else "—",
                users=len(stats.get("users", [])),
                msgs=stats.get("msgs", 0),
            ),
        )

    @loader.command(ru_doc="[@user] — Добавить/убрать пользователя из игнор-листа")
    async def afkignorecmd(self, message):
        """[@user] — Добавить/убрать пользователя из игнор-листа"""
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()

        uid = None
        display = ""

        if reply:
            uid = reply.sender_id
            sender = await reply.get_sender()
            display = utils.get_display_name(sender)
        elif args:
            target_str = args.strip().lstrip("@")
            try:
                entity = await self._client.get_entity(target_str)
                uid = entity.id
                display = utils.get_display_name(entity)
            except Exception:
                await utils.answer(message, "❌ Не удалось найти пользователя.")
                return
        else:
            await utils.answer(message, self.strings["need_reply_or_arg"])
            return

        ignore = self._ignore_list()
        if uid in ignore:
            ignore.remove(uid)
            self.db.set("SmartAFK", "ignore_list", ignore)
            await utils.answer(
                message, self.strings["unignored"].format(user=display)
            )
        else:
            ignore.append(uid)
            self.db.set("SmartAFK", "ignore_list", ignore)
            await utils.answer(
                message, self.strings["ignored"].format(user=display)
            )

    @loader.command(ru_doc="Показать игнор-лист AFK")
    async def afklistcmd(self, message):
        """Показать игнор-лист AFK"""
        ignore = self._ignore_list()
        if not ignore:
            await utils.answer(message, self.strings["ignore_list_empty"])
            return

        lines = []
        for uid in ignore:
            try:
                entity = await self._client.get_entity(uid)
                name = utils.get_display_name(entity)
                lines.append(f"• {name} (<code>{uid}</code>)")
            except Exception:
                lines.append(f"• <code>{uid}</code>")

        await utils.answer(
            message,
            self.strings["ignore_list"].format(users="\n".join(lines)),
        )

    @loader.command(ru_doc="<delay|text|status> [значение] — Настройки SmartAFK")
    async def afksetcmd(self, message):
        """<delay|text|status> [значение] — Настройки SmartAFK"""
        args = utils.get_args_raw(message).split(maxsplit=1)
        if not args:
            await utils.answer(message, self.strings["unknown_cmd"])
            return

        sub = args[0].lower()

        if sub == "status":
            await utils.answer(
                message,
                self.strings["settings_show"].format(
                    delay=self._delay(),
                    text=self._custom_text() or "<не задан>",
                ),
            )
            return

        if len(args) < 2:
            await utils.answer(message, self.strings["unknown_cmd"])
            return

        value = args[1].strip()

        if sub == "delay":
            if not value.isdigit():
                await utils.answer(message, self.strings["invalid_delay"])
                return
            self.db.set("SmartAFK", "delay", int(value))
            await utils.answer(
                message,
                self.strings["settings_updated"].format(key="delay", val=f"{value} сек."),
            )

        elif sub == "text":
            self.db.set("SmartAFK", "custom_text", value)
            await utils.answer(
                message,
                self.strings["settings_updated"].format(key="text", val=value),
            )

        else:
            await utils.answer(message, self.strings["unknown_cmd"])

    # ──────────────────────────────────────────────
    # Watcher — auto-reply logic
    # ──────────────────────────────────────────────

    async def watcher(self, message):
        if not self._afk_on():
            return

        # только реальные сообщения
        if not isinstance(message, types.Message):
            return

        sender = await message.get_sender()
        if not sender:
            return

        # не отвечать самому себе
        if sender.id == self._me.id:
            return

        # не отвечать ботам
        if getattr(sender, "bot", False):
            return

        # проверка игнор-листа
        if sender.id in self._ignore_list():
            return

        is_private = isinstance(message.peer_id, types.PeerUser)
        is_mention = message.mentioned

        # в группах — только если тегнули
        if not is_private and not is_mention:
            return

        # анти-спам: ограничение по времени
        now = time.time()
        last = self._replied.get(sender.id, 0)
        if now - last < self._delay():
            return

        self._replied[sender.id] = now

        # обновляем статистику
        stats = self._stats()
        users = stats.get("users", [])
        if sender.id not in users:
            users.append(sender.id)
        stats["users"] = users
        stats["msgs"] = stats.get("msgs", 0) + 1
        self._set_stats(stats)

        # формируем ответ
        duration = self._fmt_duration(now - self._afk_since())
        custom = self._custom_text()
        custom_block = f"✉️ {custom}" if custom else ""

        text = self.strings["afk_reply"].format(
            reason=self._reason(),
            duration=duration,
            custom=custom_block,
        ).strip()

        try:
            await message.reply(text, parse_mode="html")
        except Exception:
            pass
