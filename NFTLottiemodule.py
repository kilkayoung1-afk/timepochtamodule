# meta developer: @Kilka_Young
# meta desc: Скачивает Lottie-анимацию (TGS) из NFT-подарка Telegram и отдаёт пользователю файлом
# scope: hikka_only
# scope: hikka_min 1.6.2

"""
NFTLottie — модуль для Hikka.

Команда:
    .nftlottie <slug|ссылка>   — скачать Lottie-модель из NFT-подарка и отправить
                                  её в текущий чат как файл .tgs.

Без аргумента можно ответить (.nftlottie) на сообщение, содержащее
NFT-подарок (action=MessageActionStarGiftUnique) или ссылку вида
https://t.me/nft/PlushPepe-1234.
"""

import gzip
import io
import logging
import re

from telethon.tl.functions.payments import GetUniqueStarGiftRequest
from telethon.tl.types import (
    DocumentAttributeFilename,
    MessageActionStarGiftUnique,
    StarGiftUnique,
)

from .. import loader, utils

logger = logging.getLogger(__name__)

SLUG_RE = re.compile(r"(?:t\.me/nft/)?([A-Za-z][A-Za-z0-9]*-\d+)")


@loader.tds
class NFTLottieMod(loader.Module):
    """Скачивает Lottie (TGS) из NFT-подарка Telegram и отдаёт пользователю файлом"""

    strings = {
        "name": "NFTLottie",
        "no_args": (
            "🚫 <b>Укажи слаг NFT-подарка или ответь на сообщение с подарком.</b>\n"
            "Пример: <code>.nftlottie PlushPepe-1234</code> "
            "или <code>.nftlottie https://t.me/nft/PlushPepe-1234</code>"
        ),
        "fetching": "⏳ <b>Получаю NFT-подарок</b> <code>{slug}</code>...",
        "not_found": "❌ <b>NFT-подарок</b> <code>{slug}</code> <b>не найден.</b>",
        "no_model": "❌ <b>В подарке нет модели с анимацией.</b>",
        "uploading": "⬆️ <b>Отправляю файл</b> <code>{name}</code>...",
        "info": (
            "🎁 <b>NFT-подарок:</b> <code>{slug}</code>\n"
            "🪄 <b>Модель:</b> <b>{model}</b>\n"
            "🌈 <b>Узор:</b> <b>{pattern}</b>\n"
            "🎨 <b>Фон:</b> <b>{backdrop}</b>"
        ),
        "error": "❌ <b>Ошибка:</b> <code>{err}</code>",
    }

    strings_ru = {
        "_cls_doc": (
            "Скачивает Lottie из NFT-подарка Telegram и отдаёт пользователю "
            "файлом .json (распакованный TGS)"
        ),
    }

    @staticmethod
    def _extract_slug(text):
        if not text:
            return None
        match = SLUG_RE.search(text)
        return match.group(1) if match else None

    @staticmethod
    def _attr_value(gift, kind):
        for attr in getattr(gift, "attributes", None) or []:
            if type(attr).__name__ == kind:
                return attr
        return None

    @staticmethod
    def _safe_filename(name):
        cleaned = re.sub(r"[^A-Za-z0-9_\-]+", "_", name or "")
        return cleaned.strip("_") or "nft"

    async def _resolve_slug(self, message):
        args = utils.get_args_raw(message)
        slug = self._extract_slug(args)
        if slug:
            return slug

        reply = await message.get_reply_message()
        if reply is None:
            return None

        action = getattr(reply, "action", None)
        if isinstance(action, MessageActionStarGiftUnique):
            gift = getattr(action, "gift", None)
            if isinstance(gift, StarGiftUnique) and getattr(gift, "slug", None):
                return gift.slug

        return self._extract_slug(getattr(reply, "raw_text", "") or "")

    async def _fetch_gift(self, slug):
        try:
            result = await self._client(GetUniqueStarGiftRequest(slug=slug))
        except Exception as exc:
            logger.exception("getUniqueStarGift(%s) failed: %s", slug, exc)
            return None

        gift = getattr(result, "gift", None)
        return gift if isinstance(gift, StarGiftUnique) else None

    async def _send_lottie(self, message, gift, slug):
        model = self._attr_value(gift, "StarGiftAttributeModel")
        if model is None or getattr(model, "document", None) is None:
            await utils.answer(message, self.strings("no_model"))
            return

        model_name = getattr(model, "name", None) or slug
        base = self._safe_filename(model_name)
        json_filename = f"{base}.json"

        await utils.answer(
            message,
            self.strings("uploading").format(name=utils.escape_html(json_filename)),
        )

        document = model.document
        tgs_buf = io.BytesIO()
        await self._client.download_file(document, tgs_buf)
        tgs_buf.seek(0)
        tgs_bytes = tgs_buf.getvalue()

        # .tgs — это gzip(Lottie JSON). Распаковываем, чтобы отдать именно
        # Lottie-анимацию (.json) и избежать рендеринга как стикера.
        try:
            json_bytes = gzip.decompress(tgs_bytes)
        except OSError:
            json_bytes = tgs_bytes
            json_filename = f"{base}.tgs"

        json_buf = io.BytesIO(json_bytes)
        json_buf.name = json_filename

        pattern = self._attr_value(gift, "StarGiftAttributePattern")
        backdrop = self._attr_value(gift, "StarGiftAttributeBackdrop")
        caption = self.strings("info").format(
            slug=utils.escape_html(slug),
            model=utils.escape_html(model_name),
            pattern=utils.escape_html(getattr(pattern, "name", "—") or "—"),
            backdrop=utils.escape_html(getattr(backdrop, "name", "—") or "—"),
        )

        reply = await message.get_reply_message()
        await message.client.send_file(
            message.peer_id,
            json_buf,
            caption=caption,
            attributes=[DocumentAttributeFilename(file_name=json_filename)],
            force_document=True,
            mime_type="application/json",
            reply_to=reply.id if reply else None,
        )

        try:
            await message.delete()
        except Exception:
            pass

        logger.info("NFTLottie: sent %s as file %s", slug, json_filename)

    @loader.command(ru_doc="<слаг|ссылка> — скачать Lottie из NFT-подарка как файл .tgs")
    async def nftlottie(self, message):
        """<slug|link> — download Lottie from an NFT gift and send it as a .tgs file"""
        slug = await self._resolve_slug(message)
        if not slug:
            await utils.answer(message, self.strings("no_args"))
            return

        await utils.answer(
            message,
            self.strings("fetching").format(slug=utils.escape_html(slug)),
        )

        gift = await self._fetch_gift(slug)
        if gift is None:
            await utils.answer(
                message,
                self.strings("not_found").format(slug=utils.escape_html(slug)),
            )
            return

        try:
            await self._send_lottie(message, gift, slug)
        except Exception as exc:
            logger.exception("NFTLottie send failed: %s", exc)
            await utils.answer(
                message,
                self.strings("error").format(err=utils.escape_html(str(exc))),
            )
