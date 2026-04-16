"""
Модуль для создания эмодзи-паков по шаблону.
Владелец: @Kilka_Young
Репозиторий: https://github.com/coddrago/Heroku
"""

import os
import io
import random
import string
from PIL import Image, ImageDraw, ImageFont

from telethon import events
from telethon.tl.functions.messages import CreateStickerSetRequest
from telethon.tl.types import InputStickerSetItem, DocumentAttributeImageSize

# Путь к шаблону и шрифту (укажи свои пути, если они лежат в другой папке)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(BASE_DIR, "template.png")
FONT_PATH = os.path.join(BASE_DIR, "font.ttf")

# Список из 49 стандартных эмодзи (Telegram требует хотя бы 1 эмодзи на каждый стикер)
EMOJIS_LIST = [
    "😀", "😎", "❤️", "🔥", "🎉", "👀", "💯", "⭐", "🌈", "🦄",
    "🍕", "🎮", "🚀", "💎", "🎵", "🌍", "🧠", "👻", "🤖", "🎯",
    "🌸", "🐱", "🌊", "⚡", "🍪", "🎨", "📱", "💡", "🍺", "⚽",
    "🎩", "🦋", "🐍", "🎶", "💰", "🔑", "🍪", "🛸", "🧊", "🥑",
    "🎪", "🪐", "🧲", "🪄", "🧿", "🧸", "🦊", "🐙", "🦈"
]

def generate_emoji_image(text: str) -> bytes:
    """Генерирует картинку эмодзи с текстом поверх шаблона"""
    # Открываем шаблон
    img = Image.open(TEMPLATE_PATH).convert("RGBA").resize((512, 512), Image.LANCZOS)
    draw = ImageDraw.Draw(img)
    
    # Загружаем шрифт (размер можно менять)
    try:
        font = ImageFont.truetype(FONT_PATH, 80)
    except IOError:
        font = ImageFont.load_default()

    # Вычисляем позицию текста (по центру)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    position = ((512 - text_width) / 2, (512 - text_height) / 2)
    
    # Рисуем текст (цвет можно поменять, например, fill="white")
    draw.text(position, text, font=font, fill="white")
    
    # Сохраняем в буфер (в памяти, без создания файла на диске)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    
    return buf.getvalue()

def register_module(client):
    """Регистрация обработчика команд в ядре юзербота"""
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'\.epack\s+(.+)'))
    async def emoji_pack_creator(event):
        text = event.pattern_match.group(1)
        
        # Уведомляем пользователя о начале процесса
        msg = await event.edit(f"⚡️ Создаю эмодзи-пак с надписью **{text}**...\nЭто может занять около минуты.")
        
        # Генерируем картинку один раз (она будет одинаковой для всех 49 эмодзи)
        image_bytes = generate_emoji_image(text)
        
        # Загружаем картинку на сервер Telegram как документ
        file = await client.upload_file(image_bytes)
        
        # Формируем уникальное имя для пака (Telegram требует латиницу и уникальность)
        short_name = "epack_" + ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        pack_title = f"Emoji Pack: {text} by @Kilka_Young"
        
        # Подготавливаем 49 предметов для пака
        stickers = []
        for i in range(49):
            sticker_item = InputStickerSetItem(
                document=file,
                emoji=EMOJIS_LIST[i],
                # Для кастомных эмодзи обязательно указывать тип
                allow_custom_emoji=True 
            )
            stickers.append(sticker_item)
            
        try:
            # Создаем набор эмодзи
            # Важный момент: stickerset_type=1 означает, что это ЭМОДЗИ пак, а не стикеры
            result = await client(CreateStickerSetRequest(
                user_id=await client.get_me(),
                title=pack_title,
                short_name=short_name,
                stickers=stickers,
                stickerset_type=1 # 1 = Custom Emoji
            ))
            
            pack_link = f"https://t.me/addemoji/{short_name}"
            await msg.edit(f"✅ **Эмодзи-пак успешно создан!**\n\n"
                           f"📝 Текст: {text}\n"
                           f"🔢 Количество: 49 эмодзи\n"
                           f"🔗 Ссылка: {pack_link}\n\n"
                           f"👤 Владелец модуля: @Kilka_Young")
                           
        except Exception as e:
            await msg.edit(f"❌ **Ошибка при создании пака:**\n`{str(e)}`\n\n"
                           "Убедись, что у тебя есть Telegram Premium (для создания эмодзи нужен Premium), "
                           "и что имя пака уникально.")
