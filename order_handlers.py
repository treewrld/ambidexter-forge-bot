from utils.sanitize import sanitize_text
from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text

from keyboards import (
    get_client_menu,
    get_contact_method_kb,
    get_confirm_kb,
    get_main_menu,
    get_admin_menu,
    get_captcha_kb,
    get_banned_user_kb,
)
from states import (
    ContactMethodState,
    OrderExistingServiceState,
    CustomOrderState,
    CaptchaState,
    UnbanRequestState,
)
from services import (
    SERVICES,
    get_services_list_text,
    get_services_inline_keyboard,
)
from database import (
    get_or_create_client,
    add_order,
    is_user_banned,
    ban_user,
    get_captcha_attempts,
    increment_captcha_attempts,
    reset_captcha_attempts,
    add_unban_request,
    get_ban_reason,
)
from config import ADMIN_ID

import random


CONTACT_PROMPTS = {
    "phone": "Введите номер телефона:",
    "telegram": "Введите @username:",
    "email": "Введите email:",
}

CONTACT_LABELS = {
    "phone": "Телефон",
    "telegram": "Telegram",
    "email": "Email",
}


CAPTCHA_QUESTIONS = [
    {
        "question": "Выберите молот, чтобы продолжить 🔨",
        "options": [
            ("🔨", True),
            ("🍏", False),
            ("🚗", False),
            ("🐱", False),
        ],
    },
    {
        "question": "Где здесь молоты? Выберите правильный вариант.",
        "options": [
            ("🪨", False),
            ("🧊", False),
            ("⚒️", True),
            ("📦", False),
        ],
    },
    {
        "question": "Выберите огонь, чтобы разжечь кузню 🔥",
        "options": [
            ("🌊", False),
            ("🍞", False),
            ("🔥", True),
            ("🌳", False),
        ],
    },
]


def get_service_by_code(code: str):
    for s in SERVICES:
        if s["code"] == code:
            return s
    return None


# ====== ВСПОМОГАТЕЛЬНОЕ: ПРОВЕРКА БАНА ======

async def check_ban_and_block(message: types.Message):
    if is_user_banned(message.from_user.id):
        reason = get_ban_reason(message.from_user.id) or "Многократное не прохождение проверки."
        await message.answer(
            "🚫 Доступ к боту временно ограничен.\n\n"
            f"Причина: <b>{reason}</b>\n\n"
            "Если вы считаете, что это ошибка, вы можете отправить заявку на разбан.",
            reply_markup=get_banned_user_kb(),
        )
        return True
    return False


async def check_ban_and_block_callback(callback: types.CallbackQuery):
    if is_user_banned(callback.from_user.id):
        reason = get_ban_reason(callback.from_user.id) or "Многократное не прохождение проверки."
        await callback.message.answer(
            "🚫 Доступ к боту временно ограничен.\n\n"
            f"Причина: <b>{reason}</b>\n\n"
            "Если вы считаете, что это ошибка, вы можете отправить заявку на разбан.",
            reply_markup=get_banned_user_kb(),
        )
        await callback.answer()
        return True
    return False


# ====== КАПЧА ======

def build_captcha():
    q = random.choice(CAPTCHA_QUESTIONS)
    correct_index = None
    options = []
    for idx, (text, is_correct) in enumerate(q["options"]):
        data = f"captcha_{idx}"
        options.append((text, data))
        if is_correct:
            correct_index = idx
    return q["question"], options, correct_index


async def start_captcha(message: types.Message, state: FSMContext):
    await CaptchaState.start.set()
    question, options, correct_index = build_captcha()
    await state.update_data(captcha_correct=correct_index, captcha_stage="start")
    await message.answer(
        "Привет! 😊 Перед тем как продолжить, давай убедимся, что ты не бот.\n\n"
        f"{question}",
        reply_markup=get_captcha_kb(options),
    )


async def start_captcha_before_confirm(callback_or_message, state: FSMContext, order_type: str):
    # order_type: "service" или "custom"
    await CaptchaState.confirm.set()
    question, options, correct_index = build_captcha()
    await state.update_data(
        captcha_correct=correct_index,
        captcha_stage="confirm",
        captcha_order_type=order_type,
    )

    text = "Небольшая проверка перед подтверждением заказа 🙂\n\n" + question

    if isinstance(callback_or_message, types.CallbackQuery):
        await callback_or_message.message.answer(
            text,
            reply_markup=get_captcha_kb(options),
        )
        await callback_or_message.answer()
    else:
        await callback_or_message.answer(
            text,
            reply_markup=get_captcha_kb(options),
        )


