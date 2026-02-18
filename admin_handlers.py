from aiogram import types, Dispatcher
from aiogram.dispatcher.filters import Text

from config import ADMIN_ID
from database import (
    get_orders_page,
    get_order_by_id,
    update_order_status,
    get_connection,
    get_banned_users,
    get_unban_requests,
    update_unban_request_status,
    unban_user,
)
from keyboards import (
    get_orders_list_kb,
    get_order_actions_kb,
    get_admin_menu,
    get_admin_client_menu,
    get_unban_requests_kb,
    get_unban_actions_kb,
)

PER_PAGE = 3


# ====== ФИЛЬТР: показываем только активные заказы ======

def filter_active_orders(rows):
    return [o for o in rows if o["status"] in ("new", "in_progress")]


# ====== СПИСОК ЗАКАЗОВ ======

async def admin_all_orders(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    page = 1
    rows, total = get_orders_page(page, PER_PAGE)

    active = filter_active_orders(rows)

    await message.answer(
        f"📥 <b>Активные заказы</b>\nСтраница {page}",
        reply_markup=get_orders_list_kb(active, page, len(active), PER_PAGE),
    )


async def admin_orders_page(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    page = int(callback.data.replace("admin_orders_page_", ""))
    rows, total = get_orders_page(page, PER_PAGE)

    active = filter_active_orders(rows)

    await callback.message.edit_text(
        f"📥 <b>Активные заказы</b>\nСтраница {page}",
        reply_markup=get_orders_list_kb(active, page, len(active), PER_PAGE),
    )
    await callback.answer()


# ====== КАРТОЧКА ЗАКАЗА ======

async def admin_open_order(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    order_id = int(callback.data.replace("admin_order_", ""))
    order = get_order_by_id(order_id)

    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    title = order["title"] if order["type"] == "custom" else order["service_code"]

    text = (
        f"📄 <b>Заказ #{order['id']}</b>\n\n"
        f"👤 Клиент: {order['client_name']}\n"
        f"Тип: {order['type']}\n"
        f"Название/услуга: {title}\n"
        f"Описание: {order['description']}\n"
        f"Бюджет: {order['budget'] or '-'}\n"
        f"Сроки: {order['deadline'] or '-'}\n"
        f"Контакт: {order['contact_method']} — {order['contact_value']}\n"
        f"Статус: {order['status']}\n"
        f"Создан: {order['created_at']}"
    )

    await callback.message.edit_text(
        text,
        reply_markup=get_order_actions_kb(order_id),
    )
    await callback.answer()


# ====== ИЗМЕНЕНИЕ СТАТУСА ======

async def admin_change_status(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    _, _, rest = callback.data.partition("admin_status_")
    order_id_str, _, status = rest.partition("_")
    order_id = int(order_id_str)

    order = get_order_by_id(order_id)
    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    update_order_status(order_id, status)

    # уведомление клиенту
    if order["client_tg_id"]:
        status_text = {
            "in_progress": "В работе 🔧",
            "done": "Завершён 🟢",
            "cancelled": "Отменён ❌",
        }.get(status, status)

        await callback.bot.send_message(
            order["client_tg_id"],
            f"Ваш заказ #{order_id} обновлён.\nНовый статус: {status_text}",
        )

    # если заказ завершён — удаляем карточку и возвращаем в меню
    if status == "done":
        await callback.message.edit_text("🏁 Заказ завершён и перенесён в статистику.")
        await callback.message.answer("Выберите действие:", reply_markup=get_admin_menu())
        await callback.answer()
        return

    # иначе — перерисовываем карточку
    order = get_order_by_id(order_id)
    title = order["title"] if order["type"] == "custom" else order["service_code"]

    text = (
        f"📄 <b>Заказ #{order['id']}</b>\n\n"
        f"👤 Клиент: {order['client_name']}\n"
        f"Тип: {order['type']}\n"
        f"Название/услуга: {title}\n"
        f"Описание: {order['description']}\n"
        f"Бюджет: {order['budget'] or '-'}\n"
        f"Сроки: {order['deadline'] or '-'}\n"
        f"Контакт: {order['contact_method']} — {order['contact_value']}\n"
        f"Статус: {order['status']}\n"
        f"Создан: {order['created_at']}"
    )

    try:
        await callback.message.edit_text(
            text,
            reply_markup=get_order_actions_kb(order_id),
        )
    except:
        pass

    await callback.answer("Статус обновлён")


# ====== СТАТИСТИКА ======

async def admin_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM orders")
    total = cur.fetchone()[0]

    cur.execute("SELECT status, COUNT(*) FROM orders GROUP BY status")
    rows = cur.fetchall()
    conn.close()

    status_names = {
        "new": "Новые",
        "in_progress": "В работе",
        "done": "Завершённые",
        "cancelled": "Отменённые",
    }

    text = f"📊 <b>Статистика заказов</b>\n\nВсего заказов: <b>{total}</b>\n\n"

    for status, count in rows:
        text += f"{status_names.get(status, status)}: <b>{count}</b>\n"

    await message.answer(text, reply_markup=get_admin_menu())


# ====== ЧЁРНЫЙ СПИСОК (АДМИН) ======

async def admin_blacklist(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    banned = get_banned_users()
    if not banned:
        await message.answer("🚫 Чёрный список пуст.", reply_markup=get_admin_menu())
        return

    text = "🚫 <b>Чёрный список</b>\n\n"
    for b in banned:
        text += (
            f"👤 TG ID: <code>{b['tg_id']}</code>\n"
            f"Причина: {b['reason']}\n"
            f"Дата: {b['created_at']}\n\n"
        )

    await message.answer(text, reply_markup=get_admin_menu())


# ====== ЗАЯВКИ НА РАЗБАН (АДМИН) ======

async def admin_unban_requests(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    requests = get_unban_requests(status="pending")
    kb = get_unban_requests_kb(requests)
    await message.answer("📨 <b>Заявки на разбан</b>", reply_markup=kb)


async def admin_unban_open(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    # ловим ТОЛЬКО admin_unban_<id>
    if not callback.data.startswith("admin_unban_"):
        return

    # игнорируем approve/reject/list
    if "approve" in callback.data or "reject" in callback.data or "list" in callback.data:
        return

    req_id = int(callback.data.replace("admin_unban_", ""))

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM unban_requests WHERE id = ?", (req_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        await callback.answer("Заявка не найдена", show_alert=True)
        return

    text = (
        f"📨 <b>Заявка #{row['id']}</b>\n\n"
        f"TG ID: <code>{row['tg_id']}</code>\n"
        f"Статус: {row['status']}\n"
        f"Причина:\n{row['reason']}\n"
    )

    await callback.message.edit_text(
        text,
        reply_markup=get_unban_actions_kb(row["id"]),
    )
    await callback.answer()


async def admin_unban_approve(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    req_id = int(callback.data.replace("admin_unban_approve_", ""))

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM unban_requests WHERE id = ?", (req_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        await callback.answer("Заявка не найдена", show_alert=True)
        return

    tg_id = row["tg_id"]
    unban_user(tg_id)
    update_unban_request_status(req_id, "approved")

    try:
        await callback.bot.send_message(
            tg_id,
            "✅ Ваша заявка на разбан одобрена. Доступ к боту восстановлен.",
        )
    except:
        pass

    await callback.message.edit_text("✅ Пользователь разбанен.")
    await callback.answer("Разбан выполнен")


async def admin_unban_reject(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    req_id = int(callback.data.replace("admin_unban_reject_", ""))

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM unban_requests WHERE id = ?", (req_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        await callback.answer("Заявка не найдена", show_alert=True)
        return

    tg_id = row["tg_id"]
    update_unban_request_status(req_id, "rejected")

    try:
        await callback.bot.send_message(
            tg_id,
            "❌ Ваша заявка на разбан отклонена.",
        )
    except:
        pass

    await callback.message.edit_text("❌ Заявка отклонена.")
    await callback.answer("Отклонено")

# ====== ПЕРЕКЛЮЧЕНИЕ В РЕЖИМ КЛИЕНТА ======

async def admin_switch_to_client(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    await message.answer(
        "👁 Вы перешли в режим клиента.",
        reply_markup=get_admin_client_menu(),
    )


# ====== ВОЗВРАТ В АДМИНКУ ======

async def admin_back_to_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    await message.answer(
        "⚙️ Вы вернулись в админ-панель.",
        reply_markup=get_admin_menu(),
    )


# ====== НАЗАД В МЕНЮ (ИНЛАЙН) ======

async def admin_back_menu(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    await callback.message.edit_text("⚙️ <b>Админ-панель</b>")
    await callback.message.answer("Выберите действие:", reply_markup=get_admin_menu())
    await callback.answer()


# ====== РЕГИСТРАЦИЯ ======

def register_admin_handlers(dp: Dispatcher):
    dp.register_message_handler(admin_all_orders, Text(equals="📥 Все заказы"))
    dp.register_message_handler(admin_stats, Text(equals="📊 Статистика"))
    dp.register_message_handler(admin_blacklist, Text(equals="🚫 Черный список"))
    dp.register_message_handler(admin_unban_requests, Text(equals="📨 Заявки на разбан"))
    dp.register_message_handler(admin_switch_to_client, Text(equals="👁 Перейти в режим клиента"))
    dp.register_message_handler(admin_back_to_admin, Text(equals="⚙️ Вернуться в админку"))

    dp.register_callback_query_handler(admin_orders_page, Text(startswith="admin_orders_page_"))
    dp.register_callback_query_handler(admin_open_order, Text(startswith="admin_order_"))
    dp.register_callback_query_handler(admin_change_status, Text(startswith="admin_status_"))

    dp.register_callback_query_handler(admin_back_menu, Text(equals="admin_back_menu"))

    # ВАЖНО: сначала approve/reject
    dp.register_callback_query_handler(admin_unban_approve, Text(startswith="admin_unban_approve_"))
    dp.register_callback_query_handler(admin_unban_reject, Text(startswith="admin_unban_reject_"))

    # Потом — открытие заявки
    dp.register_callback_query_handler(admin_unban_open, Text(startswith="admin_unban_"))


