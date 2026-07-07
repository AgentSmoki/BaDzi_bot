"""Persistent reply keyboard at the bottom of the chat (Wave 6-followup
2026-05-20, пункт 4 от Богдана).

Two buttons always visible:
    [Мои карты] [Поддержка]

«Главное меню» removed 2026-05-20 — дублировало «Мои карты» (обе
вели в один и тот же экран со списком карт).

Handlers for these text inputs live in ``bot/routers/start.py`` and
match by ``F.text == "..."``.
"""

from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

REPLY_MY_CHARTS = "Мои карты"
REPLY_SUPPORT = "Поддержка"


def main_reply_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=REPLY_MY_CHARTS), KeyboardButton(text=REPLY_SUPPORT)],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Напишите вопрос или нажмите кнопку ниже",
    )
