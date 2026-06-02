import uuid

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def new_user_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Начнём", callback_data="menu:calc")
    return builder.as_markup()


def time_step_kb() -> InlineKeyboardMarkup:
    """After date is accepted (or on time-invalid retry) — user is at time step."""
    builder = InlineKeyboardBuilder()
    builder.button(text="Не знаю время", callback_data="time:skip")
    builder.button(text="Изменить дату", callback_data="edit:date")
    builder.adjust(1)
    return builder.as_markup()


def back_to_time_kb() -> InlineKeyboardMarkup:
    """After time is accepted — user is at city step."""
    builder = InlineKeyboardBuilder()
    builder.button(text="Изменить время", callback_data="edit:time")
    return builder.as_markup()


def city_choice_kb(options: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for label, callback in options:
        builder.button(text=label[:60], callback_data=callback)
    builder.button(text="Не тот город — ввести заново", callback_data="city:retry")
    builder.button(text="Изменить время", callback_data="edit:time")
    builder.adjust(1)
    return builder.as_markup()


def gender_kb() -> InlineKeyboardMarkup:
    """After city is accepted — user is at gender step."""
    builder = InlineKeyboardBuilder()
    builder.button(text="Мужской", callback_data="gender:male")
    builder.button(text="Женский", callback_data="gender:female")
    builder.button(text="Изменить город", callback_data="edit:city")
    builder.adjust(2, 1)
    return builder.as_markup()


def confirm_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Рассчитать", callback_data="confirm:calc")
    builder.button(text="Изменить", callback_data="edit:menu")
    builder.adjust(1)
    return builder.as_markup()


def edit_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Дату", callback_data="edit:date")
    builder.button(text="Время", callback_data="edit:time")
    builder.button(text="Город", callback_data="edit:city")
    builder.button(text="Пол", callback_data="edit:gender")
    builder.button(text="Отмена", callback_data="edit:cancel")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def name_skip_kb() -> InlineKeyboardMarkup:
    """Used after the chart is calculated — user can name the chart or skip."""
    builder = InlineKeyboardBuilder()
    builder.button(text="Пропустить", callback_data="name:skip")
    return builder.as_markup()


CHARTS_PER_PAGE = 10


def returning_user_kb(
    *,
    charts: list[tuple[uuid.UUID, str]],
    page: int = 0,
) -> InlineKeyboardMarkup:
    """Main menu for returning users — just the chart list.

    «Тарифы» намеренно скрыты — они появляются только когда пользователь
    упирается в free-tier лимит, а не как пункт меню. Per-chart actions
    (вопрос, базовый разбор) живут на самой карте.

    `charts`: list of (chart_id, label) ordered newest-first.
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="Добавить новую карту", callback_data="menu:calc")

    start = page * CHARTS_PER_PAGE
    end = start + CHARTS_PER_PAGE
    page_charts = charts[start:end]
    for chart_id, label in page_charts:
        builder.button(text=label[:60], callback_data=f"chart:open:{chart_id}")

    rows = [1] + [1] * len(page_charts)
    nav_buttons = 0
    if page > 0:
        builder.button(text="◀ Назад", callback_data=f"charts:page:{page - 1}")
        nav_buttons += 1
    if end < len(charts):
        builder.button(text="Вперёд ▶", callback_data=f"charts:page:{page + 1}")
        nav_buttons += 1
    if nav_buttons:
        rows.append(nav_buttons)

    builder.adjust(*rows)
    return builder.as_markup()


def chart_actions_kb(chart_id: uuid.UUID | None = None) -> InlineKeyboardMarkup:
    """Focused inline keyboard attached to a chart photo (pre-interpretation).

    «Тарифы» намеренно скрыты — они появятся только когда пользователь
    упирается в лимит free-tier (после 1.12). Сейчас фокус на бесплатных
    действиях, чтобы пользователь увидел ценность до оплаты.

    When ``chart_id`` is supplied, adds «Прогнозы» (Wave 3d) and
    «🗑 Удалить карту» (Wave 1b) buttons.
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="Получить разбор карты", callback_data="chart:interpret")
    builder.button(text="Задать вопрос по карте", callback_data="menu:ask")
    if chart_id is not None:
        builder.button(text="📅 Прогнозы", callback_data=f"forecast:show:{chart_id}")
        builder.button(text="📔 Дневник", callback_data=f"journal:show:{chart_id}")
        builder.button(
            text="🎓 Загрузить Встречу с Мастером",
            callback_data=f"meeting:show:{chart_id}",
        )
        builder.button(text="🌟 Важные даты", callback_data=f"chart:impdates:{chart_id}")
        builder.button(text="⚙️ Школа по умолчанию", callback_data=f"chart:defschool:{chart_id}")
        builder.button(text="✏️ Переименовать", callback_data=f"chart:rename:{chart_id}")
        builder.button(text="🗑 Удалить карту", callback_data=f"chart:delete:{chart_id}")
    builder.button(text="В меню", callback_data="menu:back")
    builder.adjust(1)
    return builder.as_markup()


