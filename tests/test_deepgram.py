"""Параметры запроса к Deepgram: модель для русского и отказ от обучения на наших записях."""
from aiohttp import web
from aiohttp.test_utils import TestServer

from services.deepgram import DeepgramService

DEEPGRAM_REPLY = {
    "results": {"channels": [{"alternatives": [{"transcript": "привет", "confidence": 0.9, "words": []}]}]}
}


async def transcribe_and_capture_query():
    """Прогнать распознавание через локальный сервер вместо Deepgram и вернуть параметры запроса."""
    seen = {}

    async def audio_file(request):
        return web.Response(body=b"audio")

    async def listen(request):
        seen.update(request.query)
        return web.json_response(DEEPGRAM_REPLY)

    app = web.Application()
    app.router.add_get("/file.oga", audio_file)
    app.router.add_post("/v1/listen", listen)
    async with TestServer(app) as server:
        service = DeepgramService("key")
        service.base_url = str(server.make_url("/v1/listen"))
        await service.transcribe_audio(str(server.make_url("/file.oga")))
    return seen


async def test_russian_speech_goes_to_nova3():
    query = await transcribe_and_capture_query()
    assert query["model"] == "nova-3"
    assert query["language"] == "ru"


async def test_requests_opt_out_of_deepgram_model_training():
    query = await transcribe_and_capture_query()
    assert query["mip_opt_out"] == "true"
