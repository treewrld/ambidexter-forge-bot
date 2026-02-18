from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from config import ADMIN_ID


# ====== ГЛАВНОЕ МЕНЮ ======

def get_main_menu(user_id: int) -> ReplyKeyboardMarkup:
    return get_admin_menu() if user_id == ADMIN_ID else get_client_menu()


def get_client_menu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)

    kb.row(
        KeyboardButton("🔨 Сделать заказ"),
        KeyboardButton("📋 Наши услуги"),
    )
    kb.row(
        KeyboardButton("🧩 Свой заказ"),
    )
    kb.row(
        KeyboardButton("ℹ️ О нас"),
        KeyboardButton("📞 Контакты"),
    )

    return kb


def get_admin_menu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)

    kb.row(
        KeyboardButton("📥 Все заказы"),
        KeyboardButton("📊 Статистика"),
    )
    kb.row(
        KeyboardButton("🚫 Черный список"),
        KeyboardButton("📨 Заявки на разбан"),
    )
    kb.row(
        KeyboardButton("👁 Перейти в режим клиента"),
    )

    return kb


def get_admin_client_menu() -> ReplyKeyboardMarkup:
    """
    Меню, когда админ переключился в режим клиента,
    но с кнопкой возврата в админку.
    """
    kb = ReplyKeyboardMarkup(resize_keyboard=True)

    kb.row(
        KeyboardButton("🔨 Сделать заказ"),
        KeyboardButton("📋 Наши услуги"),
    )
    kb.row(
        KeyboardButton("🧩 Свой заказ"),
    )
    kb.row(
        KeyboardButton("ℹ️ О нас"),
        KeyboardButton("📞 Контакты"),
    )
    kb.row(
        KeyboardButton("⚙️ Вернуться в админку"),
    )

    return kb


# ====== СПОСОБ СВЯЗИ ======

def get_contact_method_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)

    kb.add(
        InlineKeyboardButton("📱 Телефон", callback_data="contact_phone"),
        InlineKeyboardButton("💬 Telegram", callback_data="contact_telegram"),
    )
    kb.add(
        InlineKeyboardButton("✉️ Email", callback_data="contact_email"),
    )

    return kb


# ====== ПОДТВЕРЖДЕНИЕ ЗАКАЗА ======

def get_confirm_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)

    kb.add(
        InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_yes"),
        InlineKeyboardButton("❌ Отменить", callback_data="confirm_no"),
    )

    return kb


# ====== СПИСОК ЗАКАЗОВ (АДМИН) ======

def get_orders_list_kb(orders, page: int, total: int, per_page: int = 3):
    kb = InlineKeyboardMarkup(row_width=1)

    if not orders:
        kb.add(InlineKeyboardButton("Нет заказов", callback_data="noop"))
        return kb

    for o in orders:
        title = o["title"] if o["type"] == "custom" else o["service_code"]
        status = o["status"]
        kb.add(
            InlineKeyboardButton(
                text=f"#{o['id']} — {title} ({status})",
                callback_data=f"admin_order_{o['id']}",
            )
        )

    pages = (total + per_page - 1) // per_page
    nav = []

    if page > 1:
        nav.append(
            InlineKeyboardButton(
                "⬅️ Назад", callback_data=f"admin_orders_page_{page-1}"
            )
        )
    if page < pages:
        nav.append(
            InlineKeyboardButton(
                "Вперёд ➡️", callback_data=f"admin_orders_page_{page+1}"
            )
        )

    if nav:
        kb.row(*nav)

    kb.add(InlineKeyboardButton("🔙 В меню", callback_data="admin_back_menu"))

    return kb


# ====== КАРТОЧКА ЗАКАЗА (АДМИН) ======
def get_order_actions_kb(order_id: int):
    kb = InlineKeyboardMarkup(row_width=2)

    kb.add(
        InlineKeyboardButton(
            "🟡 В работу",
            callback_data=f"admin_status_{order_id}_in_progress",
        ),
        InlineKeyboardButton(
            "🟢 Готов",
            callback_data=f"admin_status_{order_id}_done",
        ),
    )
    kb.add(
        InlineKeyboardButton(
            "🏁 Завершить",
            callback_data=f"admin_status_{order_id}_done",
        ),
    )
    kb.add(
        InlineKeyboardButton(
            "❌ Отменить",
            callback_data=f"admin_status_{order_id}_cancelled",
        ),
    )
    kb.add(
        InlineKeyboardButton("🔙 Назад", callback_data="admin_orders_page_1"),
    )

    return kb


# ====== КАПЧА ======

def get_captcha_kb(options) -> InlineKeyboardMarkup:
    """
    options: список кортежей (text, callback_data)
    """
    kb = InlineKeyboardMarkup(row_width=2)
    for text, data in options:
        kb.add(InlineKeyboardButton(text, callback_data=data))
    return kb


# ====== ЗАБАНЕННЫЙ ПОЛЬЗОВАТЕЛЬ ======

def get_banned_user_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("Связаться с админом", callback_data="banned_contact_admin"),
    )
    kb.add(
        InlineKeyboardButton("Почему меня забанили?", callback_data="banned_why"),
    )
    return kb


# ====== ЗАЯВКИ НА РАЗБАН (АДМИН) ======

def get_unban_requests_kb(requests) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    if not requests:
        kb.add(InlineKeyboardButton("Нет заявок", callback_data="noop"))
        kb.add(InlineKeyboardButton("🔙 В меню", callback_data="admin_back_menu"))
        return kb

    for r in requests:
        kb.add(
            InlineKeyboardButton(
                text=f"#{r['id']} — {r['tg_id']} ({r['status']})",
                callback_data=f"admin_unban_{r['id']}",
            )
        )

    kb.add(InlineKeyboardButton("🔙 В меню", callback_data="admin_back_menu"))
    return kb


def get_unban_actions_kb(request_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(
            "✅ Разбанить",
            callback_data=f"admin_unban_approve_{request_id}",
        ),
        InlineKeyboardButton(
            "❌ Отклонить",
            callback_data=f"admin_unban_reject_{request_id}",
        ),
    )
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="admin_unban_list"))
    return kb
