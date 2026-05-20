"""Persistent reply keyboard at the bottom of the chat (Wave 6-followup
2026-05-20, пункт 4 от Богдана).

Three buttons always visible:
    [Главное меню] [Мои карты]
    [Поддержка]

Set ``one_time_keyboard=False`` so it stays after the user taps; users
who don't want it can hide via the Telegram menu manually.

Handlers for these text inputs live in ``bot/routers/start.py`` and
match by ``F.text == "..."``.
"""

from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

REPLY_MAIN = "Главное меню"
REPLY_MY_CHARTS = "Мои карты"
REPLY_SUPPORT = "Поддержка"


def main_reply_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=REPLY_MAIN), KeyboardButton(text=REPLY_MY_CHARTS)],
            [KeyboardButton(text=REPLY_SUPPORT)],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Напишите вопрос или нажмите кнопку ниже",
    )
