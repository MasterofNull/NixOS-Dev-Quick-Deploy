from extensions.ai_coordinator_handlers import *
import extensions.ai_coordinator_handlers as _ext
import logging
logger = logging.getLogger(__name__)

async def handle_ai_coordinator_delegate(request: web.Request) -> web.Response:
    logger.error("DEBUG: ROOT ai_coordinator_handlers.handle_ai_coordinator_delegate triggered!")
    return await _ext.handle_ai_coordinator_delegate(request)
