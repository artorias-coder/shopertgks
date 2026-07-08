from aiogram.fsm.state import State, StatesGroup


class OrderForm(StatesGroup):
    name = State()
    phone = State()
    city = State()
    delivery = State()
    shop = State()
    comment = State()
    confirm = State()


class RequestForm(StatesGroup):
    name = State()
    phone = State()
    shop = State()
    confirm = State()


class TradeInForm(StatesGroup):
    device_type = State()
    model = State()
    battery = State()
    condition = State()
    confirm = State()


class SupportState(StatesGroup):
    question = State()


class SearchState(StatesGroup):
    query = State()


class AdminBroadcast(StatesGroup):
    text = State()
    preview = State()
