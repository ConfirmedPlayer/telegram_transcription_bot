import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from config.config import config
from handlers import voice, video, audio, style, commands
from loguru import logger
from utils.redact import redact_log_record

# Configure logging
logging.basicConfig(level=logging.INFO)
# Токен бота вычищается из каждой записи до того, как она попадёт в stderr или в файл
logger.configure(patcher=redact_log_record)
try:
    logger.add("logs/bot.log", rotation="1 day", compression="zip")
except PermissionError:
    logger.add("bot.log", rotation="1 day", compression="zip")
    logger.warning("Нет прав на запись в logs/ — лог пишется в bot.log внутри контейнера")

async def main():
    # Initialize bot and dispatcher with new DefaultBotProperties
    default = DefaultBotProperties(parse_mode=ParseMode.HTML, allow_sending_without_reply=True)
    bot = Bot(token=config.BOT_TOKEN, default=default)
    dp = Dispatcher()
    
    # Register routers
    dp.include_router(commands.router)
    dp.include_router(voice.router)
    dp.include_router(video.router)
    dp.include_router(audio.router)
    dp.include_router(style.router)
    
    # Start polling
    logger.info("Starting bot...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped!")
