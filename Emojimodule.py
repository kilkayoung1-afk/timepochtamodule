# -*- coding: utf-8 -*-

# meta developer: @Kilka_Young
# scope: hikka_only
# requires: pillow

__version__ = (1, 0, 0)

"""
██╗  ██╗██╗██╗     ██╗  ██╗ █████╗       ██╗   ██╗ ██████╗ ██╗   ██╗███╗   ██╗ ██████╗
██║ ██╔╝██║██║     ██║ ██╔╝██╔══██╗      ╚██╗ ██╔╝██╔═══██╗██║   ██║████╗  ██║██╔════╝
█████╔╝ ██║██║     █████╔╝ ███████║       ╚████╔╝ ██║   ██║██║   ██║██╔██╗ ██║██║  ███╗
██╔═██╗ ██║██║     ██╔═██╗ ██╔══██║        ╚██╔╝  ██║   ██║██║   ██║██║╚██╗██║██║   ██║
██║  ██╗██║███████╗██║  ██╗██║  ██║         ██║   ╚██████╔╝╚██████╔╝██║ ╚████║╚██████╔╝
╚═╝  ╚═╝╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝         ╚═╝    ╚═════╝  ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝
                Модуль: EmojiPackMaker | Автор: @Kilka_Young
"""

import io
import time
import asyncio
from PIL import Image, ImageDraw, ImageFont

from telethon.tl.functions.stickers import CreateStickerSetRequest
from telethon.tl.functions.messages import UploadMediaRequest
from telethon.tl.types import (
    InputStickerSetItem,
    InputDocument,
    InputMediaUploadedDocument,
    DocumentAttributeFilename,
    DocumentAttributeSticker,
    InputStickerSetEmpty,
)

from .. import loader, utils


# ╔══════════════════════════════════════════════════════════════╗
# ║                    КОНСТАНТЫ ШАБЛОНА                        ║
# ╚══════════════════════════════════════════════════════════════╝

# Размер эмодзи (100x100 — стандарт Telegram для кастомных эмодзи)
EMOJI_SIZE = 100

# Символ-заглушка для поля emoji у стикера
EMOJI_CHAR = "⭐"

# Пути к шрифтам (перебираются по очереди)
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
]

# 49 оттенков фона (HSL: hue от 0 до 360, равномерно)
PALETTE_HSL = [(int(i * 360 / 49), 65, 38) for i in range(49)]


# ╔══════════════════════════════════════════════════════════════╗
# ║                    ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ                  ║
# ╚══════════════════════════════════════════════════════════════╝

def _hsl_to_rgb(h: int, s: int, l: int):
    """Конвертация HSL → RGB (значения 0-255)."""
    s /= 100
    l /= 100
    c = (1 - abs(2 * l - 1)) * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = l - c / 2
    if   h < 60:  r, g, b = c, x, 0
    elif h < 120: r, g, b = x, c, 0
    elif h < 180: r, g, b = 0, c, x
    elif h < 240: r, g, b = 0, x, c
    elif h < 300: r, g, b = x, 0, c
    else:          r, g, b = c, 0, x
    return (int((r + m) * 255), int((g + m) * 255), int((b + m) * 255))


def _load_font(size: int):
    """Загружает жирный шрифт из системных путей, иначе дефолтный."""
    for path in FONT_PATHS:
        try:
            return ImageFont.truetype(path, size), path
        except Exception:
            continue
    return ImageFont.load_default(), None


def _make_emoji_image(text: str, index: int) -> bytes:
    """
    Генерирует одно эмодзи 100×100 WEBP.
    Каждое изображение имеет уникальный оттенок фона (index 0-48),
    но одинаковую надпись — это гарантирует уникальность файлов.
    """
    sz = EMOJI_SIZE
    img = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # ── Фон: цветной круг ────────────────────────────────────────
    h, s, l = PALETTE_HSL[index]
    r, g, b = _hsl_to_rgb(h, s, l)
    pad = 3
    draw.ellipse([pad, pad, sz - pad, sz - pad], fill=(r, g, b, 255))

    # Светлая обводка
    lr, lg, lb = min(255, r + 70), min(255, g + 70), min(255, b + 70)
    draw.ellipse(
        [pad, pad, sz - pad, sz - pad],
        outline=(lr, lg, lb, 210),
        width=3,
    )

    # ── Шрифт: автоподбор размера ────────────────────────────────
    font_size = 30
    font, font_path = _load_font(font_size)
    max_w = sz - 16

    for _ in range(6):
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        if tw <= max_w:
            break
        font_size = max(7, int(font_size * max_w / tw * 0.88))
        if font_path:
            try:
                font = ImageFont.truetype(font_path, font_size)
            except Exception:
                break
        else:
            break

    # ── Текст: центрирование ─────────────────────────────────────
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (sz - tw) // 2 - bbox[0]
    y = (sz - th) // 2 - bbox[1]

    # Тень
    draw.text((x + 1, y + 1), text, font=font, fill=(0, 0, 0, 160))
    # Основной текст
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))

    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=92)
    buf.seek(0)
    return buf.read()


# ╔══════════════════════════════════════════════════════════════╗
# ║                         МОДУЛЬ                              ║
# ╚══════════════════════════════════════════════════════════════╝

