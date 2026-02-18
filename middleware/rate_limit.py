# middleware/rate_limit.py
import time
from collections import defaultdict

from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram import types


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, rate: float = 1.0, burst: int = 5):
        super().__init__()
        self.rate = rate
        self.burst = burst
        self.users = defaultdict(list)

    async def on_pre_process_message(self, message: types.Message, data: dict):
        now = time.time()
        user_id = message.from_user.id
        history = self.users[user_id]

        # чистим старые записи
        history = [t for t in history if now - t < self.rate * self.burst]
        history.append(now)
        self.users[user_id] = history

        if len(history) > self.burst:
            await message.answer("Слишком много запросов. Попробуйте чуть позже.")
            from aiogram.dispatcher.handler import CancelHandler
            raise CancelHandler()
