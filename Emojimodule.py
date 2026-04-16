import os
import zipfile
from PIL import Image, ImageDraw, ImageFont

# Пути к файлам (можно изменить под структуру репозитория)
TEMPLATE_PATH = "template.png"
TEMP_DIR = "temp_emoji_pack"
FONT_PATH = "arial.ttf" # Если сервер Linux, лучше положить свой .ttf файл в папку

def create_emoji_pack(user_text: str, pack_name: str = "custom_pack") -> str:
    """
    Создает архив с 49 эмодзи, заменяя текст на шаблоне.
    Возвращает путь к готовому .zip файлу.
    """
    # Проверяем наличие шаблона
    if not os.path.exists(TEMPLATE_PATH):
        raise FileNotFoundError(f"Шаблон {TEMPLATE_PATH} не найден! Положите его в папку с модулем.")

    # Создаем временную папку
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)
    else:
        # Очищаем папку от старых файлов
        for f in os.listdir(TEMP_DIR):
            os.remove(os.path.join(TEMP_DIR, f))

    # Загружаем шрифт (с защитой от ошибки, если шрифта нет)
    try:
        base_font_size = 20
        font = ImageFont.truetype(FONT_PATH, base_font_size)
    except IOError:
        print("Шрифт не найден, используется стандартный.")
        font = ImageFont.load_default()

    zip_path = f"{pack_name}.zip"

    # Генерируем 49 эмодзи
    for i in range(1, 50):
        # Открываем шаблон каждый раз заново, чтобы не наслаивался текст
        img = Image.open(TEMPLATE_PATH).convert("RGBA")
        draw = ImageDraw.Draw(img)

        # --- ЛОГИКА АВТОМАТИЧЕСКОГО УМЕНЬШЕНИЯ ШРИФТА ---
        # Если текст длинный, уменьшаем шрифт, чтобы он влез в 100px
        current_font = font
        while draw.textlength(user_text, font=current_font) > 90 and base_font_size > 8:
            base_font_size -= 1
            try:
                current_font = ImageFont.truetype(FONT_PATH, base_font_size)
            except:
                current_font = ImageFont.load_default()

        # Вычисляем координаты для центра текста
        bbox = draw.textbbox((0, 0), user_text, font=current_font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Центрируем (допустим, шаблон 100x100, ставим текст ровно по центру)
        x = (100 - text_width) / 2
        y = (100 - text_height) / 2

        # Рисуем текст (цвет белый, можно поменять)
        draw.text((x, y), user_text, font=current_font, fill="white", align="center")

        # Сохраняем отдельную картинку
        img_path = os.path.join(TEMP_DIR, f"{i}.png")
        img.save(img_path, "PNG")

    # Упаковываем в ZIP
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for i in range(1, 50):
            file_path = os.path.join(TEMP_DIR, f"{i}.png")
            # Записываем в архив именно под именем 1.png, 2.png и т.д.
            zipf.write(file_path, f"{i}.png")

    # Удаляем временную папку (опционально)
    for f in os.listdir(TEMP_DIR):
        os.remove(os.path.join(TEMP_DIR, f))
    os.rmdir(TEMP_DIR)

    return zip_path

# ==========================================
# ПРИМЕР ИНТЕГРАЦИИ (для Telethon / Pyrogram)
# ==========================================

async def send_pack_command(client, message):
    """
    Функция, которая вызывается при команде /createpack <текст>
    """
    text = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else "Текст"
    
    await message.edit("⏳ Генерирую пак из 49 эмодзи...")
    
    try:
        # Создаем архив
        zip_file = create_emoji_pack(user_text=text, pack_name=f"pack_{message.sender_id}")
        
        # Отправляем архив пользователю
        await client.send_file(
            entity=message.chat_id,
            file=zip_file,
            force_document=True, # Обязательно как документ, чтобы не сжалось
            caption="✅ Готово! Загрузи этот файл в @Stickers.\n"
                    "1. Открой @Stickers -> Создать пак\n"
                    "2. Выбери этот архив"
        )
        
        # Удаляем файл с сервера после отправки
        if os.path.exists(zip_file):
            os.remove(zip_file)
            
        await message.delete()
        
    except Exception as e:
        await message.edit(f"❌ Ошибка при создании: {e}")
