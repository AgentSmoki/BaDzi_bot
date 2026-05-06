from aiogram.fsm.state import State, StatesGroup


class BirthDataForm(StatesGroup):
    waiting_date = State()
    waiting_time = State()
    waiting_city = State()
    waiting_gender = State()
    confirm = State()
    naming = State()


class ConsultationState(StatesGroup):
    waiting_question = State()
