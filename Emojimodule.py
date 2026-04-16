# █▀▄▀█ █▀█ █▀▄ █░█ █░░ █▀▀
# █░▀░█ █▄█ █▄▀ █▄█ █▄▄ ██▄
# meta developer: @Kilka_Young
# requires: Pillow requests

import io
import os
import random
import string
import colorsys
import requests
import asyncio
from PIL import Image, ImageDraw, ImageFont

from .. import loader, utils

@loader.tds
class KilkaEmojiMod(loader.Module):
    """Модуль для автоматического создания пака кастомных эмодзи по шаблону"""
    strings = {"name": "KilkaEmoji"}

    async def client_ready(self, client, db):
        self.client = client
        # Скачиваем жирный шрифт, если его нет (чтобы текст был читаемым)
        if not os.path.exists("kilkafont.ttf"):
            r = requests.get("https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Black.ttf")
            with open("kilkafont.ttf", "wb") as f:
                f.write(r.content)

    @loader.sudo
    async def kilkacmd(self, message):
        """<текст> - Создать пак из 49 цветных эмодзи с вашим текстом"""
        args = utils.get_args_raw(message)
        if not args:
            return await utils.answer(message, "<b>❌ Введи текст для эмодзи! Пример: <code>.kilka HELLO</code></b>")

        await utils.answer(message, "<b>⏳ Генерирую 49 эмодзи... Это займет пару минут.</b>")

        images = []
        # Создаем 49 изображений с разными цветами
        for i in range(49):
            # Плавно меняем оттенок цвета по спектру (от 0 до 1)
            hue = i / 49.0
            r, g, b = colorsys.hsv_to_rgb(hue, 0.85, 0.85)
            color = (int(r*255), int(g*255), int(b*255), 255)

            # Требование телеграма для эмодзи: 100x100
            img = Image.new("RGBA", (100, 100), color)
            draw = ImageDraw.Draw(img)

            font_path = "kilkafont.ttf"
            best_font = None
            tw, th = 0, 0
            
            # Подбираем идеальный размер шрифта, чтобы он влез в 90х90 пикселей
            for size in range(40, 8, -1):
                try:
                    font = ImageFont.truetype(font_path, size)
                except Exception:
                    font = ImageFont.load_default()
                    break

                if hasattr(draw, 'multiline_textbbox'):
                    bbox = draw.multiline_textbbox((0, 0), args, font=font)
                    w = bbox[2] - bbox[0]
                    h = bbox[3] - bbox[1]
                else:
                    w, h = draw.textsize(args, font=font)

                if w <= 90 and h <= 90:
                    best_font = font
                    tw, th = w, h
                    break

            if not best_font:
                best_font = ImageFont.truetype(font_path, 10)
                if hasattr(draw, 'multiline_textbbox'):
                    bbox = draw.multiline_textbbox((0, 0), args, font=best_font)
                    tw = bbox[2] - bbox[0]
                    th = bbox[3] - bbox[1]
                else:
                    tw, th = draw.textsize(args, font=best_font)

            # Рисуем текст строго по центру
            x = (100 - tw) / 2
            y = (100 - th) / 2
            draw.multiline_text((x, y), args, fill="white", font=best_font, align="center")

            out = io.BytesIO()
            out.name = f"kilka_{i}.png"
            img.save(out, "PNG")
            out.seek(0)
            images.append(out)

        await utils.answer(message, "<b>⏳ Начинаю загрузку в @Stickers... Пожалуйста, не используй бота в процессе.</b>")

        chat = "@Stickers"
        me = await self.client.get_me()
        username = me.username if me.username else str(me.id)
        # Уникальная ссылка (short_name), чтобы паки не перезаписывались
        rand_str = ''.join(random.choices(string.ascii_lowercase, k=5))
        short_name = f"kilkacolor_{rand_str}_by_{username}"
        pack_name = f"Kilka {args[:10]}..."

        try:
            # Начинаем диалог с официальным ботом стикеров
            async with self.client.conversation(chat) as conv:
                await conv.send_message("/newemojipack")
                resp = await conv.get_response()

                if resp.buttons:
                    # Ищем кнопку "Static emoji" или кликаем первую
                    await resp.click(text="Static emoji", exact=False)
                    if not any("Static" in b.text for row in resp.buttons for b in row):
                        await resp.click(0)
                    resp = await conv.get_response()

                # Отправляем название пака
                await conv.send_message(pack_name)
                resp = await conv.get_response()

                for i, img in enumerate(images):
                    # Загружаем файл эмодзи
                    file = await self.client.upload_file(img, file_name=f"kilka_{i}.png")
                    await conv.send_file(file, force_document=True)
                    resp = await conv.get_response()
                    await asyncio.sleep(0.3) # Задержка от флуда

                    # Отправляем привязанный эмодзи
                    await conv.send_message("⬛")
                    resp = await conv.get_response()
                    await asyncio.sleep(0.3) # Задержка от флуда

                    if i % 10 == 0 and i > 0:
                        await utils.answer(message, f"<b>⏳ Загружено {i}/49 эмодзи...</b>")

                # Публикуем пак
                await conv.send_message("/publish")
                resp = await conv.get_response()

                # Пропускаем установку иконки
                await conv.send_message("/skip")
                resp = await conv.get_response()

                # Отправляем уникальный линк
                await conv.send_message(short_name)
                resp = await conv.get_response()

                if "Kaboom" in resp.text or "published" in resp.text.lower() or "t.me/" in resp.text:
                    await utils.answer(message, f"<b>✅ Пак эмодзи успешно создан! Владелец: @Kilka_Young</b>\n👉 https://t.me/addemoji/{short_name}")
                else:
                    await utils.answer(message, f"<b>⚠️ Возникла ошибка при создании ссылки:</b>\n{resp.text}")

        except Exception as e:
            await utils.answer(message, f"<b>❌ Ошибка при взаимодействии со @Stickers:</b>\n<code>{e}</code>")
