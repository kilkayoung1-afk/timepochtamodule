# meta developer: @Kilka_Youngv
# meta banner: https://i.imgur.com/placeholder.png
# requires: Pillow imageio numpy

__version__ = (1, 0, 0)

import os
import io
import asyncio
import random
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio
import tempfile
import zipfile

from .. import loader, utils
from telethon.tl.functions.stickers import (
    CreateStickerSetRequest,
    AddStickerToSetRequest,
)
from telethon.tl.functions.messages import GetStickerSetRequest
from telethon.tl.types import (
    InputStickerSetShortName,
    InputDocument,
    InputStickerSetItem,
)
from telethon.tl.functions.upload import GetFileRequest


def register(cb):
    cb(EmojiBumMod())


COLORS = [
    "#FF0066", "#00FFCC", "#FF6600", "#FFFF00", "#00CCFF",
    "#FF00FF", "#00FF66", "#FF3300", "#0099FF", "#FFCC00",
    "#FF0099", "#33FF00", "#9900FF", "#FF9900", "#00FF99",
    "#FF0033", "#00FFFF", "#FF6633", "#9933FF", "#FF3366",
]

FONT_STYLES = ["bold", "normal"]
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
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
        except Exception:
            try:
                return ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", size)
            except Exception:
                return ImageFont.load_default()

    def _draw_text_centered(self, draw, text, font, color, offset_x=0, offset_y=0):
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
        except Exception:
            tw, th = draw.textsize(text, font=font)
        x = (self.width - tw) / 2 + offset_x
        y = (self.height - th) / 2 + offset_y
        draw.text((x, y), text, font=font, fill=color)

    def _hex_to_rgb(self, hex_color):
        h = hex_color.lstrip("#")
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

    def _interpolate_color(self, c1, c2, t):
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        return (r, g, b, 255)

    # ===== EFFECTS =====

    def effect_glow(self, frame_idx):
        img = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 255))
        draw = ImageDraw.Draw(img)
        font = self._get_font()
        t = frame_idx / self.frames
        alpha = int(128 + 127 * math.sin(t * 2 * math.pi))
        color = random.choice(COLORS)
        rgb = self._hex_to_rgb(color)
        glow_color = (*rgb, alpha)
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
        color = self._hex_to_rgb(random.choice(COLORS[:5]))
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
        shadow_alpha = int(80 * (1 - abs(math.sin(t * 2 * math.pi))))
        self._draw_text_centered(draw, self.text, font, (100, 100, 100, shadow_alpha), 2, 2 - offset_y)
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

    def generate_webm(self, effect_name: str) -> bytes:
        effect_func = self.get_effect_func(effect_name)
        frames_list = []
        for i in range(self.frames):
            frame = effect_func(i)
            frames_list.append(np.array(frame))

        buf = io.BytesIO()
        writer = imageio.get_writer(
            buf,
            format="gif",
            mode="I",
            fps=15,
            loop=0,
        )
        for frame_arr in frames_list:
            writer.append_data(frame_arr)
        writer.close()
        buf.seek(0)
        return buf.read()

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
        "generating": "⚙️ <b>Генерирую {} анимаций... Это займёт немного времени.</b>",
        "uploading_emoji": "📤 <b>Загружаю эмодзи пак ({}/90)...</b>",
        "uploading_sticker": "📤 <b>Загружаю стикер пак ({}/90)...</b>",
        "done_emoji": "✅ <b>Эмодзи пак создан!</b>\n📦 <b>Короткое имя:</b> <code>{}</code>",
        "done_sticker": "✅ <b>Стикер пак создан!</b>\n📦 <b>Короткое имя:</b> <code>{}</code>",
        "error": "❌ <b>Ошибка: {}</b>",
        "need_premium": "⭐ <b>Для создания эмодзи паков нужен Telegram Premium!</b>",
        "start_emoji": "🎭 <b>Начинаю создание эмодзи пака...</b>",
        "start_sticker": "🎭 <b>Начинаю создание стикер пака...</b>",
        "pack_exists": "⚠️ <b>Пак с таким именем уже существует. Генерирую новое имя...</b>",
    }

    strings_ru = {
        "no_text": "❌ <b>Введите текст до 8 символов!</b>",
        "text_too_long": "❌ <b>Текст слишком длинный! Максимум 8 символов.</b>",
        "generating": "⚙️ <b>Генерирую {} анимаций... Это займёт немного времени.</b>",
        "uploading_emoji": "📤 <b>Загружаю эмодзи пак ({}/90)...</b>",
        "uploading_sticker": "📤 <b>Загружаю стикер пак ({}/90)...</b>",
        "done_emoji": "✅ <b>Эмодзи пак создан!</b>\n📦 <b>Короткое имя:</b> <code>{}</code>",
        "done_sticker": "✅ <b>Стикер пак создан!</b>\n📦 <b>Загружаю стикер пак:</b> <code>{}</code>",
        "error": "❌ <b>Ошибка: {}</b>",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "default_frames",
                30,
                "Количество кадров в анимации",
                validator=loader.validators.Integer(minimum=10, maximum=60),
            ),
            loader.ConfigValue(
                "emoji_size",
                100,
                "Размер эмодзи (px)",
                validator=loader.validators.Integer(minimum=50, maximum=100),
            ),
            loader.ConfigValue(
                "sticker_size",
                512,
                "Размер стикера (px)",
                validator=loader.validators.Integer(minimum=256, maximum=512),
            ),
        )

    async def client_ready(self, client, db):
        self._client = client
        self._me = await client.get_me()

    def _generate_short_name(self, text: str, suffix: str = "") -> str:
        safe = "".join(c for c in text.lower() if c.isalnum())[:8]
        if not safe:
            safe = "emoji"
        rand = random.randint(1000, 9999)
        bot_username = "Stickers"
        name = f"{safe}_{suffix}_{rand}_by_{self._me.username or 'user'}"
        return name[:64]

    async def _upload_file(self, data: bytes, filename: str):
        return await self._client.upload_file(
            io.BytesIO(data),
            file_name=filename,
        )

    @loader.command(ru_doc="<текст> — Создать эмодзи пак (90 эмодзи)")
    async def emojibum(self, message):
        """<текст> — Создать премиум эмодзи пак с 90 анимированными эмодзи"""
        args = utils.get_args_raw(message)
        if not args:
            await utils.answer(message, self.strings["no_text"])
            return
        text = args.strip()[:8]
        if len(args.strip()) > 8:
            await utils.answer(message, self.strings["text_too_long"])
            return

        await utils.answer(message, self.strings["start_emoji"])
        await asyncio.sleep(0.5)
        await utils.answer(message, self.strings["generating"].format(90))

        try:
            generator = AnimationGenerator(
                text,
                width=self.config["emoji_size"],
                height=self.config["emoji_size"],
                frames=self.config["default_frames"],
            )

            stickers_data = []
            effects = EFFECTS * 9

            for i, effect in enumerate(effects):
                webp_data = await asyncio.get_event_loop().run_in_executor(
                    None, generator.generate_webp, effect
                )
                stickers_data.append(webp_data)
                if i % 10 == 0:
                    await utils.answer(message, self.strings["uploading_emoji"].format(i + 1))

            await utils.answer(message, self.strings["uploading_emoji"].format(90))

            short_name = self._generate_short_name(text, "emj")

            uploaded = []
            for i, data in enumerate(stickers_data):
                f = await self._upload_file(data, f"emoji_{i}.webp")
                uploaded.append(
                    InputStickerSetItem(
                        document=await self._client.upload_file(io.BytesIO(data), file_name=f"e{i}.webp"),
                        emoji="⭐",
                    )
                )

            try:
                result = await self._client(
                    CreateStickerSetRequest(
                        user_id=self._me.id,
                        title=f"{text} Emoji Pack",
                        short_name=short_name,
                        stickers=uploaded,
                        animated=False,
                        videos=False,
                        emojis=True,
                    )
                )
                await utils.answer(
                    message,
                    self.strings["done_emoji"].format(short_name)
                    + f"\n🔗 <a href='https://t.me/addemoji/{short_name}'>Добавить пак</a>",
                )
            except Exception as e:
                err = str(e)
                if "SHORT_NAME_OCCUPIED" in err:
                    short_name = self._generate_short_name(text, "emj2")
                    await utils.answer(message, self.strings["pack_exists"])
                    result = await self._client(
                        CreateStickerSetRequest(
                            user_id=self._me.id,
                            title=f"{text} Emoji Pack",
                            short_name=short_name,
                            stickers=uploaded,
                            animated=False,
                            videos=False,
                            emojis=True,
                        )
                    )
                    await utils.answer(
                        message,
                        self.strings["done_emoji"].format(short_name)
                        + f"\n🔗 <a href='https://t.me/addemoji/{short_name}'>Добавить пак</a>",
                    )
                elif "PEER_ID_INVALID" in err or "premium" in err.lower():
                    await utils.answer(message, self.strings["need_premium"])
                else:
                    raise

        except Exception as e:
            await utils.answer(message, self.strings["error"].format(str(e)))

    @loader.command(ru_doc="<текст> — Создать стикер пак (90 стикеров)")
    async def stickerbum(self, message):
        """<текст> — Создать стикер пак с 90 анимированными стикерами"""
        args = utils.get_args_raw(message)
        if not args:
            await utils.answer(message, self.strings["no_text"])
            return
        text = args.strip()[:8]
        if len(args.strip()) > 8:
            await utils.answer(message, self.strings["text_too_long"])
            return

        await utils.answer(message, self.strings["start_sticker"])
        await asyncio.sleep(0.5)
        await utils.answer(message, self.strings["generating"].format(90))

        try:
            generator = AnimationGenerator(
                text,
                width=self.config["sticker_size"],
                height=self.config["sticker_size"],
                frames=self.config["default_frames"],
            )

            stickers_data = []
            effects = EFFECTS * 9

            for i, effect in enumerate(effects):
                webp_data = await asyncio.get_event_loop().run_in_executor(
                    None, generator.generate_webp, effect
                )
                stickers_data.append(webp_data)
                if i % 10 == 0:
                    await utils.answer(message, self.strings["uploading_sticker"].format(i + 1))

            await utils.answer(message, self.strings["uploading_sticker"].format(90))

            short_name = self._generate_short_name(text, "stk")

            uploaded = []
            for i, data in enumerate(stickers_data):
                uploaded.append(
                    InputStickerSetItem(
                        document=await self._client.upload_file(io.BytesIO(data), file_name=f"s{i}.webp"),
                        emoji="⭐",
                    )
                )

            try:
                result = await self._client(
                    CreateStickerSetRequest(
                        user_id=self._me.id,
                        title=f"{text} Sticker Pack",
                        short_name=short_name,
                        stickers=uploaded,
                        animated=False,
                        videos=False,
                        emojis=False,
                    )
                )
                await utils.answer(
                    message,
                    self.strings["done_sticker"].format(short_name)
                    + f"\n🔗 <a href='https://t.me/addstickers/{short_name}'>Добавить пак</a>",
                )
            except Exception as e:
                err = str(e)
                if "SHORT_NAME_OCCUPIED" in err:
                    short_name = self._generate_short_name(text, "stk2")
                    await utils.answer(message, self.strings["pack_exists"])
                    result = await self._client(
                        CreateStickerSetRequest(
                            user_id=self._me.id,
                            title=f"{text} Sticker Pack",
                            short_name=short_name,
                            stickers=uploaded,
                            animated=False,
                            videos=False,
                            emojis=False,
                        )
                    )
                    await utils.answer(
                        message,
                        self.strings["done_sticker"].format(short_name)
                        + f"\n🔗 <a href='https://t.me/addstickers/{short_name}'>Добавить пак</a>",
                    )
                else:
                    raise

        except Exception as e:
            await utils.answer(message, self.strings["error"].format(str(e)))

    @loader.command(ru_doc="Показать информацию о модуле")
    async def emojibuminfo(self, message):
        """Информация о EmojiBum"""
        await utils.answer(
            message,
            "🎨 <b>EmojiBum</b> — Генератор премиум эмодзи и стикеров\n\n"
            "👤 <b>Владелец:</b> @Kilka_Youngv\n"
            "📦 <b>Версия:</b> 1.0.0\n\n"
            "📝 <b>Команды:</b>\n"
            "• <code>.emojibum [текст]</code> — создать эмодзи пак (90 шт)\n"
            "• <code>.stickerbum [текст]</code> — создать стикер пак (90 шт)\n\n"
            "🎭 <b>Эффекты:</b>\n"
            "• 🌟 Glow (свечение)\n"
            "• 🌊 Wave (волна)\n"
            "• 💫 Pulse (пульсация)\n"
            "• 🔄 Rotate (вращение)\n"
            "• ⬆️ Bounce (прыжок)\n"
            "• 💜 Neon (неон)\n"
            "• 🔥 Fire (огонь)\n"
            "• ❄️ Ice (лёд)\n"
            "• 💚 Matrix (матрица)\n"
            "• 🌈 Rainbow (радуга)\n\n"
            "⚙️ Настройки через <code>.config EmojiBum</code>",
        )
