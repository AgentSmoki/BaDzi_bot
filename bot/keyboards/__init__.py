import uuid

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def new_user_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Рассчитать карту", callback_data="menu:calc")
    return builder.as_markup()


def time_skip_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Не знаю время", callback_data="time:skip")
    return builder.as_markup()


def returning_user_kb(*, chart_id: uuid.UUID, chart_label: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Добавить новую карту", callback_data="menu:calc")
    builder.button(text=f"Открыть: {chart_label}", callback_data=f"chart:open:{chart_id}")
    builder.button(text="Все мои карты", callback_data="menu:all_charts")
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
    "main_menu_kb",
    "new_user_kb",
    "pricing_kb",
    "returning_user_kb",
    "time_skip_kb",
    "topics_kb",
]