def chart_actions_kb_post_interpret(
    chart_id: uuid.UUID | None = None,
) -> InlineKeyboardMarkup:
    """Same as ``chart_actions_kb`` minus «Получить разбор карты».

    Sent after the 6-block base interpretation is delivered — the user
    has already seen it, so re-offering the same button is noise and
    invites accidental re-generation that would burn a free-question
    slot or LLM budget. Re-generation is still available via /start
    (а через chat:open: re-route в start_router).
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="Задать вопрос по карте", callback_data="menu:ask")
    if chart_id is not None:
        builder.button(text="📅 Прогнозы", callback_data=f"forecast:show:{chart_id}")
        builder.button(text="📔 Дневник", callback_data=f"journal:show:{chart_id}")
        builder.button(
            text="🎓 Загрузить Встречу с Мастером",
            callback_data=f"meeting:show:{chart_id}",
        )
        builder.button(text="🌟 Важные даты", callback_data=f"chart:impdates:{chart_id}")
        builder.button(text="⚙️ Школа по умолчанию", callback_data=f"chart:defschool:{chart_id}")
        builder.button(text="✏️ Переименовать", callback_data=f"chart:rename:{chart_id}")
        builder.button(text="🗑 Удалить карту", callback_data=f"chart:delete:{chart_id}")
    builder.button(text="В меню", callback_data="menu:back")
    builder.adjust(1)
    return builder.as_markup()


# ── Wave 3d — Forecast subscription flow ─────────────────────────────────


def forecast_menu_kb(chart_id: uuid.UUID) -> InlineKeyboardMarkup:
    """Menu shown on `forecast:show:<chart_id>` — two plans + active list.

    NB Telegram limits callback_data to 64 bytes UTF-8. UUIDs are 36
    chars, so we use the short prefix ``fc:`` for sub-callbacks that
    don't carry the chart_id (handler reads it from FSM, set by
    ``forecast:show:<chart_id>``)."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Прогноз на месяц — 500 ₽", callback_data="fc:bm")
    builder.button(text="🌅 Прогноз дня + активации — 900 ₽", callback_data="fc:bd")
    builder.button(text="Мои подписки", callback_data="fc:list")
    builder.button(text="↩ Назад к карте", callback_data=f"chart:open:{chart_id}")
    builder.adjust(1)
    return builder.as_markup()


def forecast_monthly_delivery_kb() -> InlineKeyboardMarkup:
    """User picks weekly chunks vs single bulk send. chart_id lives in FSM."""
    builder = InlineKeyboardBuilder()
    builder.button(text="Раз в неделю (4 части)", callback_data="fc:mc:weekly")
    builder.button(text="Прислать всё сразу", callback_data="fc:mc:bulk")
    builder.button(text="↩ Назад", callback_data="fc:back")
    builder.adjust(1)
    return builder.as_markup()


def forecast_daily_hour_kb() -> InlineKeyboardMarkup:
    """User picks send hour (local time)."""
    builder = InlineKeyboardBuilder()
    for hour in (4, 7, 9, 12, 19):
        builder.button(text=f"{hour:02d}:00 моего времени", callback_data=f"fc:dc:{hour}")
    builder.button(text="↩ Назад", callback_data="fc:back")
    builder.adjust(1)
    return builder.as_markup()


