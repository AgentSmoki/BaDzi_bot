from aiogram.fsm.state import State, StatesGroup


class BirthDataForm(StatesGroup):
    waiting_date = State()
    waiting_time = State()
    waiting_city = State()
    waiting_gender = State()
    confirm = State()
    naming = State()
    # Wave 2 — пункт 6 от Богдана: пользователь пишет данные одной
    # строкой ("27.04.88 Севастополь 07:03 утра"), LLM extract парсит
    # и заполняет FSM. Если поля недостаёт — fallback на пошаговый flow.
    waiting_full_text = State()


class ConsultationState(StatesGroup):
    waiting_question = State()
    # Wave 6 / ADR-010: skill-router may request 1-3 clarifying questions
    # before the main LLM call. The handler enters this state and collects
    # text answers one by one; once all are gathered, it resumes the main
    # consultation flow via _continue_consultation_with_skill.
    collecting_clarifications = State()
