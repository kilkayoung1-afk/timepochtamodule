"""
Точка входа Pochta Modules Bot.

Запуск:
    cd timerbot
    pip install -r requirements.txt
    python bot.py

Перед стартом задайте API_ID/API_HASH (см. config.py).
"""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import config
from database import DB
from handlers import register_all
from modules import all_modules, get as get_module
from userbot import UserbotManager

logger = logging.getLogger(__name__)


async def _restore_running_modules(db: DB, userbot: UserbotManager) -> None:
    """Перезапускает все включённые модули после перезапуска бота."""
    for mod_info in all_modules():
        key = mod_info["key"]
        mod = get_module(key)
        if not mod:
            continue
        for entry in await db.all_enabled_for_module(key):
            user_id = entry["user_id"]
            session = await db.get_session(user_id)
            if not session:
                continue
            try:
                await mod.start(
                    user_id=user_id,
                    session_string=session,
                    config=entry.get("config", {}),
                    db=db,
                    userbot=userbot,
                )
                logger.info("Restored module %s for user %s", key, user_id)
            except Exception as exc:
                logger.warning(
                    "Failed to restore module %s for user %s: %s", key, user_id, exc
                )


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    logging.getLogger("pyrogram").setLevel(logging.WARNING)

    if not config.BOT_TOKEN:
        logger.error("BOT_TOKEN не задан в config.py")
        sys.exit(1)

    db = DB(config.DB_PATH)
    await db.init()

    userbot = UserbotManager(api_id=config.API_ID, api_hash=config.API_HASH)
    if not userbot.is_configured():
        logger.warning(
            "API_ID/API_HASH не заданы — модуль «Таймер» работать не будет. "
            "Получите их на https://my.telegram.org/apps"
        )

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp["db"] = db
    dp["userbot"] = userbot
    register_all(dp)

    # Перезапускаем включённые модули
    await _restore_running_modules(db, userbot)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        me = await bot.get_me()
        logger.info("Bot @%s started", me.username)
        await dp.start_polling(bot)
    finally:
        await userbot.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Stopped")
