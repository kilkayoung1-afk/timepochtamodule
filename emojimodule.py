# meta developer: @your_username
# requires: Pillow

__version__ = (1, 0, 0)

from .. import loader, utils
from PIL import Image, ImageDraw, ImageFont
import io
import os
import asyncio
import math

@loader.tds
class PremiumEmojiMod(loader.Module):
    """Создание премиум эмодзи с текстом на анимированном чёрном фоне"""

    strings = {
        "name": "PremiumEmoji",
        "no_text": "❌ <b>Введите текст (до 8 символов)</b>",
        "too_long": "❌ <b>Текст слишком длинный! Максимум 8 символов</b>",
        "generating": "⏳ <b>Генерирую премиум эмодзи...</b>",
        "done": "✅ <b>Готово!</b>",
    }

    strings_ru = {
        "no_text": "❌ <b>Введите текст (до 8 символов)</b>",
        "too_long": "❌ <b>Текст слишком длинный! Максимум 8 символов</b>",
        "generating": "⏳ <b>Генерирую премиум эмодзи...</b>",
        "done": "✅ <b>Готово!</b>",
    }

    async def client_ready(self, client, db):
        self._client = client

    def _create_frame(
        self,
        text: str,
        frame_num: int,
        total_frames: int,
        size: int = 100,
    ) -> Image.Image:
        """Создание одного кадра анимации"""
        img = Image.new("RGBA", (size, size), (0, 0, 0, 255))
        draw = ImageDraw.Draw(img)

        # --- Анимированный фон: пульсирующие частицы ---
        progress = frame_num / total_frames
        angle = progress * 2 * math.pi

        # Градиентные круги (glow-эффект)
        for i in range(3):
            phase = angle + (i * 2 * math.pi / 3)
            cx = size // 2 + int(20 * math.cos(phase))
            cy = size // 2 + int(20 * math.sin(phase))
            radius = 35 + int(5 * math.sin(angle * 2 + i))

            alpha = int(60 + 40 * math.sin(angle + i))
            colors = [
                (138, 43, 226, alpha),   # фиолетовый
                (75, 0, 130, alpha),      # индиго
                (0, 191, 255, alpha),     # голубой
            ]
            color = colors[i % len(colors)]

            for r in range(radius, 0, -3):
                a = int(color[3] * (r / radius) * 0.5)
                draw.ellipse(
                    [cx - r, cy - r, cx + r, cy + r],
                    fill=(color[0], color[1], color[2], a),
                )

        # --- Звёздочки / частицы ---
        import random
        rng = random.Random(42)
        for _ in range(15):
            px = rng.randint(0, size)
            py = rng.randint(0, size)
            twinkle = abs(math.sin(angle * 3 + rng.random() * math.pi))
            alpha_star = int(200 * twinkle)
            star_color = rng.choice([
                (255, 255, 255, alpha_star),
                (200, 150, 255, alpha_star),
                (100, 200, 255, alpha_star),
            ])
            sr = rng.randint(1, 2)
            draw.ellipse(
                [px - sr, py - sr, px + sr, py + sr],
                fill=star_color,
            )

        # --- Кольцо вокруг ---
        ring_alpha = int(150 + 100 * math.sin(angle * 2))
        ring_color = (138, 43, 226, ring_alpha)
        ring_width = 2
        margin = 4
        draw.arc(
            [margin, margin, size - margin, size - margin],
            start=math.degrees(angle),
            end=math.degrees(angle) + 270,
            fill=ring_color,
            width=ring_width,
        )

        # --- Текст ---
        font_size = self._calc_font_size(text, size)
        font = self._get_font(font_size)

        # Тень
        shadow_offset = 2
        shadow_alpha = int(180 + 50 * math.sin(angle))

        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        tx = (size - text_w) // 2 - bbox[0]
        ty = (size - text_h) // 2 - bbox[1]

        # Glow текста
        glow_alpha = int(100 + 80 * math.sin(angle * 2))
        for offset in [(2, 2), (-2, -2), (2, -2), (-2, 2)]:
            draw.text(
                (tx + offset[0], ty + offset[1]),
                text,
                font=font,
                fill=(138, 43, 226, glow_alpha),
            )

        # Тень
        draw.text(
            (tx + shadow_offset, ty + shadow_offset),
            text,
            font=font,
            fill=(0, 0, 0, shadow_alpha),
        )

        # Основной текст с градиентом цвета
        text_r = int(200 + 55 * math.sin(angle))
        text_g = int(100 + 50 * math.cos(angle))
        text_b = 255
        draw.text(
            (tx, ty),
            text,
            font=font,
            fill=(text_r, text_g, text_b, 255),
        )

        return img

    def _calc_font_size(self, text: str, canvas_size: int) -> int:
        """Подбор размера шрифта"""
        length = len(text)
        if length <= 2:
            return 38
        elif length <= 4:
            return 28
        elif length <= 6:
            return 22
        else:
            return 16

    def _get_font(self, size: int) -> ImageFont.FreeTypeFont:
        """Получение шрифта"""
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
        for path in font_paths:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    continue
        return ImageFont.load_default()

    def _create_animated_gif(self, text: str) -> bytes:
        """Создание анимированного GIF"""
        total_frames = 24
        frames = []

        for i in range(total_frames):
            frame = self._create_frame(text, i, total_frames)
            frames.append(frame)

        buf = io.BytesIO()
        frames[0].save(
            buf,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            optimize=False,
            duration=60,
            loop=0,
            disposal=2,
        )
        buf.seek(0)
        return buf.read()

    def _create_animated_webp(self, text: str) -> bytes:
        """Создание анимированного WebP"""
        total_frames = 24
        frames = []

        for i in range(total_frames):
            frame = self._create_frame(text, i, total_frames)
            frames.append(frame)

        buf = io.BytesIO()
        frames[0].save(
            buf,
            format="WEBP",
            save_all=True,
            append_images=frames[1:],
            duration=60,
            loop=0,
            quality=90,
        )
        buf.seek(0)
        return buf.read()

    @loader.command(ru_doc="<текст> — Создать премиум эмодзи (до 8 символов)")
    async def pemoji(self, message):
        """<text> — Create premium animated emoji (up to 8 chars)"""
        args = utils.get_args_raw(message)

        if not args:
            await utils.answer(message, self.strings("no_text"))
            return

        text = args.strip()

        if len(text) > 8:
            await utils.answer(message, self.strings("too_long"))
            return

        await utils.answer(message, self.strings("generating"))

        try:
            gif_data = await asyncio.get_event_loop().run_in_executor(
                None, self._create_animated_gif, text
            )

            gif_buf = io.BytesIO(gif_data)
            gif_buf.name = f"pemoji_{text}.gif"
            gif_buf.seek(0)

            await message.delete()
            await self._client.send_file(
                message.peer_id,
                gif_buf,
                supports_streaming=True,
                caption=f"✨ <b>Premium Emoji:</b> <code>{text}</code>",
                parse_mode="html",
            )

        except Exception as e:
            await utils.answer(
                message,
                f"❌ <b>Ошибка:</b> <code>{e}</code>",
            )

    @loader.command(ru_doc="<текст> — Создать премиум эмодзи в формате WebP")
    async def pemojis(self, message):
        """<text> — Create premium animated sticker WebP (up to 8 chars)"""
        args = utils.get_args_raw(message)

        if not args:
            await utils.answer(message, self.strings("no_text"))
            return

        text = args.strip()

        if len(text) > 8:
            await utils.answer(message, self.strings("too_long"))
            return

        await utils.answer(message, self.strings("generating"))

        try:
            webp_data = await asyncio.get_event_loop().run_in_executor(
                None, self._create_animated_webp, text
            )

            webp_buf = io.BytesIO(webp_data)
            webp_buf.name = f"pemoji_{text}.webp"
            webp_buf.seek(0)

            await message.delete()
            await self._client.send_file(
                message.peer_id,
                webp_buf,
                supports_streaming=True,
                caption=f"✨ <b>Premium Sticker:</b> <code>{text}</code>",
                parse_mode="html",
            )

        except Exception as e:
            await utils.answer(
                message,
                f"❌ <b>Ошибка:</b> <code>{e}</code>",
            )
