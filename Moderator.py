# meta developer: @Kilka_Young
# requires: sqlalchemy

__version__ = (1, 0, 0)

import asyncio
import time
from datetime import datetime, timedelta
from typing import Optional

from telethon import types
from telethon.tl.functions.channels import (
    EditBannedRequest,
    EditAdminRequest,
    InviteToChannelRequest,
    GetFullChannelRequest,
)
from telethon.tl.functions.messages import EditChatDefaultBannedRightsRequest
from telethon.tl.types import (
    ChatBannedRights,
    ChatAdminRights,
    ChannelParticipantsAdmins,
)

from .. import loader, utils


ADMIN_LEVELS = {
    1: {
        "title": "👤 Модератор",
        "rights": ChatAdminRights(
            delete_messages=True,
            ban_users=False,
            invite_users=True,
            pin_messages=False,
            add_admins=False,
            change_info=False,
            post_messages=False,
            edit_messages=False,
        ),
    },
    2: {
        "title": "🛡 Старший модератор",
        "rights": ChatAdminRights(
            delete_messages=True,
            ban_users=True,
            invite_users=True,
            pin_messages=False,
            add_admins=False,
            change_info=False,
            post_messages=False,
            edit_messages=False,
        ),
    },
    3: {
        "title": "⚔️ Администратор",
        "rights": ChatAdminRights(
            delete_messages=True,
            ban_users=True,
            invite_users=True,
            pin_messages=True,
            add_admins=False,
            change_info=False,
            post_messages=False,
            edit_messages=False,
        ),
    },
    4: {
        "title": "🌟 Старший администратор",
        "rights": ChatAdminRights(
            delete_messages=True,
            ban_users=True,
            invite_users=True,
            pin_messages=True,
            add_admins=False,
            change_info=True,
            post_messages=True,
            edit_messages=True,
        ),
    },
    5: {
        "title": "👑 Главный администратор",
        "rights": ChatAdminRights(
            delete_messages=True,
            ban_users=True,
            invite_users=True,
            pin_messages=True,
            add_admins=True,
            change_info=True,
            post_messages=True,
            edit_messages=True,
        ),
    },
}


