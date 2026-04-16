# meta developer: @Kilka_Young
# meta banner: https://imgur.com/a/grammar-fix

import re
from hikkatl.types import Message
from .. import loader, utils

import aiohttp


@loader.tds
class GrammarFixMod(loader.Module):
    """Исправляет грамматические и орфографические ошибки в тексте. By @Kilka_Young"""

    strings = {
        "name": "GrammarFix",
        "no_text": "❌ <b>Нет текста для проверки.</b> Используй реплай или напиши текст после команды.",
        "no_errors": "✅ <b>Ошибок не найдено!</b>",
        "fixed": "✏️ <b>Исправлено:</b>\n<code>{}</code>",
        "errors_found": (
            "📝 <b>Найдено ошибок:</b> {count}\n\n"
            "{details}\n\n"
            "✏️ <b>Исправленный текст:</b>\n<code>{fixed}</code>"
        ),
        "api_error": "❌ <b>Ошибка API:</b> {}",
        "checking": "🔍 <b>Проверяю текст...</b>",
    }

    strings_en = {
        "name": "GrammarFix",
        "no_text": "❌ <b>No text to check.</b> Reply to a message or write text after the command.",
        "no_errors": "✅ <b>No errors found!</b>",
        "fixed": "✏️ <b>Fixed:</b>\n<code>{}</code>",
        "errors_found": (
            "📝 <b>Errors found:</b> {count}\n\n"
            "{details}\n\n"
            "✏️ <b>Fixed text:</b>\n<code>{fixed}</code>"
        ),
        "api_error": "❌ <b>API error:</b> {}",
        "checking": "🔍 <b>Checking text...</b>",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "language",
                "ru",
                "Язык проверки (ru, en, uk, ...)",
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "auto_edit",
                True,
                "Автоматически заменять текст на исправленный при .fix",
                validator=loader.validators.Boolean(),
            ),
        )

    async def _check_text(self, text: str, lang: str) -> dict:
        """Отправляет текст на проверку через LanguageTool API"""
        url = "https://api.languagetool.org/v2/check"
        payload = {
            "text": text,
            "language": lang,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=payload) as resp:
                if resp.status != 200:
                    return {"error": f"HTTP {resp.status}"}
                return await resp.json()

    def _apply_fixes(self, text: str, matches: list) -> str:
        """Применяет исправления к тексту"""
        # Сортируем по позиции с конца, чтобы замены не сбивали индексы
        sorted_matches = sorted(matches, key=lambda m: m["offset"], reverse=True)

        result = text
        for match in sorted_matches:
            offset = match["offset"]
            length = match["length"]
            replacements = match.get("replacements", [])

            if replacements:
                # Берём первое (наиболее вероятное) исправление
                replacement = replacements[0]["value"]
                result = result[:offset] + replacement + result[offset + length:]

        return result

    def _format_details(self, matches: list) -> str:
        """Форматирует детали ошибок"""
        details = []
        for i, match in enumerate(matches, 1):
            context = match.get("context", {})
            original = context.get("text", "")[
                context.get("offset", 0):context.get("offset", 0) + context.get("length", 0)
            ]
            replacements = match.get("replacements", [])
            suggestion = replacements[0]["value"] if replacements else "—"
            message = match.get("message", "")

            details.append(
                f"  {i}. <b>{original}</b> → <b>{suggestion}</b>\n"
                f"      <i>{message}</i>"
            )

        return "\n".join(details)

    @loader.command(
        ru_doc="[текст/реплай] — Найти ошибки и показать исправления",
        en_doc="[text/reply] — Find errors and show fixes",
    )
    async def gramcmd(self, message: Message):
        """[text/reply] — Find errors and show detailed fixes"""
        text = utils.get_args_raw(message)

        if not text and message.is_reply:
            reply = await message.get_reply_message()
            text = reply.raw_text

        if not text:
            await utils.answer(message, self.strings("no_text"))
            return

        await utils.answer(message, self.strings("checking"))

        try:
            result = await self._check_text(text, self.config["language"])
        except Exception as e:
            await utils.answer(message, self.strings("api_error").format(str(e)))
            return

        if "error" in result:
            await utils.answer(message, self.strings("api_error").format(result["error"]))
            return

        matches = result.get("matches", [])

        if not matches:
            await utils.answer(message, self.strings("no_errors"))
            return

        fixed_text = self._apply_fixes(text, matches)
        details = self._format_details(matches)

        await utils.answer(
            message,
            self.strings("errors_found").format(
                count=len(matches),
                details=details,
                fixed=fixed_text,
            ),
        )

    @loader.command(
        ru_doc="[текст/реплай] — Исправить текст и заменить сообщение",
        en_doc="[text/reply] — Fix text and replace the message",
    )
    async def fixcmd(self, message: Message):
        """[text/reply] — Fix text and auto-edit message"""
        text = utils.get_args_raw(message)
        reply = None

        if not text and message.is_reply:
            reply = await message.get_reply_message()
            text = reply.raw_text

        if not text:
            await utils.answer(message, self.strings("no_text"))
            return

        await utils.answer(message, self.strings("checking"))

        try:
            result = await self._check_text(text, self.config["language"])
        except Exception as e:
            await utils.answer(message, self.strings("api_error").format(str(e)))
            return

        if "error" in result:
            await utils.answer(message, self.strings("api_error").format(result["error"]))
            return

        matches = result.get("matches", [])

        if not matches:
            await utils.answer(message, self.strings("no_errors"))
            return

        fixed_text = self._apply_fixes(text, matches)

        if self.config["auto_edit"] and reply and reply.out:
            # Если реплай на своё сообщение — редактируем его
            try:
                await reply.edit(fixed_text)
                await message.delete()
                return
            except Exception:
                pass

        await utils.answer(message, self.strings("fixed").format(fixed_text))

    @loader.command(
        ru_doc="[текст/реплай] — Быстрое исправление (только результат)",
        en_doc="[text/reply] — Quick fix (result only)",
    )
    async def qfixcmd(self, message: Message):
        """[text/reply] — Quick fix, outputs only corrected text"""
        text = utils.get_args_raw(message)

        if not text and message.is_reply:
            reply = await message.get_reply_message()
            text = reply.raw_text

        if not text:
            await utils.answer(message, self.strings("no_text"))
            return

        try:
            result = await self._check_text(text, self.config["language"])
        except Exception as e:
            await utils.answer(message, self.strings("api_error").format(str(e)))
            return

        matches = result.get("matches", [])

        if not matches:
            await utils.answer(message, self.strings("no_errors"))
            return

        fixed_text = self._apply_fixes(text, matches)
        await utils.answer(message, fixed_text)
