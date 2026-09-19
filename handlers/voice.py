from aiogram import Router, F
from aiogram.types import Message
from services.deepgram import DeepgramService
from services.delivery import deliver
from utils.redact import redact_token
from config.config import config
from loguru import logger
import traceback

router = Router()
deepgram_service = DeepgramService(config.DEEPGRAM_API_KEY)

@router.message(F.voice)
async def handle_voice(message: Message):
    try:
        # Show processing status
        await message.bot.send_chat_action(message.chat.id, "typing")
        
        # Get file
        file = await message.bot.get_file(message.voice.file_id)
        file_url = f"https://api.telegram.org/file/bot{config.BOT_TOKEN}/{file.file_path}"
        
        logger.debug(f"Processing voice message. File path: {file.file_path}")
        
        # Transcribe
        result = await deepgram_service.transcribe_audio(file_url)
        
        # Summary first, then transcript
        await deliver(message, result.text, "voice")
        
    except Exception as e:
        error_msg = f"Ошибка: {redact_token(str(e))}"
        logger.error(f"Error processing voice message: {str(e)}\n{traceback.format_exc()}")
        await message.answer(error_msg)
