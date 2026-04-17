import asyncio
import logging
import os
import aiosqlite
import aiohttp
from datetime import datetime
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage

# --- CONFIG ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
SMS_API_KEY = os.getenv("SMS_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
DB_PATH = "sms_service.db"
SMS_ACTIVATE_URL = "https://api.sms-activate.org/stubs/handler_api.php"

# --- DATABASE ---
class Database:
    def __init__(self, path):
        self.path = path

    async def setup(self):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    balance REAL DEFAULT 0.0,
                    username TEXT
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    activation_id TEXT,
                    phone TEXT,
                    service TEXT,
                    status TEXT,
                    code TEXT
                )
            """)
            await db.commit()

    async def get_user(self, user_id):
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
                return await cursor.fetchone()

    async def add_user(self, user_id, username):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
            await db.commit()

    async def update_balance(self, user_id, amount):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
            await db.commit()

db_manager = Database(DB_PATH)

# --- SMS API SERVICE ---
class SMSService:
    def __init__(self, api_key):
        self.api_key = api_key

    async def _request(self, params):
        params["api_key"] = self.api_key
        async with aiohttp.ClientSession() as session:
            async with session.get(SMS_ACTIVATE_URL, params=params) as resp:
                return await resp.text()

    async def get_number(self, service, country=0):
        res = await self._request({"action": "getNumber", "service": service, "country": country})
        if "ACCESS_NUMBER" in res:
            _, act_id, phone = res.split(":")
            return {"id": act_id, "phone": phone}
        return None

    async def get_status(self, act_id):
        res = await self._request({"action": "getStatus", "id": act_id})
        return res

    async def set_status(self, act_id, status):
        # 1 - сообщить об отправке, 8 - отмена
        await self._request({"action": "setStatus", "id": act_id, "status": status})

sms_api = SMSService(SMS_API_KEY)

# --- HANDLERS ---
router = Router()

def get_main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Купить номер", callback_data="buy_list")],
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile"), InlineKeyboardButton(text="💳 Пополнить", callback_data="deposit")]
    ])

@router.message(Command("start"))
async def cmd_start(message: Message):
    await db_manager.add_user(message.from_user.id, message.from_user.username)
    await message.answer(
        f"🤖 *Добро пожаловать в SMS Service!*\n\nПолучайте коды верификации для любых соцсетей быстро и надежно.",
        reply_markup=get_main_kb(),
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "profile")
async def view_profile(call: CallbackQuery):
    user = await db_manager.get_user(call.from_user.id)
    text = (f"👤 *Ваш профиль*\n\n"
            f"🆔 ID: `{call.from_user.id}`\n"
            f"💰 Баланс: `{user['balance']}` руб.\n"
            f"📞 Заказов: (в разработке)")
    await call.message.edit_text(text, reply_markup=get_main_kb(), parse_mode="Markdown")

@router.callback_query(F.data == "buy_list")
async def buy_list(call: CallbackQuery):
    # Упрощенный список сервисов
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Telegram (tg) - 30₽", callback_data="buy_tg")],
        [InlineKeyboardButton(text="WhatsApp (wa) - 20₽", callback_data="buy_wa")],
        [InlineKeyboardButton(text="ВКонтакте (vk) - 15₽", callback_data="buy_vk")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="profile")]
    ])
    await call.message.edit_text("Выбери сервис для получения SMS:", reply_markup=kb)

@router.callback_query(F.data.startswith("buy_"))
async def process_buy(call: CallbackQuery):
    service_code = call.data.split("_")[1]
    user = await db_manager.get_user(call.from_user.id)
    
    price = 30 # В идеале получать цены через getPrices API
    if user['balance'] < price:
        return await call.answer("❌ Недостаточно средств на балансе!", show_alert=True)

    await call.answer("⏳ Запрашиваю номер...")
    num_data = await sms_api.get_number(service_code)
    
    if not num_data:
        return await call.message.answer("❌ Свободных номеров нет, попробуйте позже.")

    act_id = num_data['id']
    phone = num_data['phone']
    
    # Списываем баланс (упрощенно)
    await db_manager.update_balance(call.from_user.id, -price)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_{act_id}")]
    ])
    
    msg = await call.message.answer(
        f"✅ Номер получен!\n\n📞 `{phone}`\nСервис: {service_code}\n\n*Ожидание SMS...*",
        reply_markup=kb, parse_mode="Markdown"
    )

    # Запуск цикла проверки
    asyncio.create_task(wait_for_sms(msg, act_id, call.from_user.id, price))

async def wait_for_sms(msg: Message, act_id, user_id, price):
    for _ in range(60): # 10 минут ожидания (каждые 10 сек)
        await asyncio.sleep(10)
        status = await sms_api.get_status(act_id)
        
        if "STATUS_OK" in status:
            code = status.split(":")[1]
            await msg.edit_text(f"📩 *Код получен:* `{code}`\nНомер: `{act_id}`", parse_mode="Markdown")
            return
        
        if "STATUS_CANCEL" in status:
            await msg.edit_text("❌ Заказ отменен. Средства возвращены.")
            await db_manager.update_balance(user_id, price)
            return

    # Если время вышло
    await sms_api.set_status(act_id, 8)
    await msg.edit_text("⌛️ Время ожидания истекло. Номер отменен.")
    await db_manager.update_balance(user_id, price)

@router.callback_query(F.data.startswith("cancel_"))
async def cancel_order(call: CallbackQuery):
    act_id = call.data.split("_")[1]
    await sms_api.set_status(act_id, 8)
    await call.answer("Запрос на отмену отправлен")

# --- ADMIN HANDLERS ---
@router.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("👑 Админ-панель\n\nДля пополнения используй:\n`/give ID сумма`")

@router.message(Command("give"))
async def give_money(message: Message):
    if message.from_user.id != ADMIN_ID: return
    try:
        _, user_id, amount = message.text.split()
        await db_manager.update_balance(int(user_id), float(amount))
        await message.answer(f"✅ Баланс пользователя `{user_id}` пополнен на {amount} руб.", parse_mode="Markdown")
    except:
        await message.answer("Ошибка. Формат: `/give 1234567 100`")

# --- MAIN ---
async def main():
    logging.basicConfig(level=logging.INFO)
    await db_manager.setup()
    
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    
    print("Бот запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