def forecast_cancel_kb(subscription_id: uuid.UUID) -> InlineKeyboardMarkup:
    """Cancel confirm dialog for a single subscription row.
    chart_id lives in FSM; only sub_id rides the callback (50 chars)."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🛑 Отменить подписку", callback_data=f"fc:cc:{subscription_id}")
    builder.button(text="Назад", callback_data="fc:list")
    builder.adjust(1)
    return builder.as_markup()


def calc_intro_kb() -> InlineKeyboardMarkup:
    """Shown when the user presses «Рассчитать карту» (menu:calc).

    Default UX (Wave 2): bot invites a single-line entry like
    «27.04.88 Севастополь 07:03 утра». The «Ввести по шагам» button
    is the escape hatch for users who'd rather walk through the
    classic FSM (date → time → city → gender). «В меню» lets the
    user abort the calc flow entirely — без него юзер залипает в
    waiting_full_text FSM без выхода (live regression 2026-05-20
    via @S_Kate2011, screenshot in chat).
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="Ввести по шагам", callback_data="calc:stepwise")
    builder.button(text="В меню", callback_data="menu:back")
    builder.adjust(1)
    return builder.as_markup()


def chart_delete_confirm_kb(chart_id: uuid.UUID) -> InlineKeyboardMarkup:
    """Confirm dialog shown before hard-deleting a chart (Wave 1b).

    The action is irreversible — chart row + cascade on consultations —
    so we always go through a Yes/No prompt instead of deleting on a
    single tap."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🗑 Удалить навсегда",
        callback_data=f"chart:delete_confirm:{chart_id}",
    )
    builder.button(text="Отмена", callback_data="chart:delete_cancel")
    builder.adjust(1)
    return builder.as_markup()


def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Рассчитать карту", callback_data="menu:calc")
    builder.button(text="Задать вопрос", callback_data="menu:ask")
    builder.button(text="Тарифы", callback_data="menu:pricing")
    builder.adjust(1)
    return builder.as_markup()


def topics_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Характер", callback_data="topic:character")
    builder.button(text="Карьера", callback_data="topic:career")
    builder.button(text="Отношения", callback_data="topic:relationships")
    builder.button(text="Прогноз на год", callback_data="topic:forecast")
    builder.button(text="Свободный вопрос", callback_data="topic:free")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def add_partner_chart_kb() -> InlineKeyboardMarkup:
    """Inline kb shown by the skill-router (Wave 6) when the
    relationships skill detects «my husband / my girlfriend» and the
    user's main chart has no ``partner_chart_id`` linked yet.

    Two buttons: «Добавить карту партнёра» (triggers the partner FSM
    flow in bot.routers.birth_data) and «Без неё» (the LLM answers
    generically without the comparison)."""
    builder = InlineKeyboardBuilder()
    builder.button(text="Добавить карту партнёра", callback_data="partner:add")
    builder.button(text="Ответить без неё", callback_data="partner:skip")
    builder.adjust(1)
    return builder.as_markup()


def partner_chart_selector_kb(
    candidates: list[tuple[uuid.UUID, str]],
) -> InlineKeyboardMarkup:
    """Same intent as `add_partner_chart_kb` but offers the user's
    OTHER existing charts as ready-to-link partner candidates first.

    Shown when the relationships skill needs a partner chart AND the
    user already has other charts in their library (excluding the
    current owner chart). Tapping a chart row immediately links it
    via `ChartRepository.set_partner` and resumes the consultation
    — no second FSM walk required.

    Falls back to `partner:add` / `partner:skip` at the bottom so the
    user can still build a fresh partner chart or skip the comparison.

    Caller (consultation router) passes pre-formatted (id, label)
    pairs to keep the keyboards module free of service-layer imports.
    """
    builder = InlineKeyboardBuilder()
    for chart_id, label in candidates:
        # callback_data limit is 64 bytes — «partner:use:` (12) + uuid (36) = 48 ✓
        builder.button(text=label, callback_data=f"partner:use:{chart_id}")
    builder.button(text="➕ Добавить новую карту партнёра", callback_data="partner:add")
    builder.button(text="Ответить без неё", callback_data="partner:skip")
    builder.adjust(1)
    return builder.as_markup()


def school_selector_kb(callback_prefix: str = "school") -> InlineKeyboardMarkup:
    """Wave 7 Phase 2 — three coexisting interpretation schools.

    Shown after «Задать вопрос по карте» / before each new consultation
    turn. The callback_data values are tight enums (``<prefix>:classic`` /
    ``<prefix>:edoha`` / ``<prefix>:modern``).

    ``callback_prefix`` (Wave 7 Phase 2 ext, 2026-05-26):
    - ``"school"`` (default) — для consultation router (handle_school_chosen).
    - ``"fc:ms"`` — для месячного прогноза (handle_monthly_school_confirm).
    - ``"fc:ds"`` — для дневного прогноза (handle_daily_school_confirm).
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="🎓 Классическая", callback_data=f"{callback_prefix}:classic")
    builder.button(text="🌀 Мастер ЭдоХа", callback_data=f"{callback_prefix}:edoha")
    builder.button(text="🧬 Современная", callback_data=f"{callback_prefix}:modern")
    builder.adjust(1)
    return builder.as_markup()


