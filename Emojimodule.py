import os
from PIL import Image, ImageDraw, ImageFont

# ===== НАСТРОЙКИ =====
TEMPLATE_PATH = "template.png"
FONT_PATH = "font.ttf"
OUTPUT_DIR = "emojis"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ===== ГЕНЕРАЦИЯ =====
def generate_emojis(text):
    files = []

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

        path = f"{OUTPUT_DIR}/emoji_{i+1}.png"
        img.save(path)
        files.append(path)

    return files


# ===== ИНСТРУКЦИЯ =====
def print_guide():
    print("\n📦 Эмодзи готовы!")
    print("\n👉 Дальше делай так:")
    print("1. Открой Telegram")
    print("2. Найди бота @Stickers")
    print("3. Отправь /newemojipack")
    print("4. Введи название пака")
    print("5. Загрузи все 49 файлов из папки emojis")
    print("6. Отправь любой эмодзи (например 🙂)")
    print("7. В конце отправь /publish")
    print("\n🔗 Получишь ссылку вида:")
    print("https://t.me/addemoji/your_pack_name\n")


# ===== ЗАПУСК =====
if __name__ == "__main__":
    text = input("Введите текст для эмодзи: ")

    print("🎨 Генерация...")
    generate_emojis(text)

    print_guide()
