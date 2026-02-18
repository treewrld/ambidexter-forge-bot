from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Список услуг (можно расширять)
SERVICES = [
    {
        "code": "gates",
        "name": "Кованые ворота",
        "price": "от 500 €",
        "description": "Индивидуальный дизайн, ручная ковка, монтаж.",
    },
    {
        "code": "fence",
            "name": "Кованые заборы",
            "price": "от 300 €",
            "description": "Секции, столбы, декоративные элементы.",
    },
    {
        "code": "railings",
        "name": "Перила и ограждения",
        "price": "от 200 €",
        "description": "Лестницы, балконы, террасы.",
    },
    {
        "code": "decor",
        "name": "Декор и элементы интерьера",
        "price": "от 100 €",
        "description": "Подсвечники, решётки, арт-объекты.",
    },
]


def get_services_list_text() -> str:
    lines = ["<b>Наши услуги:</b>\n"]
    for s in SERVICES:
        lines.append(
            f"🔹 <b>{s['name']}</b>\n"
            f"💰 Цена: <i>{s['price']}</i>\n"
            f"{s['description']}\n"
        )
    return "\n".join(lines)


def get_services_inline_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    for s in SERVICES:
        kb.add(
            InlineKeyboardButton(
                text=f"{s['name']} ({s['price']})",
                callback_data=f"service_{s['code']}",
            )
        )
    return kb
