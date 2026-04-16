# meta developer: @Kilka_Young

import os
from PIL import Image, ImageDraw, ImageFont

OUTPUT_DIR = "emojis"
TEMPLATE_PATH = "template.png"
FONT_PATH = "font.ttf"

os.makedirs(OUTPUT_DIR, exist_ok=True)


def generate_emojis(text):
    for i in range(49):
        img = Image.open(TEMPLATE_PATH).convert("RGBA")
        draw = ImageDraw.Draw(img)

        font = ImageFont.truetype(FONT_PATH, 90)

        bbox = draw.textbbox((0, 0), text, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        W, H = img.size

        draw.text(
            ((W - w) / 2, (H - h) / 2),
            text,
            font=font,
            fill=(255, 255, 255)
        )

        img.save(f"{OUTPUT_DIR}/emoji_{i+1}.png")


# ===== ГЛАВНАЯ ФУНКЦИЯ МОДУЛЯ =====
def register(module_name):

    class EmojiModule:
        strings = {"name": "EmojiGenerator"}

        async def emoji(self, message):
            args = message.text.split(maxsplit=1)

            if len(args) < 2:
                await message.reply("❌ Введи текст: .emoji TEXT")
                return

            text = args[1]

            generate_emojis(text)

            await message.reply(
                "✅ Готово!\n"
                "📂 Эмодзи в папке emojis/\n"
                "👉 Загрузи через @Stickers"
            )

    return EmojiModule()
