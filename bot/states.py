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
    # Wave 7 Phase 2 (ADR-011): before each question the user picks an
    # interpretation school (classic / edoha / modern). Handler shows the
    # 3-button selector and waits in this state for the callback. Then
    # transitions to ``waiting_question``. The chosen school is persisted
    # in FSM data as ``chosen_school`` and threaded through skill-router
    # → compose_messages → load_base_prompt(school=...).
    choosing_school = State()
    waiting_question = State()
    # Wave 6 / ADR-010: skill-router may request 1-3 clarifying questions
    # before the main LLM call. The handler enters this state and collects
    # text answers one by one; once all are gathered, it resumes the main
    # consultation flow via _continue_consultation_with_skill.
    collecting_clarifications = State()


class JournalState(StatesGroup):
    """Wave 4 — reflection journal FSM."""

    # Waiting for the user's daily reflection (text or voice). Triggered
    # by «📝 Записать сегодня» button or by the cron reminder.
    waiting_reflection = State()
    # User pasted a voice message; we transcribed it via TeleTranscribe MCP
    # and showed the text — now waiting for «✅ Добавить» / «✏ Изменить».
    confirming_voice_transcript = State()
    # User asked to correct the transcript — second LLM-pass takes the
    # «what to fix» instruction here.
    waiting_correction_instruction = State()


class MasterMeetingState(StatesGroup):
    """Wave 5 — master-meeting upload FSM."""

    # Pasted by the user after the explainer screen. We URL-validate,
    # detect source type, enqueue the background TT-URL transcribe task.
    waiting_url = State()
