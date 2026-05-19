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


def chart_actions_kb() -> InlineKeyboardMarkup:
    """Focused inline keyboard attached to a chart photo (pre-interpretation).

    «Тарифы» намеренно скрыты — они появятся только когда пользователь
    упирается в лимит free-tier (после 1.12). Сейчас фокус на бесплатных
    действиях, чтобы пользователь увидел ценность до оплаты.
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="Получить разбор карты", callback_data="chart:interpret")
    builder.button(text="Задать вопрос по карте", callback_data="menu:ask")
    builder.button(text="В меню", callback_data="menu:back")
    builder.adjust(1)
    return builder.as_markup()


def chart_actions_kb_post_interpret() -> InlineKeyboardMarkup:
    """Same as ``chart_actions_kb`` minus «Получить разбор карты».

    Sent after the 6-block base interpretation is delivered — the user
    has already seen it, so re-offering the same button is noise and
    invites accidental re-generation that would burn a free-question
    slot or LLM budget. Re-generation is still available via /start
    (а через chat:open: re-route в start_router).
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="Задать вопрос по карте", callback_data="menu:ask")
    builder.button(text="В меню", callback_data="menu:back")
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


def pricing_kb(*, allow_skip: bool = False) -> InlineKeyboardMarkup:
    """Pricing keyboard shown after the free question is consumed.

    ``allow_skip``: when True, adds a hidden «Пропустить (тест)» button
    that resets ``free_question_used`` so the same user can keep asking
    (admin-only, used during pre-release testing). The handler is
    behind an explicit admin-id check, so a leaked callback_data on
    a non-admin chat is inert.
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="Месяц — 290 ₽", callback_data="pay:monthly")
    builder.button(text="3 месяца — 990 ₽", callback_data="pay:quarterly")
    builder.button(text="Год — 2 490 ₽", callback_data="pay:annual")
    if allow_skip:
        builder.button(text="🔧 Пропустить (тест)", callback_data="pricing:skip")
    builder.button(text="Назад", callback_data="menu:back")
    builder.adjust(1)
    return builder.as_markup()


__all__ = [
    "add_partner_chart_kb",
    "back_to_time_kb",
    "chart_actions_kb",
    "chart_actions_kb_post_interpret",
    "city_choice_kb",
    "confirm_kb",
    "edit_menu_kb",
    "gender_kb",
    "main_menu_kb",
    "name_skip_kb",
    "new_user_kb",
    "pricing_kb",
    "returning_user_kb",
    "time_step_kb",
    "topics_kb",
]
