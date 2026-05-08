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

    Per-chart actions (вопрос Анастасии, базовый разбор, тарифы) live on
    the chart card itself (`chart_actions_kb`), so the user always knows
    which chart they're acting on. Main menu = navigation only.

    `charts`: list of (chart_id, label) ordered newest-first. Empty list
    falls through gracefully — only "Добавить новую карту" + "Тарифы"
    render.
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

    # "Тарифы" сидит внизу как ненавязчивая ссылка на оплату — не отвлекает
    # от выбора карты, но всегда под рукой.
    builder.button(text="Тарифы", callback_data="menu:pricing")
    rows.append(1)

    builder.adjust(*rows)
    return builder.as_markup()


def chart_actions_kb() -> InlineKeyboardMarkup:
    """Focused inline keyboard attached to a chart photo.

    Order matters — «Получить разбор» сверху как самое ценное бесплатное
    действие, потом «Задать вопрос», потом тарифы и навигация. `menu:ask`
    и `chart:interpret` опираются на `chart_id`, который пиннится в FSM
    в `chart:open:{id}` / `confirm:calc`.
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="Получить разбор моей карты", callback_data="chart:interpret")
    builder.button(text="Задать вопрос Анастасии", callback_data="menu:ask")
    builder.button(text="Тарифы", callback_data="menu:pricing")
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


def pricing_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Месяц — 290 ₽", callback_data="pay:monthly")
    builder.button(text="3 месяца — 990 ₽", callback_data="pay:quarterly")
    builder.button(text="Год — 2 490 ₽", callback_data="pay:annual")
    builder.button(text="Назад", callback_data="menu:back")
    builder.adjust(1)
    return builder.as_markup()


__all__ = [
    "back_to_time_kb",
    "chart_actions_kb",
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