@loader.tds
class ChatModerationModule(loader.Module):
    """Модуль модерации чата с расширенными возможностями"""

    strings = {
        "name": "ChatModeration",
        "not_admin": "🚫 <b>Вы не являетесь администратором этого чата!</b>",
        "not_group": "🚫 <b>Эта команда работает только в группах!</b>",
        "no_reply": "🚫 <b>Ответьте на сообщение пользователя!</b>",
        "no_args": "🚫 <b>Укажите аргументы!</b>",
        "banned": "🔨 <b>Пользователь {user} был заблокирован!</b>\n📝 Причина: {reason}",
        "unbanned": "✅ <b>Пользователь {user} разблокирован!</b>",
        "muted": "🔇 <b>Пользователь {user} замучен на {time}!</b>\n📝 Причина: {reason}",
        "unmuted": "🔊 <b>Пользователь {user} размучен!</b>",
        "kicked": "👢 <b>Пользователь {user} был кикнут!</b>\n📝 Причина: {reason}",
        "chat_closed": "🔒 <b>Чат закрыт!</b>",
        "chat_opened": "🔓 <b>Чат открыт!</b>",
        "admin_given": "⭐️ <b>Пользователю {user} выдан {level} уровень администрации!</b>",
        "admin_removed": "❌ <b>У пользователя {user} сняты права администратора!</b>",
        "stats": "📊 <b>Статистика чата:</b>\n\n"
                 "📅 За сегодня: <b>{day}</b> сообщений\n"
                 "📆 За месяц: <b>{month}</b> сообщений\n"
                 "🗓 За всё время: <b>{all_time}</b> сообщений",
        "top_loading": "⏳ <b>Загрузка топа...</b>",
        "no_data": "📭 <b>Нет данных за выбранный период!</b>",
        "error": "❌ <b>Ошибка: {error}</b>",
        "user_not_found": "🚫 <b>Пользователь не найден!</b>",
        "self_action": "🚫 <b>Нельзя применить действие к себе!</b>",
        "admin_protect": "🚫 <b>Нельзя применить действие к администратору!</b>",
        "pin_success": "📌 <b>Сообщение закреплено!</b>",
        "unpin_success": "📌 <b>Сообщение откреплено!</b>",
        "warn_given": "⚠️ <b>Пользователь {user} получил предупреждение! ({count}/3)</b>\n📝 Причина: {reason}",
        "warn_reset": "✅ <b>Предупреждения пользователя {user} сброшены!</b>",
        "auto_ban": "🔨 <b>Пользователь {user} автоматически заблокирован за 3 предупреждения!</b>",
        "admin_config": "⚙️ <b>Конфигурация уровней администрации:</b>\n\n{levels}",
        "choose_period": "📅 <b>Выберите период для топа:</b>",
        "no_reply_or_args": "🚫 <b>Ответьте на сообщение или укажите username/ID!</b>",
        "slow_mode_set": "🐢 <b>Медленный режим установлен: {time} секунд!</b>",
        "slow_mode_off": "✅ <b>Медленный режим отключён!</b>",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "auto_ban_warns",
                3,
                "Количество предупреждений до автобана",
                validator=loader.validators.Integer(minimum=1, maximum=10),
            ),
            loader.ConfigValue(
                "default_mute_time",
                3600,
                "Время мута по умолчанию (в секундах)",
                validator=loader.validators.Integer(minimum=60),
            ),
            loader.ConfigValue(
                "log_channel",
                "",
                "ID канала для логов модерации (необязательно)",
            ),
        )
        self._message_stats = {}
        self._warns = {}

    async def client_ready(self, client, db):
        self._client = client
        self._db = db
        self._message_stats = self.db.get("ChatModeration", "message_stats", {})
        self._warns = self.db.get("ChatModeration", "warns", {})

    # ========================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ========================

    def _save_stats(self):
        self.db.set("ChatModeration", "message_stats", self._message_stats)

    def _save_warns(self):
        self.db.set("ChatModeration", "warns", self._warns)

    async def _check_admin(self, message) -> bool:
        """Проверка на администратора"""
        if not message.is_group and not message.is_channel:
            await utils.answer(message, self.strings["not_group"])
            return False

        chat = await message.get_chat()
        try:
            perms = await self._client.get_permissions(chat, message.sender_id)
            if not perms.is_admin and not perms.is_creator:
                await utils.answer(message, self.strings["not_admin"])
                return False
            return True
        except Exception:
            await utils.answer(message, self.strings["not_admin"])
            return False

    async def _get_target(self, message) -> Optional[types.User]:
        """Получение целевого пользователя"""
        reply = await message.get_reply_message()
        if reply:
            return await reply.get_sender()

        args = utils.get_args(message)
        if args:
            try:
                user = await self._client.get_entity(args[0])
                return user
            except Exception:
                return None
        return None

    async def _is_admin_target(self, message, user) -> bool:
        """Проверка является ли цель администратором"""
        try:
            chat = await message.get_chat()
            perms = await self._client.get_permissions(chat, user.id)
            return perms.is_admin or perms.is_creator
        except Exception:
            return False

    async def _log_action(self, action: str, chat_id: int):
        """Логирование действий в канал"""
        if self.config["log_channel"]:
            try:
                await self._client.send_message(
                    int(self.config["log_channel"]),
                    f"📋 <b>Лог модерации</b>\n{action}",
                    parse_mode="html",
                )
            except Exception:
                pass

    def _parse_time(self, time_str: str) -> Optional[int]:
        """Парсинг времени из строки (1h, 30m, 1d)"""
        units = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
        try:
            if time_str[-1] in units:
                return int(time_str[:-1]) * units[time_str[-1]]
            return int(time_str)
        except (ValueError, IndexError):
            return None

    def _format_time(self, seconds: int) -> str:
        """Форматирование времени"""
        if seconds < 60:
            return f"{seconds} сек."
        elif seconds < 3600:
            return f"{seconds // 60} мин."
        elif seconds < 86400:
            return f"{seconds // 3600} ч."
        else:
            return f"{seconds // 86400} дн."

    def _record_message(self, chat_id: int, user_id: int):
        """Запись сообщения в статистику"""
        chat_key = str(chat_id)
        user_key = str(user_id)
        timestamp = int(time.time())

        if chat_key not in self._message_stats:
            self._message_stats[chat_key] = {}

        if user_key not in self._message_stats[chat_key]:
            self._message_stats[chat_key][user_key] = []

        self._message_stats[chat_key][user_key].append(timestamp)
        self._save_stats()

    # ========================
    # НАБЛЮДАТЕЛЬ СООБЩЕНИЙ
    # ========================

    async def watcher(self, message):
        """Запись статистики сообщений"""
        if not message.is_group and not message.is_channel:
            return
        if not message.sender_id:
            return

        chat_id = message.chat_id
        self._record_message(chat_id, message.sender_id)

    # ========================
    # КОМАНДЫ МОДЕРАЦИИ
    # ========================

    @loader.command(ru_doc="Забанить пользователя. Ответ/username + причина")
    async def bancmd(self, message):
        """Бан пользователя"""
        if not await self._check_admin(message):
            return

        user = await self._get_target(message)
        if not user:
            await utils.answer(message, self.strings["no_reply_or_args"])
            return

        if user.id == message.sender_id:
            await utils.answer(message, self.strings["self_action"])
            return

        if await self._is_admin_target(message, user):
            await utils.answer(message, self.strings["admin_protect"])
            return

        args = utils.get_args_raw(message)
        reason = args if args and not args.startswith("@") else "Не указана"

        try:
            chat = await message.get_chat()
            await self._client(
                EditBannedRequest(
                    chat,
                    user,
                    ChatBannedRights(
                        until_date=None,
                        view_messages=True,
                    ),
                )
            )

            text = self.strings["banned"].format(
                user=f'<a href="tg://user?id={user.id}">{utils.escape_html(user.first_name)}</a>',
                reason=reason,
            )
            await utils.answer(message, text)
            await self._log_action(text, message.chat_id)

        except Exception as e:
            await utils.answer(message, self.strings["error"].format(error=str(e)))

    @loader.command(ru_doc="Разбанить пользователя. Ответ/username")
    async def unbancmd(self, message):
        """Разбан пользователя"""
        if not await self._check_admin(message):
            return

        user = await self._get_target(message)
        if not user:
            await utils.answer(message, self.strings["no_reply_or_args"])
            return

        try:
            chat = await message.get_chat()
            await self._client(
                EditBannedRequest(
                    chat,
                    user,
                    ChatBannedRights(until_date=None),
                )
            )

            text = self.strings["unbanned"].format(
                user=f'<a href="tg://user?id={user.id}">{utils.escape_html(user.first_name)}</a>'
            )
            await utils.answer(message, text)
            await self._log_action(text, message.chat_id)

        except Exception as e:
            await utils.answer(message, self.strings["error"].format(error=str(e)))

    @loader.command(ru_doc="Замутить пользователя. Ответ/username время(1h/30m/1d) причина")
    async def mutecmd(self, message):
        """Мут пользователя"""
        if not await self._check_admin(message):
            return

        user = await self._get_target(message)
        if not user:
            await utils.answer(message, self.strings["no_reply_or_args"])
            return

        if user.id == message.sender_id:
            await utils.answer(message, self.strings["self_action"])
            return

        if await self._is_admin_target(message, user):
            await utils.answer(message, self.strings["admin_protect"])
            return

        args = utils.get_args(message)
        mute_time = self.config["default_mute_time"]
        reason = "Не указана"

        if args:
            parsed = self._parse_time(args[0])
            if parsed:
                mute_time = parsed
                reason = " ".join(args[1:]) if len(args) > 1 else "Не указана"
            else:
                reason = " ".join(args)

        until_date = datetime.now() + timedelta(seconds=mute_time)

        try:
            chat = await message.get_chat()
            await self._client(
                EditBannedRequest(
                    chat,
                    user,
                    ChatBannedRights(
                        until_date=until_date,
                        send_messages=True,
                        send_media=True,
                        send_stickers=True,
                        send_gifs=True,
                        send_games=True,
                        send_inline=True,
                    ),
                )
            )

            text = self.strings["muted"].format(
                user=f'<a href="tg://user?id={user.id}">{utils.escape_html(user.first_name)}</a>',
                time=self._format_time(mute_time),
                reason=reason,
            )
            await utils.answer(message, text)
            await self._log_action(text, message.chat_id)

        except Exception as e:
            await utils.answer(message, self.strings["error"].format(error=str(e)))

    @loader.command(ru_doc="Размутить пользователя. Ответ/username")
    async def unmutecmd(self, message):
        """Размут пользователя"""
        if not await self._check_admin(message):
            return

        user = await self._get_target(message)
        if not user:
            await utils.answer(message, self.strings["no_reply_or_args"])
            return

        try:
            chat = await message.get_chat()
            await self._client(
                EditBannedRequest(
                    chat,
                    user,
                    ChatBannedRights(until_date=None),
                )
            )

            text = self.strings["unmuted"].format(
                user=f'<a href="tg://user?id={user.id}">{utils.escape_html(user.first_name)}</a>'
            )
            await utils.answer(message, text)
            await self._log_action(text, message.chat_id)

        except Exception as e:
            await utils.answer(message, self.strings["error"].format(error=str(e)))

    @loader.command(ru_doc="Кикнуть пользователя. Ответ/username причина")
    async def kickcmd(self, message):
        """Кик пользователя"""
        if not await self._check_admin(message):
            return

        user = await self._get_target(message)
        if not user:
            await utils.answer(message, self.strings["no_reply_or_args"])
            return

        if user.id == message.sender_id:
            await utils.answer(message, self.strings["self_action"])
            return

        if await self._is_admin_target(message, user):
            await utils.answer(message, self.strings["admin_protect"])
            return

        args = utils.get_args_raw(message)
        reason = args if args else "Не указана"

        try:
            chat = await message.get_chat()
            await self._client.kick_participant(chat, user)

            text = self.strings["kicked"].format(
                user=f'<a href="tg://user?id={user.id}">{utils.escape_html(user.first_name)}</a>',
                reason=reason,
            )
            await utils.answer(message, text)
            await self._log_action(text, message.chat_id)

        except Exception as e:
            await utils.answer(message, self.strings["error"].format(error=str(e)))

    @loader.command(ru_doc="Закрыть чат (запретить писать)")
    async def closecmd(self, message):
        """Закрыть чат"""
        if not await self._check_admin(message):
            return

        try:
            chat = await message.get_chat()
            await self._client(
                EditChatDefaultBannedRightsRequest(
                    peer=chat,
                    banned_rights=ChatBannedRights(
                        until_date=None,
                        send_messages=True,
                        send_media=True,
                        send_stickers=True,
                        send_gifs=True,
                        send_games=True,
                        send_inline=True,
                    ),
                )
            )
            await utils.answer(message, self.strings["chat_closed"])

        except Exception as e:
            await utils.answer(message, self.strings["error"].format(error=str(e)))

    @loader.command(ru_doc="Открыть чат")
    async def opencmd(self, message):
        """Открыть чат"""
        if not await self._check_admin(message):
            return

        try:
            chat = await message.get_chat()
            await self._client(
                EditChatDefaultBannedRightsRequest(
                    peer=chat,
                    banned_rights=ChatBannedRights(until_date=None),
                )
            )
            await utils.answer(message, self.strings["chat_opened"])

        except Exception as e:
            await utils.answer(message, self.strings["error"].format(error=str(e)))

    @loader.command(ru_doc="Закрепить сообщение. Ответьте на сообщение")
    async def pincmd(self, message):
        """Закрепить сообщение"""
        if not await self._check_admin(message):
            return

        reply = await message.get_reply_message()
        if not reply:
            await utils.answer(message, self.strings["no_reply"])
            return

        try:
            await self._client.pin_message(
                message.chat_id,
                reply.id,
                notify=False,
            )
            await utils.answer(message, self.strings["pin_success"])

        except Exception as e:
            await utils.answer(message, self.strings["error"].format(error=str(e)))

    @loader.command(ru_doc="Открепить сообщение. Ответьте на сообщение или все")
    async def unpincmd(self, message):
        """Открепить сообщение"""
        if not await self._check_admin(message):
            return

        try:
            reply = await message.get_reply_message()
            if reply:
                await self._client.unpin_message(message.chat_id, reply.id)
            else:
                await self._client.unpin_message(message.chat_id)

            await utils.answer(message, self.strings["unpin_success"])

        except Exception as e:
            await utils.answer(message, self.strings["error"].format(error=str(e)))

    @loader.command(ru_doc="Выдать предупреждение. Ответ/username причина")
    async def warncmd(self, message):
        """Выдать предупреждение"""
        if not await self._check_admin(message):
            return

        user = await self._get_target(message)
        if not user:
            await utils.answer(message, self.strings["no_reply_or_args"])
            return

        if user.id == message.sender_id:
            await utils.answer(message, self.strings["self_action"])
            return

        args = utils.get_args_raw(message)
        reason = args if args else "Не указана"

        chat_key = str(message.chat_id)
        user_key = str(user.id)

        if chat_key not in self._warns:
            self._warns[chat_key] = {}

        if user_key not in self._warns[chat_key]:
            self._warns[chat_key][user_key] = 0

        self._warns[chat_key][user_key] += 1
        count = self._warns[chat_key][user_key]
        self._save_warns()

        max_warns = self.config["auto_ban_warns"]

        if count >= max_warns:
            self._warns[chat_key][user_key] = 0
            self._save_warns()
            try:
                chat = await message.get_chat()
                await self._client(
                    EditBannedRequest(
                        chat,
                        user,
                        ChatBannedRights(until_date=None, view_messages=True),
                    )
                )
                text = self.strings["auto_ban"].format(
                    user=f'<a href="tg://user?id={user.id}">{utils.escape_html(user.first_name)}</a>'
                )
                await utils.answer(message, text)
                await self._log_action(text, message.chat_id)
            except Exception as e:
                await utils.answer(message, self.strings["error"].format(error=str(e)))
        else:
            text = self.strings["warn_given"].format(
                user=f'<a href="tg://user?id={user.id}">{utils.escape_html(user.first_name)}</a>',
                count=count,
                reason=reason,
            )
            await utils.answer(message, text)
            await self._log_action(text, message.chat_id)

    @loader.command(ru_doc="Сбросить предупреждения. Ответ/username")
    async def unwarnallcmd(self, message):
        """Сбросить предупреждения"""
        if not await self._check_admin(message):
            return

        user = await self._get_target(message)
        if not user:
            await utils.answer(message, self.strings["no_reply_or_args"])
            return

        chat_key = str(message.chat_id)
        user_key = str(user.id)

        if chat_key in self._warns and user_key in self._warns[chat_key]:
            self._warns[chat_key][user_key] = 0
            self._save_warns()

        await utils.answer(
            message,
            self.strings["warn_reset"].format(
                user=f'<a href="tg://user?id={user.id}">{utils.escape_html(user.first_name)}</a>'
            ),
        )

    @loader.command(ru_doc="Установить медленный режим. slowmode <секунды> или off")
    async def slowmodecmd(self, message):
        """Медленный режим"""
        if not await self._check_admin(message):
            return

        args = utils.get_args(message)
        if not args:
            await utils.answer(message, self.strings["no_args"])
            return

        try:
            chat = await message.get_chat()

            if args[0].lower() == "off":
                from telethon.tl.functions.channels import ToggleSlowModeRequest
                await self._client(ToggleSlowModeRequest(chat, seconds=0))
                await utils.answer(message, self.strings["slow_mode_off"])
            else:
                seconds = int(args[0])
                from telethon.tl.functions.channels import ToggleSlowModeRequest
                await self._client(ToggleSlowModeRequest(chat, seconds=seconds))
                await utils.answer(
                    message,
                    self.strings["slow_mode_set"].format(time=seconds),
                )

        except Exception as e:
            await utils.answer(message, self.strings["error"].format(error=str(e)))

    # ========================
    # КОМАНДЫ АДМИНИСТРАЦИИ
    # ========================

    @loader.command(ru_doc="Выдать права администратора. Ответ/username уровень(1-5) [звание]")
    async def admincmd(self, message):
        """Выдать права администратора"""
        if not await self._check_admin(message):
            return

        user = await self._get_target(message)
        if not user:
            await utils.answer(message, self.strings["no_reply_or_args"])
            return

        args = utils.get_args(message)

        level = 1
        custom_title = None

        for arg in args:
            if arg.isdigit() and 1 <= int(arg) <= 5:
                level = int(arg)
            elif not arg.startswith("@") and not arg.isdigit():
                custom_title = arg

        if not custom_title:
            custom_title = ADMIN_LEVELS[level]["title"]

        try:
            chat = await message.get_chat()
            await self._client(
                EditAdminRequest(
                    channel=chat,
                    user_id=user,
                    admin_rights=ADMIN_LEVELS[level]["rights"],
                    rank=custom_title,
                )
            )

            text = self.strings["admin_given"].format(
                user=f'<a href="tg://user?id={user.id}">{utils.escape_html(user.first_name)}</a>',
                level=f"{level} ({custom_title})",
            )
            await utils.answer(message, text)
            await self._log_action(text, message.chat_id)

        except Exception as e:
            await utils.answer(message, self.strings["error"].format(error=str(e)))

    @loader.command(ru_doc="Снять права администратора. Ответ/username")
    async def deadmincmd(self, message):
        """Снять права администратора"""
        if not await self._check_admin(message):
            return

        user = await self._get_target(message)
        if not user:
            await utils.answer(message, self.strings["no_reply_or_args"])
            return

        try:
            chat = await message.get_chat()
            await self._client(
                EditAdminRequest(
                    channel=chat,
                    user_id=user,
                    admin_rights=ChatAdminRights(),
                    rank="",
                )
            )

            text = self.strings["admin_removed"].format(
                user=f'<a href="tg://user?id={user.id}">{utils.escape_html(user.first_name)}</a>'
            )
            await utils.answer(message, text)
            await self._log_action(text, message.chat_id)

        except Exception as e:
            await utils.answer(message, self.strings["error"].format(error=str(e)))

    @loader.command(ru_doc="Показать уровни администрации")
    async def adminlevelscmd(self, message):
        """Информация об уровнях администрации"""
        levels_text = ""
        for level, data in ADMIN_LEVELS.items():
            rights = data["rights"]
            rights_list = []

            if rights.delete_messages:
                rights_list.append("🗑 Удаление сообщений")
            if rights.ban_users:
                rights_list.append("🔨 Блокировка пользователей")
            if rights.invite_users:
                rights_list.append("➕ Приглашение пользователей")
            if rights.pin_messages:
                rights_list.append("📌 Закрепление сообщений")
            if rights.change_info:
                rights_list.append("ℹ️ Изменение информации")
            if rights.post_messages:
                rights_list.append("📢 Публикация сообщений")
            if rights.edit_messages:
                rights_list.append("✏️ Редактирование сообщений")
            if rights.add_admins:
                rights_list.append("👑 Добавление администраторов")

            levels_text += (
                f"<b>Уровень {level} — {data['title']}</b>\n"
                f"{'  ├ ' + chr(10) + '  ├ '.join(rights_list[:-1]) + chr(10) + '  └ ' + rights_list[-1] if len(rights_list) > 1 else '  └ ' + rights_list[0] if rights_list else '  └ Нет прав'}\n\n"
            )

        await utils.answer(
            message,
            self.strings["admin_config"].format(levels=levels_text),
        )

    # ========================
    # СТАТИСТИКА И ТОП
    # ========================

    @loader.command(ru_doc="Статистика сообщений чата")
    async def statscmd(self, message):
        """Статистика чата"""
        if not message.is_group and not message.is_channel:
            await utils.answer(message, self.strings["not_group"])
            return

        chat_key = str(message.chat_id)
        now = int(time.time())
        day_ago = now - 86400
        month_ago = now - 2592000

        total_day = 0
        total_month = 0
        total_all = 0

        if chat_key in self._message_stats:
            for user_msgs in self._message_stats[chat_key].values():
                for ts in user_msgs:
                    total_all += 1
                    if ts >= day_ago:
                        total_day += 1
                    if ts >= month_ago:
                        total_month += 1

        await utils.answer(
            message,
            self.strings["stats"].format(
                day=total_day,
                month=total_month,
                all_time=total_all,
            ),
        )

    @loader.command(ru_doc="Топ активных пользователей. Выберите период")
    async def topcmd(self, message):
        """Топ активных пользователей"""
        if not message.is_group and not message.is_channel:
            await utils.answer(message, self.strings["not_group"])
            return

        keyboard = [
            [
                {"text": "📅 1 день", "data": "top_1"},
                {"text": "📆 7 дней", "data": "top_7"},
            ],
            [
                {"text": "🗓 Месяц", "data": "top_30"},
                {"text": "🌐 Всё время", "data": "top_0"},
            ],
        ]

        await self.inline.form(
            text=self.strings["choose_period"],
            message=message,
            reply_markup=keyboard,
        )

    async def _generate_top(self, chat_id: int, days: int) -> str:
        """Генерация топа пользователей"""
        chat_key = str(chat_id)
        now = int(time.time())

        period_start = 0 if days == 0 else now - (days * 86400)

        user_counts = {}

        if chat_key not in self._message_stats:
            return self.strings["no_data"]

        for user_id, messages in self._message_stats[chat_key].items():
            count = sum(1 for ts in messages if ts >= period_start)
            if count > 0:
                user_counts[user_id] = count

        if not user_counts:
            return self.strings["no_data"]

        sorted_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:600]

        period_text = {
            0: "🌐 Всё время",
            1: "📅 1 день",
            7: "📆 7 дней",
            30: "🗓 Месяц",
        }.get(days, f"{days} дней")

        result = f"🏆 <b>Топ активных пользователей ({period_text}):</b>\n\n"

        medals = {1: "🥇", 2: "🥈", 3: "🥉"}

        for i, (user_id, count) in enumerate(sorted_users, 1):
            medal = medals.get(i, f"{i}.")
            try:
                user = await self._client.get_entity(int(user_id))
                name = utils.escape_html(
                    f"{user.first_name} {user.last_name or ''}".strip()
                )
                user_link = f'<a href="tg://user?id={user_id}">{name}</a>'
            except Exception:
                user_link = f"ID: {user_id}"

            bar_length = min(20, max(1, count * 20 // sorted_users[0][1]))
            bar = "█" * bar_length + "░" * (20 - bar_length)

            result += f"{medal} {user_link}\n    {bar} <b>{count}</b> сообщ.\n\n"

            if i >= 20:
                result += f"... и ещё {len(sorted_users) - 20} пользователей\n"
                break

        return result

    @loader.callback_handler()
    async def top_callback(self, call):
        """Обработка кнопок топа"""
        if not call.data.startswith("top_"):
            return

        days = int(call.data.split("_")[1])

        await call.answer("⏳ Загружаю...")
        await call.edit(self.strings["top_loading"])

        text = await self._generate_top(call.message.chat_id, days)

        period_names = {
            0: "всё время",
            1: "1 день",
            7: "7 дней",
            30: "месяц",
        }

        keyboard = [
            [
                {"text": "📅 1 день", "data": "top_1"},
                {"text": "📆 7 дней", "data": "top_7"},
            ],
            [
                {"text": "🗓 Месяц", "data": "top_30"},
                {"text": "🌐 Всё время", "data": "top_0"},
            ],
            [{"text": "🔄 Обновить", "data": f"top_{days}"}],
        ]

        await call.edit(text, reply_markup=keyboard)

    # ========================
    # ДОПОЛНИТЕЛЬНЫЕ КОМАНДЫ
    # ========================

    @loader.command(ru_doc="Удалить N сообщений. purge <количество>")
    async def purgecmd(self, message):
        """Удаление сообщений"""
        if not await self._check_admin(message):
            return

        args = utils.get_args(message)
        if not args or not args[0].isdigit():
            await utils.answer(message, "🚫 <b>Укажите количество сообщений для удаления!</b>")
            return

        count = min(int(args[0]), 100)

        try:
            messages_to_delete = []
            async for msg in self._client.iter_messages(
                message.chat_id, limit=count + 1
            ):
                messages_to_delete.append(msg.id)

            await self._client.delete_messages(message.chat_id, messages_to_delete)

        except Exception as e:
            await utils.answer(message, self.strings["error"].format(error=str(e)))

    @loader.command(ru_doc="Информация о пользователе. Ответ/username")
    async def whoiscmd(self, message):
        """Информация о пользователе"""
        user = await self._get_target(message)
        if not user:
            me = await self._client.get_me()
            user = me

        try:
            chat_key = str(message.chat_id)
            user_key = str(user.id)

            total_msgs = 0
            day_msgs = 0
            month_msgs = 0
            now = int(time.time())

            if (
                chat_key in self._message_stats
                and user_key in self._message_stats[chat_key]
            ):
                for ts in self._message_stats[chat_key][user_key]:
                    total_msgs += 1
                    if ts >= now - 86400:
                        day_msgs += 1
                    if ts >= now - 2592000:
                        month_msgs += 1

            warns = 0
            if chat_key in self._warns and user_key in self._warns[chat_key]:
                warns = self._warns[chat_key][user_key]

            is_admin = False
            is_creator = False
            if message.is_group or message.is_channel:
                try:
                    chat = await message.get_chat()
                    perms = await self._client.get_permissions(chat, user.id)
                    is_admin = perms.is_admin
                    is_creator = perms.is_creator
                except Exception:
                    pass

            status_emoji = "👑" if is_creator else "⭐️" if is_admin else "👤"
            username = f"@{user.username}" if user.username else "Нет"
            name = f"{user.first_name} {user.last_name or ''}".strip()

            text = (
                f"👤 <b>Информация о пользователе</b>\n\n"
                f"{status_emoji} <b>Имя:</b> {utils.escape_html(name)}\n"
                f"🆔 <b>ID:</b> <code>{user.id}</code>\n"
                f"📎 <b>Username:</b> {username}\n"
                f"{'👑 Создатель' if is_creator else '⭐️ Администратор' if is_admin else ''}\n\n"
                f"📊 <b>Статистика сообщений:</b>\n"
                f"  • За день: <b>{day_msgs}</b>\n"
                f"  • За месяц: <b>{month_msgs}</b>\n"
                f"  • Всего: <b>{total_msgs}</b>\n\n"
                f"⚠️ <b>Предупреждений:</b> {warns}/{self.config['auto_ban_warns']}"
            )

            await utils.answer(message, text)

        except Exception as e:
            await utils.answer(message, self.strings["error"].format(error=str(e)))

    @loader.command(ru_doc="Список команд модерации")
    async def modhelpcmd(self, message):
        """Помощь по командам"""
        text = (
            "🛡 <b>Команды модерации</b>\n\n"
            "🔨 <b>Основные:</b>\n"
            "• <code>.ban</code> — Заблокировать\n"
            "• <code>.unban</code> — Разблокировать\n"
            "• <code>.mute [время]</code> — Замутить\n"
            "• <code>.unmute</code> — Размутить\n"
            "• <code>.kick</code> — Выгнать\n\n"
            "⚙️ <b>Управление чатом:</b>\n"
            "• <code>.close</code> — Закрыть чат\n"
            "• <code>.open</code> — Открыть чат\n"
            "• <code>.pin</code> — Закрепить\n"
            "• <code>.unpin</code> — Открепить\n"
            "• <code>.slowmode [сек/off]</code> — Медл. режим\n"
            "• <code>.purge [N]</code> — Удалить N сообщений\n\n"
            "⚠️ <b>Предупреждения:</b>\n"
            "• <code>.warn [причина]</code> — Предупреждение\n"
            "• <code>.unwarnall</code> — Сбросить варны\n\n"
            "👑 <b>Администрация:</b>\n"
            "• <code>.admin [уровень 1-5] [звание]</code> — Выдать\n"
            "• <code>.deadmin</code> — Снять права\n"
            "• <code>.adminlevels</code> — Уровни прав\n\n"
            "📊 <b>Статистика:</b>\n"
            "• <code>.stats</code> — Статистика чата\n"
            "• <code>.top</code> — Топ активных\n"
            "• <code>.whois</code> — Инфо о пользователе\n"
        )
        await utils.answer(message, text)
