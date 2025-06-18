import logging
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest
import settings.config as cfg

bot = Bot(token=cfg.BOT_TOKEN)

async def check_sub(channels: list[str], user_id: int) -> bool:
    for channel in channels:
        try:
            chat_member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            logging.info(f"User {user_id} status in channel {channel}: {chat_member.status}")
            if chat_member.status in ["left", "kicked", "restricted"]:
                return False
        except TelegramBadRequest as e:
            logging.error(f"Telegram API error checking subscription for user {user_id} in channel {channel}: {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error checking subscription for user {user_id} in channel {channel}: {e}")
            return False
    return True

def are_markups_equal(markup1: InlineKeyboardMarkup | None, markup2: InlineKeyboardMarkup | None) -> bool:
    """Сравнивает две InlineKeyboardMarkup на равенство."""
    if markup1 is None and markup2 is None:
        return True
    if markup1 is None or markup2 is None:
        return False
    if not isinstance(markup1, InlineKeyboardMarkup) or not isinstance(markup2, InlineKeyboardMarkup):
        return False
    if len(markup1.inline_keyboard) != len(markup2.inline_keyboard):
        return False
    for row1, row2 in zip(markup1.inline_keyboard, markup2.inline_keyboard):
        if len(row1) != len(row2):
            return False
        for btn1, btn2 in zip(row1, row2):
            if btn1.text != btn2.text or btn1.url != btn2.url or btn1.callback_data != btn2.callback_data:
                return False
    return True