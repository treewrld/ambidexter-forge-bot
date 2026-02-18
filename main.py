import logging

from aiogram import Bot, Dispatcher, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage

from config import TOKEN
from database import init_db

from order_handlers import register_order_handlers, fallback
from admin_handlers import register_admin_handlers

from middleware.admin_protect import AdminProtectMiddleware
from middleware.rate_limit import RateLimitMiddleware
from utils.error_handler import register_error_handler

logging.basicConfig(level=logging.INFO)


def main():
    init_db()

    bot = Bot(token=TOKEN, parse_mode="HTML")
    dp = Dispatcher(bot, storage=MemoryStorage())

    # middleware
    dp.middleware.setup(AdminProtectMiddleware())
    dp.middleware.setup(RateLimitMiddleware(rate=1.5, burst=5))

    # хендлеры
    register_order_handlers(dp)
    register_admin_handlers(dp)

    # fallback — последним
    dp.register_message_handler(fallback)

    # глобальный обработчик ошибок
    register_error_handler(dp)

    executor.start_polling(dp, skip_updates=True)


if __name__ == "__main__":
    main()
