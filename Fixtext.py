# meta developer: @Kilka_Young
# meta banner: https://i.imgur.com/JQpVpNg.jpeg
# requires: aiohttp

import aiohttp
from hikkatl.types import Message
from .. import loader, utils


@loader.tds
class FixTextMod(loader.Module):
    """Исправляет грамматические и орфографические ошибки в тексте. By @Kilka_Young"""

    strings = {
        "name": "FixText",
        "no_text": (
            "❌ <b>Нет текста для проверки.</b>\n"
            "Используй реплай на сообщение или напиши текст после команды."
        ),
        "no_errors": "✅ <b>Ошибок не найдено!</b>",
        "checking": "🔍 <b>Проверяю текст...</b>",
        "api_error": "❌ <b>Ошибка API:</b> <code>{}</code>",
        "fixed_short": "✏️ <b>Исправлено:</b>\n<code>{}</code>",
        "errors_found": (
            "📝 <b>Найдено ошибок:</b> {count}\n\n"
            "{details}\n\n"
            "✏️ <b>Исправленный текст:</b>\n<code>{fixed}</code>"
        ),
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "language",
                "ru",
                lambda: "Язык проверки (ru, en, uk, de, fr ...)",
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "auto_edit",
                True,
                lambda: "Редактировать своё сообщение при .fix по реплаю",
                validator=loader.validators.Boolean(),
            ),
        )

    async def _get_text(self, message: Message) -> str | None:
        """Извлекает текст из аргументов или реплая"""
        text = utils.get_args_raw(message)
        if not text and message.is_reply:
            reply = await message.get_reply_message()
            if reply and reply.raw_text:
                text = reply.raw_text
        return text or None

    async def _check_text(self, text: str) -> dict:
        """Проверяет текст через LanguageTool API"""
        url = "https://api.languagetool.org/v2/check"
        data = {
            "text": text,
            "language": self.config["language"],
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as resp:
                if resp.status != 200:
                    return {"error": f"HTTP {resp.status}"}
                return await resp.json()

    @staticmethod
    def _apply_fixes(text: str, matches: list) -> str:
        """Применяет все исправления к тексту"""
        # Сортировка с конца, чтобы замены не сбивали индексы
        for match in sorted(matches, key=lambda m: m["offset"], reverse=True):
            replacements = match.get("replacements", [])
            if replacements:
                offset = match["offset"]
                length = match["length"]
                text = text[:offset] + replacements[0]["value"] + text[offset + length:]
        return text

    @staticmethod
    def _format_details(matches: list) -> str:
        """Форматирует список ошибок"""
        lines = []
        for i, match in enumerate(matches, 1):
            ctx = match.get("context", {})
            start = ctx.get("offset", 0)
            end = start + ctx.get("length", 0)
            original = ctx.get("text", "")[start:end]

            replacements = match.get("replacements", [])
            suggestion = replacements[0]["value"] if replacements else "—"
            msg = match.get("message", "")

            lines.append(
                f"  {i}. <b>{original}</b> → <b>{suggestion}</b>\n"
                f"      <i>{msg}</i>"
            )
        return "\n".join(lines)

    async def _process(self, message: Message) -> tuple:
        """Общая логика: получить текст → проверить → вернуть результат.
        Возвращает (text, fixed_text, matches) или отвечает ошибкой и возвращает None."""
        text = await self._get_text(message)
        if not text:
            await utils.answer(message, self.strings["no_text"])
            return None

        await utils.answer(message, self.strings["checking"])

        try:
            result = await self._check_text(text)
        except Exception as e:
            await utils.answer(message, self.strings["api_error"].format(e))
            return None

        if "error" in result:
            await utils.answer(message, self.strings["api_error"].format(result["error"]))
            return None

        matches = result.get("matches", [])
        if not matches:
            await utils.answer(message, self.strings["no_errors"])
            return None

        fixed = self._apply_fixes(text, matches)
        return text, fixed, matches

    @loader.command(
        ru_doc="[текст/реплай] — Подробный разбор ошибок с исправлением",
    )
    async def gramcmd(self, message: Message):
        """[text/reply] — Detailed error analysis"""
        data = await self._process(message)
        if data is None:
            return

        _, fixed, matches = data
        details = self._format_details(matches)

        await utils.answer(
            message,
            self.strings["errors_found"].format(
                count=len(matches),
                details=details,
                fixed=fixed,
            ),
        )

    @loader.command(
        ru_doc="[текст/реплай] — Исправить текст (авто-редактирование своего сообщения)",
    )
    async def fixcmd(self, message: Message):
        """[text/reply] — Fix text and auto-edit your message"""
        text = utils.get_args_raw(message)
        reply = None

        if not text and message.is_reply:
            reply = await message.get_reply_message()
            if reply and reply.raw_text:
                text = reply.raw_text

        if not text:
            await utils.answer(message, self.strings["no_text"])
            return

        await utils.answer(message, self.strings["checking"])

        try:
            result = await self._check_text(text)
        except Exception as e:
            await utils.answer(message, self.strings["api_error"].format(e))
            return

        if "error" in result:
            await utils.answer(message, self.strings["api_error"].format(result["error"]))
            return

        matches = result.get("matches", [])
        if not matches:
            await utils.answer(message, self.strings["no_errors"])
            return

        fixed = self._apply_fixes(text, matches)

        # Если реплай на своё сообщение — редактируем оригинал
        if self.config["auto_edit"] and reply and reply.out:
            try:
                await reply.edit(fixed)
                await message.delete()
                return
            except Exception:
                pass

        await utils.answer(message, self.strings["fixed_short"].format(fixed))

    @loader.command(
        ru_doc="[текст/реплай] — Быстрое исправление (только результат)",
    )
    async def qfixcmd(self, message: Message):
        """[text/reply] — Quick fix, outputs corrected text only"""
        data = await self._process(message)
        if data is None:
            return

        _, fixed, _ = data
        await utils.answer(message, fixed)
