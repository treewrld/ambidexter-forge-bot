# middleware/admin_protect.py
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram import types

from config import ADMIN_ID


class AdminProtectMiddleware(BaseMiddleware):
    async def on_pre_process_update(self, update: types.Update, data: dict):
        callback = update.callback_query
        message = update.message

        # защищаем admin_* callback-и
        if callback and callback.data and callback.data.startswith("admin_"):
            if callback.from_user.id != ADMIN_ID:
                await callback.answer("Недостаточно прав.", show_alert=True)
                raise CancelHandler()

        # защищаем админские текстовые команды
        if message and message.text:
            if message.text.startswith("📥 Все заказы") or \
               message.text.startswith("📊 Статистика") or \
               message.text.startswith("👁 Перейти в режим клиента") or \
               message.text.startswith("⚙️ Вернуться в админку"):
                if message.from_user.id != ADMIN_ID:
                    await message.answer("Недостаточно прав.")
                    raise CancelHandler()


from aiogram.dispatcher.handler import CancelHandler