def default_school_kb(chart_id: uuid.UUID, current: str | None = None) -> InlineKeyboardMarkup:
    """Wave 7 / 1.18.14 — per-chart default school picker (chart menu).

    Three schools + «Спрашивать каждый раз» (clears the default) + back.
    The currently-selected option is marked with ✓. Callbacks:
    - ``defschool:set:<school>:<chart_id>`` — persist default
    - ``defschool:clear:<chart_id>`` — clear (ask every consultation)
    """
    labels = {
        "classic": "🎓 Классическая",
        "edoha": "🌀 Мастер ЭдоХа",
        "modern": "🧬 Современная",
    }
    builder = InlineKeyboardBuilder()
    for school, label in labels.items():
        mark = " ✓" if current == school else ""
        builder.button(text=f"{label}{mark}", callback_data=f"defschool:set:{school}:{chart_id}")
    ask_mark = " ✓" if current is None else ""
    builder.button(
        text=f"❓ Спрашивать каждый раз{ask_mark}",
        callback_data=f"defschool:clear:{chart_id}",
    )
    builder.button(text="« Назад к карте", callback_data=f"chart:open:{chart_id}")
    builder.adjust(1)
    return builder.as_markup()


def pricing_kb(*, allow_skip: bool = True) -> InlineKeyboardMarkup:
    """Pricing keyboard shown after the free quota is consumed.

    Wave 7 UX rework (2026-05-24):
    - Тарифные кнопки помечены «(скоро)» и шлют callback_data
      ``pay:disabled:*`` → handler показывает alert «оплата
      подключается». До запуска ЮКассы (1.12.3) кнопки нерабочие,
      но видны клиенту как «обещание».
    - «🔓 Продолжить бесплатно» (бывш. «🔧 Пропустить (тест)») —
      теперь доступна **всем** (не только admin). Раньше gate был
      нужен чтобы избежать абуза тестового флага в проде; сейчас
      ЮКасса не работает в принципе, поэтому skip-режим = единственный
      путь продолжить разговор. При подключении ЮКассы вернуть
      ``allow_skip=False`` (или удалить параметр вместе с handler'ом
      pricing:skip).
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Месяц — 290 ₽ (скоро)", callback_data="pay:disabled:monthly")
    builder.button(text="💳 3 месяца — 990 ₽ (скоро)", callback_data="pay:disabled:quarterly")
    builder.button(text="💳 Год — 2 490 ₽ (скоро)", callback_data="pay:disabled:annual")
    if allow_skip:
        builder.button(text="🔓 Продолжить бесплатно", callback_data="pricing:skip")
    builder.button(text="Назад", callback_data="menu:back")
    builder.adjust(1)
    return builder.as_markup()


__all__ = [
    "add_partner_chart_kb",
    "back_to_time_kb",
    "calc_intro_kb",
    "chart_actions_kb",
    "chart_actions_kb_post_interpret",
    "chart_delete_confirm_kb",
    "city_choice_kb",
    "confirm_kb",
    "edit_menu_kb",
    "forecast_cancel_kb",
    "forecast_daily_hour_kb",
    "forecast_menu_kb",
    "forecast_monthly_delivery_kb",
    "gender_kb",
    "main_menu_kb",
    "name_skip_kb",
    "new_user_kb",
    "partner_chart_selector_kb",
    "pricing_kb",
    "returning_user_kb",
    "time_step_kb",
    "topics_kb",
]
