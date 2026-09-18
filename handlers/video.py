from aiogram import Router, F
from aiogram.types import Message
from services.deepgram import DeepgramService
from services.delivery import deliver
from config.config import config
from loguru import logger
import traceback

router = Router()
deepgram_service = DeepgramService(config.DEEPGRAM_API_KEY)

@router.message(F.video)
async def handle_video(message: Message):
    try:
        # Show typing action
        await message.bot.send_chat_action(message.chat.id, "typing")
        
        # Get file
        file = await message.bot.get_file(message.video.file_id)
        file_url = f"https://api.telegram.org/file/bot{config.BOT_TOKEN}/{file.file_path}"
        
        logger.debug(f"Processing video file. File URL: {file_url}")
        
        # Transcribe
        result = await deepgram_service.transcribe_audio(file_url)
        
        # Summary first, then transcript
        await deliver(message, result.text, "video")
        
    except Exception as e:
        error_msg = f"Ошибка: {str(e)}"
        logger.error(f"Full error: {str(e)}\n{traceback.format_exc()}")
        await message.answer(error_msg)

@router.message(F.video_note)
async def handle_video_note(message: Message):
    processing_msg = await message.reply("🎥 Обрабатываю видео...")
    
    try:
        file = await message.bot.get_file(message.video_note.file_id)
        file_url = f"https://api.telegram.org/file/bot{config.BOT_TOKEN}/{file.file_path}"
        
        logger.debug(f"Processing video note file. File URL: {file_url}")
        
        result = await deepgram_service.transcribe_audio(file_url)
        await deliver(message, result.text, "video_note", placeholder=processing_msg)
        
    except Exception as e:
        error_msg = f"❌ Ошибка при обработке видео: {str(e)[:200]}..."
        logger.error(f"Full error: {str(e)}\n\nTraceback:\n{''.join(traceback.format_exc())}")
        await processing_msg.edit_text(error_msg)