async def show_order_confirm_after_captcha(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    service = get_service_by_code(data["service_code"])
    contact_label = CONTACT_LABELS[data["contact_method"]]

    await OrderExistingServiceState.confirm.set()
    await callback.message.answer(
        "<b>Проверьте заказ:</b>\n\n"
        f"Имя: <b>{data.get('user_name') or '-'}</b>\n"
        f"Услуга: <b>{service['name']}</b>\n"
        f"Описание: {data['description']}\n"
        f"{contact_label}: {data['contact_value']}",
        reply_markup=get_confirm_kb(),
    )


async def show_custom_confirm_after_captcha(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    contact_label = CONTACT_LABELS[data["contact_method"]]

    await CustomOrderState.confirm.set()
    await callback.message.answer(
        "<b>Проверьте заказ:</b>\n\n"
        f"Имя: <b>{data.get('user_name') or '-'}</b>\n"
        f"Название: <b>{data['title']}</b>\n"
        f"Описание: {data['description']}\n"
        f"Бюджет: {data['budget']}\n"
        f"Сроки: {data['deadline']}\n"
        f"{contact_label}: {data['contact_value']}",
        reply_markup=get_confirm_kb(),
    )


async def captcha_answer(callback: types.CallbackQuery, state: FSMContext):
    if await check_ban_and_block_callback(callback):
        return

    data = await state.get_data()
    correct_index = data.get("captcha_correct")
    stage = data.get("captcha_stage")
    order_type = data.get("captcha_order_type")

    chosen = int(callback.data.replace("captcha_", ""))

    if chosen == correct_index:
        # Успех
        reset_captcha_attempts(callback.from_user.id)

        if stage == "start":
            # завершаем только стартовую капчу
            await state.finish()
            await callback.message.answer("Отлично! 🔥 Проверка пройдена.")
            await callback.message.answer(
                "Выберите действие:",
                reply_markup=get_client_menu()
            )
        elif stage == "confirm":
            # данные заказа должны сохраниться, state не очищаем
            if order_type == "service":
                # спрашиваем имя перед подтверждением заказа готовой услуги
                await OrderExistingServiceState.user_name.set()
                await callback.message.answer("Как к вам обращаться?")
            elif order_type == "custom":
                # спрашиваем имя перед подтверждением кастомного заказа
                await CustomOrderState.user_name.set()
                await callback.message.answer("Как к вам обращаться?")
            else:
                await callback.message.answer("Проверка пройдена, но тип заказа не определён.")
        await callback.answer("Верно! Продолжаем 👌")
        return

    # Ошибка
    attempts = increment_captcha_attempts(callback.from_user.id)
    remaining = max(0, 5 - attempts)

    if attempts >= 5:
        ban_user(callback.from_user.id, "Не прошёл капчу 5 раз.")
        await state.finish()
        await callback.message.answer(
            "🚫 Вы не прошли проверку 5 раз.\n"
            "Доступ к боту временно ограничен.",
            reply_markup=get_banned_user_kb(),
        )
        await callback.answer("Вы заблокированы.")
        return

    # предупреждение
    await callback.message.answer(
        f"Ответ неверный 😔\n"
        f"Попыток: <b>{attempts}</b> из 5.\n"
        f"Осталось: <b>{remaining}</b>.\n"
        "Попробуем ещё раз!",
    )

    # новая капча
    question, options, correct_index = build_captcha()
    await state.update_data(captcha_correct=correct_index, captcha_stage=stage, captcha_order_type=order_type)
    await callback.message.answer(
        question,
        reply_markup=get_captcha_kb(options),
    )
    await callback.answer()


# ====== /start ======

async def cmd_start(message: types.Message, state: FSMContext):
    await state.finish()

    if message.from_user.id == ADMIN_ID:
        await message.answer(
            "⚙️ <b>Админ-панель Кузнечной Мастерской Амбидекстора</b>",
            reply_markup=get_admin_menu(),
        )
        return

    if await check_ban_and_block(message):
        return

    # запускаем капчу
    await start_captcha(message, state)


# ====== БАЗОВЫЕ ХЕНДЛЕРЫ ======

async def show_services(message: types.Message):
    if await check_ban_and_block(message):
        return
    await message.answer(get_services_list_text())


async def about_us(message: types.Message):
    if await check_ban_and_block(message):
        return
    await message.answer(
        "<b>Кузнечная Мастерская Амбидекстора</b>\n\n"
        "🔥 Художественная ковка\n"
        "🔥 Индивидуальные проекты\n"
        "🔥 Авторский стиль\n"
        "🔥 Ручная работа"
    )


async def contacts(message: types.Message):
    if await check_ban_and_block(message):
        return
    await message.answer(
        "<b>Контакты:</b>\n"
        "Email: ognenukovcheg@gmail.com\n"
        "Телефон: +7 (915) 350 24 76"
    )


# ====== ЗАКАЗ ГОТОВОЙ УСЛУГИ ======

async def make_order(message: types.Message, state: FSMContext):
    if await check_ban_and_block(message):
        return
    await message.answer(
        "Выберите услугу:",
        reply_markup=get_services_inline_keyboard(),
    )


async def choose_service(callback: types.CallbackQuery, state: FSMContext):
    if await check_ban_and_block_callback(callback):
        return

    code = callback.data.replace("service_", "")
    service = get_service_by_code(code)

    if not service:
        await callback.answer("Услуга не найдена", show_alert=True)
        return

    await state.update_data(service_code=code)

    await OrderExistingServiceState.description.set()
    await callback.message.answer(
        f"Вы выбрали: <b>{service['name']}</b>\n"
        f"Цена: <i>{service['price']}</i>\n\n"
        "Опишите заказ:"
    )
    await callback.answer()


async def order_description(message: types.Message, state: FSMContext):
    if await check_ban_and_block(message):
        return

    desc = sanitize_text(message.text)
    await state.update_data(description=desc)

    await ContactMethodState.method.set()
    await message.answer("Выберите способ связи:", reply_markup=get_contact_method_kb())


async def contact_method(callback: types.CallbackQuery, state: FSMContext):
    if await check_ban_and_block_callback(callback):
        return

    method = callback.data.replace("contact_", "")
    await state.update_data(contact_method=method)

    await ContactMethodState.value.set()
    await callback.message.answer(CONTACT_PROMPTS[method])
    await callback.answer()


async def contact_value(message: types.Message, state: FSMContext):
    if await check_ban_and_block(message):
        return

    value = sanitize_text(message.text)
    await state.update_data(contact_value=value)

    # капча перед подтверждением заказа
    await start_captcha_before_confirm(message, state, order_type="service")


# ====== ИМЯ ДЛЯ ГОТОВОЙ УСЛУГИ ======

async def order_user_name(message: types.Message, state: FSMContext):
    if await check_ban_and_block(message):
        return

    name = sanitize_text(message.text)
    await state.update_data(user_name=name)

    data = await state.get_data()
    service = get_service_by_code(data["service_code"])
    contact_label = CONTACT_LABELS[data["contact_method"]]

    await OrderExistingServiceState.confirm.set()
    await message.answer(
        "<b>Проверьте заказ:</b>\n\n"
        f"Имя: <b>{name}</b>\n"
        f"Услуга: <b>{service['name']}</b>\n"
        f"Описание: {data['description']}\n"
        f"{contact_label}: {data['contact_value']}",
        reply_markup=get_confirm_kb(),
    )


async def confirm_order(callback: types.CallbackQuery, state: FSMContext):
    if await check_ban_and_block_callback(callback):
        return

    choice = callback.data.replace("confirm_", "")

    if choice == "no":
        await state.finish()
        await callback.message.edit_text("❌ Заказ отменён.")
        await callback.message.answer(
            "Выберите действие:", reply_markup=get_client_menu()
        )
        await callback.answer()
        return

    data = await state.get_data()
    service = get_service_by_code(data["service_code"])

    client_id = get_or_create_client(
        tg_id=callback.from_user.id,
        username=callback.from_user.username,
        name=data.get("user_name"),
    )

    order_id = add_order(
        client_id=client_id,
        type_="service",
        service_code=data["service_code"],
        title=None,
        description=data["description"],
        budget=None,
        deadline=None,
        contact_method=data["contact_method"],
        contact_value=data["contact_value"],
    )

    username = callback.from_user.username
    tg_link = f"@{username}" if username else f"tg://user?id={callback.from_user.id}"

    order_text = (
        f"📥 <b>Новый заказ #{order_id}</b>\n\n"
        f"👤 Имя: <b>{data.get('user_name')}</b> "
        f"({tg_link}, ID: <code>{callback.from_user.id}</code>)\n\n"
        f"Услуга: <b>{service['name']}</b>\n"
        f"Описание: {data['description']}\n"
        f"Контакт: {data['contact_value']}"
    )
    await callback.bot.send_message(ADMIN_ID, order_text)

    await callback.message.edit_text("🔥 Заказ отправлен! Мы свяжемся с вами.")
    await callback.message.answer(
        "Выберите действие:", reply_markup=get_client_menu()
    )

    await state.finish()
    await callback.answer()


# ====== КАСТОМНЫЙ ЗАКАЗ ======

async def custom_order(message: types.Message, state: FSMContext):
    if await check_ban_and_block(message):
        return

    await CustomOrderState.title.set()
    await message.answer("Введите название заказа:")


async def custom_title(message: types.Message, state: FSMContext):
    if await check_ban_and_block(message):
        return

    title = sanitize_text(message.text)
    await state.update_data(title=title)

    await CustomOrderState.description.set()
    await message.answer("Опишите заказ подробно:")


async def custom_desc(message: types.Message, state: FSMContext):
    if await check_ban_and_block(message):
        return

    desc = sanitize_text(message.text)
    await state.update_data(description=desc)

    await CustomOrderState.budget.set()
    await message.answer("Укажите бюджет:")


async def custom_budget(message: types.Message, state: FSMContext):
    if await check_ban_and_block(message):
        return

    budget = sanitize_text(message.text)
    await state.update_data(budget=budget)

    await CustomOrderState.deadline.set()
    await message.answer("Укажите сроки:")


async def custom_deadline(message: types.Message, state: FSMContext):
    if await check_ban_and_block(message):
        return

    deadline = sanitize_text(message.text)
    await state.update_data(deadline=deadline)

    await CustomOrderState.contact_method.set()
    await message.answer("Выберите способ связи:", reply_markup=get_contact_method_kb())


async def custom_contact_method(callback: types.CallbackQuery, state: FSMContext):
    if await check_ban_and_block_callback(callback):
        return

    method = callback.data.replace("contact_", "")
    await state.update_data(contact_method=method)

    await CustomOrderState.contact_value.set()
    await callback.message.answer(CONTACT_PROMPTS[method])
    await callback.answer()


async def custom_contact_value(message: types.Message, state: FSMContext):
    if await check_ban_and_block(message):
        return

    value = sanitize_text(message.text)
    await state.update_data(contact_value=value)

    # капча перед подтверждением кастомного заказа
    await start_captcha_before_confirm(message, state, order_type="custom")


# ====== ИМЯ ДЛЯ КАСТОМНОГО ЗАКАЗА ======

async def custom_user_name(message: types.Message, state: FSMContext):
    if await check_ban_and_block(message):
        return

    name = sanitize_text(message.text)
    await state.update_data(user_name=name)

    data = await state.get_data()
    contact_label = CONTACT_LABELS[data["contact_method"]]

    await CustomOrderState.confirm.set()
    await message.answer(
        "<b>Проверьте заказ:</b>\n\n"
        f"Имя: <b>{name}</b>\n"
        f"Название: <b>{data['title']}</b>\n"
        f"Описание: {data['description']}\n"
        f"Бюджет: {data['budget']}\n"
        f"Сроки: {data['deadline']}\n"
        f"{contact_label}: {data['contact_value']}",
        reply_markup=get_confirm_kb(),
    )


async def confirm_custom(callback: types.CallbackQuery, state: FSMContext):
    if await check_ban_and_block_callback(callback):
        return

    choice = callback.data.replace("confirm_", "")

    if choice == "no":
        await state.finish()
        await callback.message.edit_text("❌ Заказ отменён.")
        await callback.message.answer(
            "Выберите действие:", reply_markup=get_client_menu()
        )
        await callback.answer()
        return

    data = await state.get_data()

    client_id = get_or_create_client(
        tg_id=callback.from_user.id,
        username=callback.from_user.username,
        name=data.get("user_name"),
    )

    order_id = add_order(
        client_id=client_id,
        type_="custom",
        service_code=None,
        title=data["title"],
        description=data["description"],
        budget=data["budget"],
        deadline=data["deadline"],
        contact_method=data["contact_method"],
        contact_value=data["contact_value"],
    )

    username = callback.from_user.username
    tg_link = f"@{username}" if username else f"tg://user?id={callback.from_user.id}"

    order_text = (
        f"📥 <b>Новый кастомный заказ #{order_id}</b>\n\n"
        f"👤 Имя: <b>{data.get('user_name')}</b> "
        f"({tg_link}, ID: <code>{callback.from_user.id}</code>)\n\n"
        f"Название: <b>{data['title']}</b>\n"
        f"Описание: {data['description']}\n"
        f"Бюджет: {data['budget']}\n"
        f"Сроки: {data['deadline']}\n"
        f"Контакт: {data['contact_value']}"
    )
    await callback.bot.send_message(ADMIN_ID, order_text)

    await callback.message.edit_text("🔥 Заказ отправлен! Мы свяжемся с вами.")
    await callback.message.answer(
        "Выберите действие:", reply_markup=get_client_menu()
    )

    await state.finish()
    await callback.answer()


# ====== ЗАБАНЕННЫЙ ПОЛЬЗОВАТЕЛЬ: КНОПКИ ======

async def banned_contact_admin(callback: types.CallbackQuery, state: FSMContext):
    await UnbanRequestState.waiting_reason.set()
    await callback.message.answer(
        "Опишите, пожалуйста, почему вы считаете, что бан был ошибочным.\n"
        "Это сообщение увидит администратор.",
    )
    await callback.answer()


async def banned_why(callback: types.CallbackQuery, state: FSMContext):
    reason = get_ban_reason(callback.from_user.id) or "Причина не указана."
    await callback.message.answer(
        "Причина блокировки:\n\n"
        f"<b>{reason}</b>"
    )
    await callback.answer()


async def unban_request_reason(message: types.Message, state: FSMContext):
    reason = sanitize_text(message.text)
    add_unban_request(message.from_user.id, reason)
    await state.finish()

    await message.answer(
        "✅ Ваша заявка на разбан отправлена администратору.\n"
        "Ожидайте решения.",
    )


# ====== FALLBACK ======

async def fallback(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        return

    if await check_ban_and_block(message):
        return

    await message.answer(
        "Команда не распознана. Воспользуйтесь меню ниже.",
        reply_markup=get_main_menu(message.from_user.id),
    )


# ====== РЕГИСТРАЦИЯ ХЕНДЛЕРОВ ======

def register_order_handlers(dp: Dispatcher):
    dp.register_message_handler(cmd_start, commands=["start"], state="*")

    dp.register_message_handler(show_services, Text(equals="📋 Наши услуги"))
    dp.register_message_handler(about_us, Text(equals="ℹ️ О нас"))
    dp.register_message_handler(contacts, Text(equals="📞 Контакты"))

    # капча
    dp.register_callback_query_handler(
        captcha_answer, Text(startswith="captcha_"), state=CaptchaState
    )

    # забаненный пользователь
    dp.register_callback_query_handler(
        banned_contact_admin, Text(equals="banned_contact_admin")
    )
    dp.register_callback_query_handler(
        banned_why, Text(equals="banned_why")
    )
    dp.register_message_handler(
        unban_request_reason, state=UnbanRequestState.waiting_reason
    )

    # заказ готовой услуги
    dp.register_message_handler(make_order, Text(equals="🔨 Сделать заказ"))
    dp.register_callback_query_handler(choose_service, Text(startswith="service_"))
    dp.register_message_handler(
        order_description, state=OrderExistingServiceState.description
    )

    dp.register_callback_query_handler(
        contact_method,
        Text(startswith="contact_"),
        state=ContactMethodState.method,
    )
    dp.register_message_handler(
        contact_value, state=ContactMethodState.value
    )

    # имя для готовой услуги
    dp.register_message_handler(
        order_user_name, state=OrderExistingServiceState.user_name
    )

    dp.register_callback_query_handler(
        confirm_order,
        Text(startswith="confirm_"),
        state=OrderExistingServiceState.confirm,
    )

    # кастомный заказ
    dp.register_message_handler(custom_order, Text(equals="🧩 Свой заказ"))
    dp.register_message_handler(
        custom_title, state=CustomOrderState.title
    )
    dp.register_message_handler(
        custom_desc, state=CustomOrderState.description
    )
    dp.register_message_handler(
        custom_budget, state=CustomOrderState.budget
    )
    dp.register_message_handler(
        custom_deadline, state=CustomOrderState.deadline
    )

    dp.register_callback_query_handler(
        custom_contact_method,
        Text(startswith="contact_"),
        state=CustomOrderState.contact_method,
    )
    dp.register_message_handler(
        custom_contact_value, state=CustomOrderState.contact_value
    )

    # имя для кастомного заказа
    dp.register_message_handler(
        custom_user_name, state=CustomOrderState.user_name
    )

    dp.register_callback_query_handler(
        confirm_custom,
        Text(startswith="confirm_"),
        state=CustomOrderState.confirm,
    )

