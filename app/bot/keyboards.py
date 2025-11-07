# app/bot/keyboards.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def grid_keyboard(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    """rows: [[(label, callback_data), ...], ...]"""
    kb = [[InlineKeyboardButton(text=txt, callback_data=data) for (txt, data) in row] for row in rows]
    return InlineKeyboardMarkup(kb)

def chunk(items, n):
    for i in range(0, len(items), n):
        yield items[i:i+n]