@loader.tds
class EmojiPackMakerMod(loader.Module):
    """Создаёт пак из 49 кастомных эмодзи с вашей надписью на красивом цветном фоне"""

    strings = {
        "name": "EmojiPackMaker",

        "no_text": (
            "❌ <b>Укажи текст для эмодзи!</b>\n\n"
            "Использование: <code>.makeemoji ГГ</code>\n"
            "Или: <code>.makeemoji LOL</code>"
        ),

        "start": (
            "🎨 <b>Запускаю генерацию пака...</b>\n\n"
            "📝 Надпись: <code>{text}</code>\n"
            "📦 Стикеров: <b>49 шт.</b>\n\n"
            "<i>Это займёт около минуты...</i>"
        ),

        "uploading": (
            "📤 <b>Загружаю эмодзи...</b>\n\n"
            "📝 Надпись: <code>{text}</code>\n"
            "▓ Прогресс: <b>{done}/49</b>  [{bar}]"
        ),

        "creating": (
            "✨ <b>Финальный шаг — создаю пак...</b>\n\n"
            "📝 Надпись: <code>{text}</code>\n"
            "⏳ Почти готово!"
        ),

        "done": (
            "✅ <b>Пак кастомных эмодзи создан!</b>\n\n"
            "📝 <b>Надпись:</b> <code>{text}</code>\n"
            "📦 <b>Название:</b> <code>{title}</code>\n"
            "🔢 <b>Кол-во:</b> 49 эмодзи\n\n"
            "🔗 <b>Добавить пак:</b>\n"
            "<a href='https://t.me/addemoji/{name}'>t.me/addemoji/{name}</a>"
        ),

        "error": (
            "❌ <b>Ошибка при создании пака:</b>\n"
            "<code>{error}</code>"
        ),
    }

    # ── Вспомогательный метод: полоса прогресса ──────────────────
    @staticmethod
    def _progress_bar(done: int, total: int = 49, width: int = 10) -> str:
        filled = int(width * done / total)
        return "█" * filled + "░" * (width - filled)

    # ── Основная команда ─────────────────────────────────────────
    @loader.command(
        ru_doc="<текст> — Создать пак из 49 кастомных эмодзи с вашей надписью"
    )
    async def makeemoji(self, message):
        """<текст> — Создать пак из 49 кастомных эмодзи с вашей надписью"""

        text = utils.get_args_raw(message).strip()
        if not text:
            await utils.answer(message, self.strings["no_text"])
            return

        await utils.answer(message, self.strings["start"].format(text=text))

        # Формируем короткое имя пака (уникальное, до 32 символов)
        ts = int(time.time()) % 10_000_000
        me = await self._client.get_me()
        short_name = f"emj{ts}u{me.id % 9999}"
        # Telegram: short_name 1-64 символа, только a-z0-9_
        short_name = short_name[:32]

        me_input = await self._client.get_input_entity(me)
        sticker_items = []

        try:
            for i in range(49):
                # Обновляем прогресс каждые 3 стикера
                if i % 3 == 0:
                    await utils.answer(
                        message,
                        self.strings["uploading"].format(
                            text=text,
                            done=i,
                            bar=self._progress_bar(i),
                        ),
                    )

                # Генерируем изображение (уникальный оттенок для каждого)
                img_bytes = _make_emoji_image(text, i)

                # Загружаем на серверы Telegram
                uploaded = await self._client.upload_file(
                    io.BytesIO(img_bytes),
                    file_name=f"emoji_{i:02d}.webp",
                )

                # Сохраняем как документ-стикер, получаем document ref
                media_result = await self._client(
                    UploadMediaRequest(
                        peer=me_input,
                        media=InputMediaUploadedDocument(
                            file=uploaded,
                            mime_type="image/webp",
                            attributes=[
                                DocumentAttributeFilename(
                                    file_name=f"emoji_{i:02d}.webp"
                                ),
                                DocumentAttributeSticker(
                                    alt=EMOJI_CHAR,
                                    stickerset=InputStickerSetEmpty(),
                                ),
                            ],
                        ),
                    )
                )

                doc = media_result.document
                sticker_items.append(
                    InputStickerSetItem(
                        document=InputDocument(
                            id=doc.id,
                            access_hash=doc.access_hash,
                            file_reference=doc.file_reference,
                        ),
                        emoji=EMOJI_CHAR,
                    )
                )

                # Антифлуд-пауза каждые 5 загрузок
                if (i + 1) % 5 == 0:
                    await asyncio.sleep(1.2)

            # Финальный прогресс
            await utils.answer(
                message,
                self.strings["uploading"].format(
                    text=text,
                    done=49,
                    bar=self._progress_bar(49),
                ),
            )
            await asyncio.sleep(0.5)

            # Создаём пак
            await utils.answer(
                message,
                self.strings["creating"].format(text=text),
            )

            title = f"{text[:40]} Emoji Pack"

            result = await self._client(
                CreateStickerSetRequest(
                    user_id=me_input,
                    title=title,
                    short_name=short_name,
                    stickers=sticker_items,
                    emojis=True,   # ← кастомные эмодзи!
                )
            )

            await utils.answer(
                message,
                self.strings["done"].format(
                    text=text,
                    title=result.set.title,
                    name=result.set.short_name,
                ),
            )

        except Exception as e:
            await utils.answer(
                message,
                self.strings["error"].format(error=str(e)),
            )
