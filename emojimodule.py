# meta developer: @your_username
# requires: Pillow imageio

__version__ = (1, 0, 0)

from .. import loader, utils
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import io
import os
import asyncio
import math
import random

@loader.tds
class PremiumEmojiMod(loader.Module):
    """Создание премиум анимированных стикеров с текстом на чёрном фоне"""

    strings = {
        "name": "PremiumEmoji",
        "no_text": "❌ <b>Введите текст (до 8 символов)</b>",
        "too_long": "❌ <b>Текст слишком длинный! Максимум 8 символов</b>",
        "generating": "⏳ <b>Генерирую премиум стикер...</b>",
    }

    strings_ru = {
        "no_text": "❌ <b>Введите текст (до 8 символов)</b>",
        "too_long": "❌ <b>Текст слишком длинный! Максимум 8 символов</b>",
        "generating": "⏳ <b>Генерирую премиум стикер...</b>",
    }

    async def client_ready(self, client, db):
        self._client = client

    def _get_font(self, size: int) -> ImageFont.FreeTypeFont:
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
        for path in font_paths:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    continue
        return ImageFont.load_default()

    def _calc_font_size(self, text: str, canvas: int) -> int:
        n = len(text)
        if n <= 2:
            return int(canvas * 0.38)
        elif n <= 4:
            return int(canvas * 0.28)
        elif n <= 6:
            return int(canvas * 0.22)
        return int(canvas * 0.16)

    def _draw_glow(self, draw, x, y, text, font, color, radius=8):
        """Рисует glow вокруг текста"""
        r, g, b = color
        for offset in range(radius, 0, -2):
            alpha = int(80 * (1 - offset / radius))
            for dx in range(-offset, offset + 1, offset):
                for dy in range(-offset, offset + 1, offset):
                    draw.text(
                        (x + dx, y + dy),
                        text,
                        font=font,
                        fill=(r, g, b, alpha),
                    )

    def _create_frame(
        self,
        text: str,
        frame_num: int,
        total_frames: int,
        size: int = 512,
    ) -> Image.Image:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 255))
        draw = ImageDraw.Draw(img)

        progress = frame_num / total_frames
        angle = progress * 2 * math.pi

        # --- Фоновые частицы (фиксированные по seed) ---
        rng = random.Random(777)
        for _ in range(30):
            px = rng.randint(5, size - 5)
            py = rng.randint(5, size - 5)
            twinkle = abs(math.sin(angle * 2 + rng.random() * math.pi * 2))
            a = int(220 * twinkle)
            cr = rng.choice([
                (255, 255, 255),
                (180, 120, 255),
                (100, 180, 255),
                (255, 200, 100),
            ])
            sr = rng.randint(1, 3)
            draw.ellipse(
                [px - sr, py - sr, px + sr, py + sr],
                fill=(cr[0], cr[1], cr[2], a),
            )

        # --- Пульсирующий фоновый glow ---
        glow_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow_layer)
        pulse = 0.5 + 0.5 * math.sin(angle * 2)

        for i, col in enumerate([
            (138, 43, 226),
            (75, 0, 230),
            (0, 150, 255),
        ]):
            phase = angle + i * (2 * math.pi / 3)
            cx = size // 2 + int(size * 0.12 * math.cos(phase))
            cy = size // 2 + int(size * 0.12 * math.sin(phase))
            r = int(size * 0.28 + size * 0.05 * pulse)
            for step in range(r, 0, -8):
                a = int(55 * (step / r) * (0.6 + 0.4 * pulse))
                gd.ellipse(
                    [cx - step, cy - step, cx + step, cy + step],
                    fill=(col[0], col[1], col[2], a),
                )

        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=size // 20))
        img = Image.alpha_composite(img, glow_layer)
        draw = ImageDraw.Draw(img)

        # --- Вращающееся кольцо ---
        margin = int(size * 0.04)
        ring_w = max(3, size // 60)
        arc_alpha = int(180 + 75 * math.sin(angle * 2))

        # Внешнее кольцо
        draw.arc(
            [margin, margin, size - margin, size - margin],
            start=math.degrees(angle),
            end=math.degrees(angle) + 240,
            fill=(138, 43, 226, arc_alpha),
            width=ring_w,
        )
        # Внутреннее кольцо (обратное вращение)
        inner = margin + ring_w + int(size * 0.02)
        draw.arc(
            [inner, inner, size - inner, size - inner],
            start=math.degrees(-angle * 1.5),
            end=math.degrees(-angle * 1.5) + 180,
            fill=(0, 191, 255, int(arc_alpha * 0.7)),
            width=max(2, ring_w // 2),
        )

        # --- Текст ---
        font_size = self._calc_font_size(text, size)
        font = self._get_font(font_size)

        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        tx = (size - tw) // 2 - bbox[0]
        ty = (size - th) // 2 - bbox[1]

        # Цвет текста (плавно меняется)
        text_r = int(200 + 55 * math.sin(angle))
        text_g = int(80 + 60 * math.cos(angle * 1.3))
        text_b = 255

        # Glow текста
        self._draw_glow(
            draw, tx, ty, text, font,
            (text_r, text_g, text_b),
            radius=max(6, font_size // 8),
        )

        # Тень
        shadow = max(2, size // 120)
        draw.text(
            (tx + shadow, ty + shadow),
            text,
            font=font,
            fill=(0, 0, 0, 200),
        )

        # Основной текст
        draw.text(
            (tx, ty),
            text,
            font=font,
            fill=(text_r, text_g, text_b, 255),
        )

        return img

    def _build_webp(self, text: str) -> bytes:
        """Собирает анимированный WebP 512x512"""
        size = 512
        total = 30
        frames = []

        for i in range(total):
            frame = self._create_frame(text, i, total, size)
            frames.append(frame)

        buf = io.BytesIO()
        frames[0].save(
            buf,
            format="WEBP",
            save_all=True,
            append_images=frames[1:],
            duration=60,       # ~16 fps
            loop=0,
            quality=90,
            method=4,
        )
        buf.seek(0)
        return buf.read()

    @loader.command(ru_doc="<текст> — Создать премиум анимированный стикер (до 8 символов)")
    async def pemoji(self, message):
        """<text> — Create premium animated sticker (up to 8 chars)"""
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
            data = await asyncio.get_event_loop().run_in_executor(
                None, self._build_webp, text
            )

            buf = io.BytesIO(data)
            buf.name = "sticker.webp"
            buf.seek(0)

            await message.delete()
            await self._client.send_file(
                message.peer_id,
                buf,
                force_document=False,
            )

        except Exception as e:
            await utils.answer(
                message,
                f"❌ <b>Ошибка:</b> <code>{e}</code>",
            )
