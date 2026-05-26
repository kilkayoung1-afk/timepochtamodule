"""
Конфигурация бота.

API_ID и API_HASH получаются на https://my.telegram.org/apps
Без них модуль "Таймер" работать не будет (Pyrogram не запустит сессию пользователя).
"""

import os

# Bot API token (BotFather)
BOT_TOKEN = os.getenv(
    "BOT_TOKEN",
    "8897460041:AAEAPXrwpXKuhH3MoEoDa2zTbTxhosZUn2Y",
)

# Список Telegram-айди администраторов
ADMIN_IDS: list[int] = [
    int(x) for x in os.getenv("ADMIN_IDS", "7119847306").split(",") if x.strip()
]

# Pyrogram credentials. Получите на https://my.telegram.org/apps
API_ID: int = int(os.getenv("API_ID", "0"))
API_HASH: str = os.getenv("API_HASH", "")

# Канал для проверки подписки (опционально). Пример: "@my_channel"
REQUIRED_CHANNEL: str = os.getenv("REQUIRED_CHANNEL", "")
REQUIRED_CHANNEL_LINK: str = os.getenv("REQUIRED_CHANNEL_LINK", "")

# Пути
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.getenv("DB_PATH", os.path.join(BASE_DIR, "bot.db"))

# Тариф "premium" — это пользователи с подключённой Telegram Premium
# подпиской (User.is_premium = True). Дополнительно — список ручных VIP id.
MANUAL_PREMIUM_IDS: set[int] = set(
    int(x) for x in os.getenv("MANUAL_PREMIUM_IDS", "").split(",") if x.strip()
)

# Интервал обновления ника в модуле "Таймер" (секунды)
TIMER_DEFAULT_INTERVAL: int = int(os.getenv("TIMER_INTERVAL", "60"))

# Максимальная длина first_name в Telegram
TG_FIRST_NAME_MAX = 64
