from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_channel_btn() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="📢 FreddyaKach", url="https://t.me/FreddyaKach")
    )
    keyboard.row(
        InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_subscription")
    )
    return keyboard.as_markup()

def get_tutorials_btn() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="🎥 ТуторыЗамены", url="https://t.me/+IkIXHNQL3vgyYzQ8")
    )
    return keyboard.as_markup()

def get_days_keyboard():
    buttons = [
        [InlineKeyboardButton(text="📅 2 дня", callback_data="days_2")],
        [InlineKeyboardButton(text="📅 3 дня", callback_data="days_3")],
        [InlineKeyboardButton(text="📅 4 дня", callback_data="days_4")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_program_keyboard(days: int) -> InlineKeyboardMarkup:
    if days == 2:
        buttons = [
            InlineKeyboardButton(text="💪 Фуллбоди x2", callback_data="prog_fullbody2")
        ]
    elif days == 3:
        buttons = [
            InlineKeyboardButton(text="💪 Фуллбоди x3", callback_data="prog_fullbody3"),
            InlineKeyboardButton(text="🔄 Гибрид верх-низ + фулбади", callback_data="prog_hybrid3")
        ]
    elif days == 4:
        buttons = [
            InlineKeyboardButton(text="🔀 Верх-низ x2", callback_data="prog_upperlower2"),
            InlineKeyboardButton(text="🔄 Гибрид Фуллбоди + Верх-низ (разработка)", callback_data="prog_ul1_fb2"),
            InlineKeyboardButton(text="⚖️ Перед-зад x2", callback_data="prog_ap2")
        ]
    else:
        buttons = []

    buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_days"))

    return InlineKeyboardMarkup(inline_keyboard=[[btn] for btn in buttons])