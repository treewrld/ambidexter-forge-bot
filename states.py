from aiogram.dispatcher.filters.state import State, StatesGroup


class ContactMethodState(StatesGroup):
    method = State()
    value = State()


class OrderExistingServiceState(StatesGroup):
    service_code = State()
    description = State()
    contact_method = State()
    contact_value = State()
    user_name = State()
    confirm = State()


class CustomOrderState(StatesGroup):
    title = State()
    description = State()
    budget = State()
    deadline = State()
    contact_method = State()
    contact_value = State()
    user_name = State()
    confirm = State()


class CaptchaState(StatesGroup):
    start = State()
    confirm = State()


class UnbanRequestState(StatesGroup):
    waiting_reason = State()
