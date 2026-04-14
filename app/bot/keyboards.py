"""
Reusable inline keyboard factories for the bot.
"""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def confirm_transaction_kb() -> InlineKeyboardMarkup:
    """Confirm / Cancel buttons shown before saving a transaction."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Saqlash", callback_data="tx:confirm"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="tx:cancel"),
        ]
    ])


def edit_field_kb() -> InlineKeyboardMarkup:
    """Field selector shown when editing the last transaction."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💰 Summa", callback_data="edit:amount"),
            InlineKeyboardButton(text="📂 Toifa", callback_data="edit:category"),
        ],
        [
            InlineKeyboardButton(text="📝 Izoh", callback_data="edit:description"),
            InlineKeyboardButton(text="❌ Bekor", callback_data="edit:cancel"),
        ],
    ])


def category_kb(categories: list[str]) -> InlineKeyboardMarkup:
    """Dynamic category picker — 2 buttons per row."""
    rows = []
    for i in range(0, len(categories), 2):
        row = [InlineKeyboardButton(text=cat, callback_data=f"cat:{cat}") for cat in categories[i:i+2]]
        rows.append(row)
    rows.append([InlineKeyboardButton(text="❌ Bekor", callback_data="cat:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


DEFAULT_CATEGORIES = [
    "Savdo", "Logistika", "Ijara", "Maosh",
    "Kommunal", "Marketing", "Soliq", "Boshqa",
]
