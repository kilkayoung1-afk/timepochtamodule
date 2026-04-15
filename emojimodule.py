# meta developer: @Kilka_Youngv
# requires: Pillow imageio numpy

__version__ = (1, 0, 1)

import os
import io
import asyncio
import random
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import imageio
import tempfile

from .. import loader, utils
from telethon.tl.functions.stickers import CreateStickerSetRequest
from telethon.tl.types import InputStickerSetItem, InputStickerSetEmpty


def register(cb):
    cb(EmojiBumMod())


COLORS = [
    "#FF0066", "#00FFCC", "#FF6600", "#FFFF00", "#00CCFF",
    "#FF00FF", "#00FF66", "#FF3300", "#0099FF", "#FFCC00",
    "#FF0099", "#33FF00", "#9900FF", "#FF9900", "#00FF99",
    "#FF0033", "#00FFFF", "#FF6633", "#9933FF", "#FF3366",
]

EFFECTS = ["glow", "wave", "pulse", "rotate", "bounce", "neon", "fire", "ice", "matrix", "rainbow"]


class AnimationGenerator:
    def __init__(self, text: str, width: int = 100, height: int = 100, frames: int = 30):
        self.text = text[:8]
        self.width = width
        self.height = height
        self.frames = frames
        self.font_size = self._calc_font_size()

    def _calc_font_size(self):
        base = min(self.width, self.height)
        length = len(self.text)
        if length <= 2:
            return int(base * 0.55)
        elif length <= 4:
            return int(base * 0.38)
        elif length <= 6:
            return int(base * 0.28)
        else:
            return int(base * 0.22)

    def _get_font(self, size=None):
        if size is None:
            size = self.font_size
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
        ]
        for path in font_paths:
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
        return ImageFont.load_default()

    def _draw_text_centered(self, draw, text, font, color, offset_x=0, offset_y=0):
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
        except Exception:
            tw, th = font.getsize(text)
        x = (self.width - tw) / 2 + offset_x
        y = (self.height - th) / 2 + offset_y
        draw.text((x, y), text, font=font, fill=color)

    def _hex_to_rgb(self, hex_color):
        h = hex_color.lstrip("#")
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

    def _hsv_to_rgb(self, h, s, v):
        h = h % 360
        c = v * s
        x = c * (1 - abs((h / 60) % 2 - 1))
        m = v - c
        if h < 60:
            r, g, b = c, x, 0
        elif h < 120:
            r, g, b = x, c, 0
        elif h < 180:
            r, g, b = 0, c, x
        elif h < 240:
            r, g, b = 0, x, c
        elif h < 300:
            r, g, b = x, 0, c
        else:
            r, g, b = c, 0, x
        return int((r + m) * 255), int((g + m) * 255), int((b + m) * 255)

    def effect_glow(self, frame_idx):
        img = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 255))
        draw = ImageDraw.Draw(img)
        font = self._get_font()
        t = frame_idx / self.frames
        alpha = int(128 + 127 * math.sin(t * 2 * math.pi))
        color = COLORS[frame_idx % len(COLORS)]
        rgb = self._hex_to_rgb(color)
        for offset in [(2, 2), (-2, 2), (2, -2), (-2, -2), (3, 0), (-3, 0), (0, 3), (0, -3)]:
            self._draw_text_centered(draw, self.text, font, (*rgb, alpha // 2), offset[0], offset[1])
        self._draw_text_centered(draw, self.text, font, (255, 255, 255, 255))
        return img

    def effect_wave(self, frame_idx):
        img = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 255))
        draw = ImageDraw.Draw(img)
        font = self._get_font()
        t = frame_idx / self.frames
        offset_y = int(8 * math.sin(t * 2 * math.pi))
        colors = ["#FF0066", "#00FFCC", "#FFFF00"]
        color_idx = int(t * len(colors)) % len(colors)
        color = self._hex_to_rgb(colors[color_idx])
        self._draw_text_centered(draw, self.text, font, (*color, 255), 0, offset_y)
        return img

    def effect_pulse(self, frame_idx):
        t = frame_idx / self.frames
        scale = 0.85 + 0.15 * math.sin(t * 2 * math.pi)
        size = int(self.font_size * scale)
        img = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 255))
        draw = ImageDraw.Draw(img)
        font = self._get_font(max(8, size))
        color = self._hex_to_rgb(COLORS[frame_idx % len(COLORS)])
        self._draw_text_centered(draw, self.text, font, (*color, 255))
        return img

    def effect_rotate(self, frame_idx):
        t = frame_idx / self.frames
        angle = t * 360
        base = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 255))
        txt_img = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(txt_img)
        font = self._get_font()
        color = self._hex_to_rgb(COLORS[int(t * len(COLORS)) % len(COLORS)])
        self._draw_text_centered(draw, self.text, font, (*color, 255))
        rotated = txt_img.rotate(angle, resample=Image.BICUBIC)
        base.paste(rotated, (0, 0), rotated)
        return base

    def effect_bounce(self, frame_idx):
        t = frame_idx / self.frames
        offset_y = int(-12 * abs(math.sin(t * 2 * math.pi)))
        img = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 255))
        draw = ImageDraw.Draw(img)
        font = self._get_font()
        color = self._hex_to_rgb(COLORS[frame_idx % len(COLORS)])
        self._draw_text_centered(draw, self.text, font, (*color, 255), 0, offset_y)
        return img

    def effect_neon(self, frame_idx):
        img = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 255))
        draw = ImageDraw.Draw(img)
        font = self._get_font()
        t = frame_idx / self.frames
        flicker = random.uniform(0.8, 1.0) if random.random() > 0.1 else random.uniform(0.3, 0.6)
        alpha = int(255 * flicker)
        neon_colors = ["#FF00FF", "#00FFFF", "#FF0066"]
        c = self._hex_to_rgb(neon_colors[int(t * 3) % 3])
        for d in range(4, 0, -1):
            a = int(alpha * (d / 4) * 0.4)
            for ox, oy in [(d, 0), (-d, 0), (0, d), (0, -d)]:
                self._draw_text_centered(draw, self.text, font, (*c, a), ox, oy)
        self._draw_text_centered(draw, self.text, font, (255, 255, 255, alpha))
        return img

    def effect_fire(self, frame_idx):
        img = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 255))
        draw = ImageDraw.Draw(img)
        font = self._get_font()
        t = frame_idx / self.frames
        fire_colors = [(255, 0, 0), (255, 80, 0), (255, 160, 0), (255, 220, 0), (255, 255, 100)]
        idx = int(t * len(fire_colors) * 2) % len(fire_colors)
        c = fire_colors[idx]
        flicker_x = random.randint(-2, 2)
        flicker_y = random.randint(-3, 0)
        self._draw_text_centered(draw, self.text, font, (*c, 255), flicker_x, flicker_y)
        return img

    def effect_ice(self, frame_idx):
        img = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 255))
        draw = ImageDraw.Draw(img)
        font = self._get_font()
        t = frame_idx / self.frames
        ice_colors = [(200, 240, 255), (150, 220, 255), (100, 200, 255), (180, 240, 255)]
        c = ice_colors[int(t * len(ice_colors)) % len(ice_colors)]
        shimmer = int(30 * math.sin(t * 4 * math.pi))
        for ox, oy in [(1, 1), (-1, -1), (1, -1), (-1, 1)]:
            self._draw_text_centered(draw, self.text, font, (200, 230, 255, 80), ox, oy)
        self._draw_text_centered(draw, self.text, font, (min(255, c[0] + shimmer), min(255, c[1] + shimmer), 255, 255))
        return img

    def effect_matrix(self, frame_idx):
        img = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 255))
        draw = ImageDraw.Draw(img)
        font = self._get_font()
        t = frame_idx / self.frames
        green = int(150 + 105 * math.sin(t * 2 * math.pi))
        self._draw_text_centered(draw, self.text, font, (0, green, 0, 100), 0, 2)
        self._draw_text_centered(draw, self.text, font, (0, 255, 0, 255))
        return img

    def effect_rainbow(self, frame_idx):
        img = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 255))
        draw = ImageDraw.Draw(img)
        font = self._get_font()
        t = (frame_idx / self.frames + 0.01) % 1.0
        hue = t * 360
        r, g, b = self._hsv_to_rgb(hue, 1.0, 1.0)
        self._draw_text_centered(draw, self.text, font, (r, g, b, 255))
        return img

    def get_effect_func(self, effect_name):
        mapping = {
            "glow": self.effect_glow,
            "wave": self.effect_wave,
            "pulse": self.effect_pulse,
            "rotate": self.effect_rotate,
            "bounce": self.effect_bounce,
            "neon": self.effect_neon,
            "fire": self.effect_fire,
            "ice": self.effect_ice,
            "matrix": self.effect_matrix,
            "rainbow": self.effect_rainbow,
        }
        return mapping.get(effect_name, self.effect_glow)

    def generate_webp(self, effect_name: str) -> bytes:
        effect_func = self.get_effect_func(effect_name)
        frames_list = []
        for i in range(self.frames):
            frame = effect_func(i)
            frames_list.append(frame)

        buf = io.BytesIO()
        frames_list[0].save(
            buf,
            format="WEBP",
            save_all=True,
            append_images=frames_list[1:],
            loop=0,
            duration=int(1000 / 15),
        )
        buf.seek(0)
        return buf.read()


