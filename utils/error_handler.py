# utils/error_handler.py
import logging

from aiogram import types, Dispatcher
from aiogram.utils.exceptions import MessageNotModified, Throttled


logger = logging.getLogger(__name__)


async def global_error_handler(update: types.Update, exception: Exception):
    if isinstance(exception, MessageNotModified):
        return True

    if isinstance(exception, Throttled):
        return True

    logger.exception(f"Unhandled error: {exception} | Update: {update}")
    try:
        if update.message:
            await update.message.answer("Произошла ошибка. Мы уже работаем над этим.")
        elif update.callback_query:
            await update.callback_query.answer("Произошла ошибка.", show_alert=True)
    except Exception:
        pass

    return True


def register_error_handler(dp: Dispatcher):
    dp.register_errors_handler(global_error_handler)