@loader.tds
class EmojiBumMod(loader.Module):
    """🎨 Создание премиум анимированных эмодзи и стикеров | by @Kilka_Youngv"""

    strings = {
        "name": "EmojiBum",
        "no_text": "❌ <b>Введите текст до 8 символов!</b>",
        "text_too_long": "❌ <b>Текст слишком длинный! Максимум 8 символов.</b>",
        "generating": "⚙️ <b>Генерирую анимации... [{}/90]</b>",
        "uploading": "📤 <b>Загружаю файлы... [{}/90]</b>",
        "creating": "🛠 <b>Создаю пак в Telegram...</b>",
        "done_emoji": (
            "✅ <b>Эмодзи пак создан!</b>\n"
            "📦 <b>Имя:</b> <code>{}</code>\n"
            "🔗 <a href='https://t.me/addemoji/{}'>Добавить пак</a>"
        ),
        "done_sticker": (
            "✅ <b>Стикер пак создан!</b>\n"
            "📦 <b>Имя:</b> <code>{}</code>\n"
            "🔗 <a href='https://t.me/addstickers/{}'>Добавить пак</a>"
        ),
        "error": "❌ <b>Ошибка:</b> <code>{}</code>",
        "need_premium": "⭐ <b>Для эмодзи паков нужен Telegram Premium!</b>",
        "pack_exists": "⚠️ <b>Пак с таким именем занят, генерирую новое имя...</b>",
        "start": "🎨 <b>EmojiBum запущен для текста:</b> <code>{}</code>",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "frames",
                20,
                "Количество кадров анимации",
                validator=loader.validators.Integer(minimum=10, maximum=50),
            ),
            loader.ConfigValue(
                "emoji_size",
                100,
                "Размер эмодзи в пикселях",
                validator=loader.validators.Integer(minimum=50, maximum=100),
            ),
            loader.ConfigValue(
                "sticker_size",
                512,
                "Размер стикера в пикселях",
                validator=loader.validators.Integer(minimum=256, maximum=512),
            ),
        )

    async def client_ready(self, client, db):
        self._client = client
        self._me = await client.get_me()

    def _make_short_name(self, text: str, tag: str) -> str:
        safe = "".join(c for c in text.lower() if c.isalnum()) or "pack"
        safe = safe[:8]
        uid = self._me.username or str(self._me.id)
        rand = random.randint(100, 999)
        name = f"{safe}{tag}{rand}_{uid}"
        # Telegram ограничение: только a-z, 0-9, _
        name = "".join(c if (c.isalnum() or c == "_") else "_" for c in name)
        return name[:32]

    async def _upload_sticker(self, data: bytes, name: str):
        return await self._client.upload_file(
            io.BytesIO(data),
            file_name=name,
        )

    async def _create_pack(self, title: str, short_name: str, stickers: list, is_emoji: bool):
        """Создание пака через CreateStickerSetRequest с правильными параметрами"""
        import inspect
        sig = inspect.signature(CreateStickerSetRequest.__init__)
        params = list(sig.parameters.keys())

        # Базовые параметры которые точно есть
        kwargs = {
            "user_id": self._me.id,
            "title": title,
            "short_name": short_name,
            "stickers": stickers,
        }

        # Добавляем emojis только если поддерживается
        if "emojis" in params and is_emoji:
            kwargs["emojis"] = True

        return await self._client(CreateStickerSetRequest(**kwargs))

    async def _generate_and_upload(self, message, text: str, size: int, tag: str, is_emoji: bool):
        title_type = "Emoji" if is_emoji else "Sticker"
        title = f"{text} {title_type} Pack"

        generator = AnimationGenerator(
            text=text,
            width=size,
            height=size,
            frames=self.config["frames"],
        )

        effects = EFFECTS * 9  # 10 эффектов × 9 = 90

        # Генерация
        raw_list = []
        for i, effect in enumerate(effects):
            if i % 15 == 0:
                await utils.answer(message, self.strings["generating"].format(i + 1))

            webp = await asyncio.get_event_loop().run_in_executor(
                None, generator.generate_webp, effect
            )
            raw_list.append(webp)

        # Загрузка файлов
        uploaded = []
        for i, data in enumerate(raw_list):
            if i % 15 == 0:
                await utils.answer(message, self.strings["uploading"].format(i + 1))

            file = await self._upload_sticker(data, f"sticker_{i}.webp")
            uploaded.append(
                InputStickerSetItem(
                    document=file,
                    emoji="⭐",
                )
            )

        await utils.answer(message, self.strings["creating"])

        # Создание пака
        short_name = self._make_short_name(text, tag)

        for attempt in range(3):
            try:
                await self._create_pack(title, short_name, uploaded, is_emoji)
                return short_name
            except Exception as e:
                err = str(e)
                if "SHORT_NAME_OCCUPIED" in err or "SHORT_NAME_INVALID" in err:
                    await utils.answer(message, self.strings["pack_exists"])
                    short_name = self._make_short_name(text, f"{tag}{attempt+2}")
                    await asyncio.sleep(1)
                    continue
                elif "STICKERS_TOO_MUCH" in err:
                    # Обрезаем до 50
                    uploaded = uploaded[:50]
                    continue
                elif "premium" in err.lower() and is_emoji:
                    await utils.answer(message, self.strings["need_premium"])
                    return None
                else:
                    raise

        raise Exception("Не удалось создать пак после 3 попыток")

    @loader.command(ru_doc="<текст> — Создать эмодзи пак (90 штук)")
    async def emojibum(self, message):
        """<текст> — Создать премиум эмодзи пак с 90 анимированными эмодзи"""
        args = utils.get_args_raw(message)
        if not args:
            await utils.answer(message, self.strings["no_text"])
            return

        text = args.strip()
        if len(text) > 8:
            await utils.answer(message, self.strings["text_too_long"])
            return

        text = text[:8]
        await utils.answer(message, self.strings["start"].format(text))

        try:
            short_name = await self._generate_and_upload(
                message=message,
                text=text,
                size=self.config["emoji_size"],
                tag="emj",
                is_emoji=True,
            )
            if short_name:
                await utils.answer(
                    message,
                    self.strings["done_emoji"].format(short_name, short_name),
                )
        except Exception as e:
            await utils.answer(message, self.strings["error"].format(str(e)))

    @loader.command(ru_doc="<текст> — Создать стикер пак (90 штук)")
    async def stickerbum(self, message):
        """<текст> — Создать стикер пак с 90 анимированными стикерами"""
        args = utils.get_args_raw(message)
        if not args:
            await utils.answer(message, self.strings["no_text"])
            return

        text = args.strip()
        if len(text) > 8:
            await utils.answer(message, self.strings["text_too_long"])
            return

        text = text[:8]
        await utils.answer(message, self.strings["start"].format(text))

        try:
            short_name = await self._generate_and_upload(
                message=message,
                text=text,
                size=self.config["sticker_size"],
                tag="stk",
                is_emoji=False,
            )
            if short_name:
                await utils.answer(
                    message,
                    self.strings["done_sticker"].format(short_name, short_name),
                )
        except Exception as e:
            await utils.answer(message, self.strings["error"].format(str(e)))

    @loader.command(ru_doc="Информация о модуле EmojiBum")
    async def emojibuminfo(self, message):
        """Показать информацию о модуле EmojiBum"""
        await utils.answer(
            message,
            "🎨 <b>EmojiBum v1.0.1</b>\n"
            "👤 <b>Автор:</b> @Kilka_Young\n\n"
            "📌 <b>Команды:</b>\n"
            "• <code>.emojibum [текст]</code> — эмодзи пак (90 шт)\n"
            "• <code>.stickerbum [текст]</code> — стикер пак (90 шт)\n\n"
            "🎭 <b>Эффекты (10 шт × 9 = 90):</b>\n"
            "🌟 Glow • 🌊 Wave • 💫 Pulse • 🔄 Rotate • ⬆️ Bounce\n"
            "💜 Neon • 🔥 Fire • ❄️ Ice • 💚 Matrix • 🌈 Rainbow\n\n"
            "⚙️ Настройки: <code>.config EmojiBum</code>",
        )
