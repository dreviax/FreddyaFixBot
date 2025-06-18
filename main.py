import logging
import asyncio

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ParseMode, ContentType
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove, LabeledPrice, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram import F

from handlers.prog_fullbody2 import register_fullbody2_handlers, muscle_sequence as fullbody_sequence
from handlers.prog_fullbody3 import register_fullbody3_handlers
from handlers.prog_hybrid3 import register_hybrid3_handlers, muscle_sequence_day1, muscle_sequence_day2, muscle_sequence_day3
from handlers.prog_upperlower2 import register_upperlower2_handlers, muscle_sequence_day1 as ul_day1, muscle_sequence_day2 as ul_day2
from handlers.prog_ap2 import register_pushpull2_handlers, muscle_sequence_day1 as ap_day1, muscle_sequence_day2 as ap_day2
import settings.markups as nav
import settings.config as cfg
from utils import check_sub, are_markups_equal
from storage import user_program, save_user_program, count_programs

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

bot = Bot(
    token=cfg.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

async def send_split_message(bot, chat_id: int, text: str, reply_markup=None):
    MAX_MESSAGE_LENGTH = 4000
    logger.debug(f"Sending message to chat {chat_id}, length: {len(text)}")
    if len(text) <= MAX_MESSAGE_LENGTH:
        await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
        return
    lines = text.split("\n")
    current_chunk = ""
    for line in lines:
        if len(current_chunk) + len(line) + 1 > MAX_MESSAGE_LENGTH:
            logger.debug(f"Sending chunk of length {len(current_chunk.strip())} for chat {chat_id}")
            await bot.send_message(chat_id=chat_id, text=current_chunk.strip())
            current_chunk = ""
        current_chunk += line + "\n"
    if current_chunk.strip():
        logger.debug(f"Sending final chunk of length {len(current_chunk.strip())} for chat {chat_id}")
        await bot.send_message(chat_id=chat_id, text=current_chunk.strip(), reply_markup=reply_markup)

async def format_day(day_num: int, day_name: str, exercises: list, muscle_seq: list, sets_reps: str, is_multi_day: bool = True):
    prefix = f"{day_num}️⃣ <b>День {day_num} ({day_name})</b>\n" if is_multi_day else ""
    day_text = prefix
    muscle_groups = {}
    subgroup_to_group = {}
    nested_subgroups = {"Квадрицепсы": [], "Бицепс бедра": []}

    for group, subgroup, count in muscle_seq:
        if isinstance(count, list):
            for sub_subgroup, _ in count:
                subgroup_to_group[sub_subgroup] = group
                nested_subgroups[subgroup].append(sub_subgroup)
        else:
            subgroup_to_group[subgroup] = group

    logger.debug(f"Exercises to format: {exercises}")

    for exercise in exercises:
        try:
            subgroup, exercise_name = exercise.split(": ", 1)
            muscle_group = subgroup_to_group.get(subgroup, "Прочее")
            if muscle_group not in muscle_groups:
                muscle_groups[muscle_group] = {}
            if subgroup not in muscle_groups[muscle_group]:
                muscle_groups[muscle_group][subgroup] = []
            muscle_groups[muscle_group][subgroup].append(exercise_name)
        except ValueError:
            logger.warning(f"Invalid exercise format: {exercise}")
            muscle_group = "Прочее"
            if muscle_group not in muscle_groups:
                muscle_groups[muscle_group] = {}
            if "Неизвестная группа" not in muscle_groups[muscle_group]:
                muscle_groups[muscle_group]["Неизвестная группа"] = []
            muscle_groups[muscle_group]["Неизвестная группа"].append(exercise)

    for muscle_group in sorted(muscle_groups.keys()):
        day_text += f"\n💪 <b>{muscle_group}</b>\n"
        if muscle_group == "Ноги" and is_multi_day:
            for parent_subgroup in ["Квадрицепсы", "Бицепс бедра"]:
                if any(sub in muscle_groups[muscle_group] for sub in nested_subgroups[parent_subgroup]):
                    day_text += f"  ➡️ <b><i>{parent_subgroup}</i></b>\n"
                    for subgroup in sorted(nested_subgroups[parent_subgroup]):
                        if subgroup in muscle_groups[muscle_group]:
                            day_text += f"    ➡️ <b><i>{subgroup}</i></b>\n"
                            for exercise in muscle_groups[muscle_group][subgroup]:
                                day_text += f"      • {exercise} ({sets_reps})\n"
            other_subgroups = [sub for sub in muscle_groups[muscle_group] if sub not in sum(nested_subgroups.values(), [])]
            for subgroup in sorted(other_subgroups):
                day_text += f"  ➡️ <b><i>{subgroup}</i></b>\n"
                for exercise in muscle_groups[muscle_group][subgroup]:
                    day_text += f"    • {exercise} ({sets_reps})\n"
        else:
            for subgroup in sorted(muscle_groups[muscle_group].keys()):
                day_text += f"  ➡️ <b><i>{subgroup}</i></b>\n"
                for exercise in muscle_groups[muscle_group][subgroup]:
                    day_text += f"    • {exercise} ({sets_reps})\n"

    logger.debug(f"Formatted day {day_num} ({day_name}) for user: {day_text}")
    return day_text

async def display_program(message: types.Message, user_id: str, first_name: str) -> bool:
    logger.debug(f"Checking user_program for user {user_id}: {user_program.get(user_id)}")
    if user_id not in user_program or not user_program[user_id].get("program"):
        logger.info(f"No program found for user {user_id}")
        return False

    program = user_program[user_id]
    days = program.get('days', 2)
    sets_reps = program.get('sets_reps', '3 подхода, 3-8 повторений')
    program_type = program.get('type', 'Unknown')
    logger.info(f"Displaying program for user {user_id}: type={program_type}, days={days}, program={program['program']}")

    intro_text = (
        "😲 Отличный выбор упражнений, спортсмен, очень оптимальный выбор!\n\n"
        "📝 <i>Упражнения не написаны по исполнительному порядку, начинай тренировку с мышцы, "
        "которую ты хочешь акцентировать сегодня, и после переходи на следующие упражнения по своему выбору.</i>\n"
        "💡 <i>Если ты хочешь постепенно добавлять объем, добавляй! Но только если твое тело это позволяет, не нагружай себя просто так.</i>\n\n"
    )
    if program_type == "4 день верх/низ":
        intro_text += "ℹ️ <i>Программа на 4 дня состоит из двух чередующихся дней (верх/низ), которые нужно повторять.</i>\n\n"
    elif program_type == "4 day перед/зад":
        intro_text += "ℹ️ <i>Программа на 4 дня состоит из двух чередующихся дней (перед/зад), которые нужно повторять.</i>\n\n"
    intro_text += (
        f"🏋️ <b>Ваша программа тренировок</b>\n"
        f"📅 Тип: {program_type}\n"
        f"🗓 Дней: {days}\n"
    )
    footer_text = (
        "\n💡 Техника: <a href='https://t.me/+IkIXHNQL3vgyYzQ8'>ТуторыЗамены</a>\n"
        "📋 Просмотр: /programma\n"
        "🔥 Удачи!"
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Пересоставить", callback_data="clear_program")]
    ])

    if isinstance(program["program"], list) and program_type in ["FullBody 2.0", "FullBody 3.0"]:
        response = intro_text + f"ℹ️ <i>Программа одинакова для всех дней тренировок.</i>\n\n<b>Упражнения:</b>\n"
        day_text = await format_day(1, "", program["program"], fullbody_sequence, sets_reps, is_multi_day=False)
        response += day_text
        await send_split_message(bot, message.chat.id, response + footer_text, reply_markup=markup)
        logger.info(f"Displayed {program_type} program for user {user_id}")
        return True

    if isinstance(program["program"], dict):
        if program_type == "3 day гибрид верх/низа и фулбади":
            days_config = [
                (1, "Фулбади", program["program"]["day1"], muscle_sequence_day1),
                (2, "Верх", program["program"]["day2"], muscle_sequence_day2),
                (3, "Низ", program["program"]["day3"], muscle_sequence_day3)
            ]
        elif program_type == "4 день верх/низ":
            days_config = [
                (1, "Верх", program["program"]["day1"], ul_day1),
                (2, "Низ", program["program"]["day2"], ul_day2)
            ]
        elif program_type == "4 day перед/зад":
            days_config = [
                (1, "Перед", program["program"]["day1"], ap_day1),
                (2, "Зад", program["program"]["day2"], ap_day2)
            ]
        else:
            logger.warning(f"Unknown dict-based program type: {program_type} for user {user_id}")
            return False

        if program_type in ["4 день верх/низ", "4 day перед/зад"]:
            full_text = intro_text + "\n"
            for day_num, day_name, exercises, muscle_seq in days_config:
                day_text = await format_day(day_num, day_name, exercises, muscle_seq, sets_reps)
                full_text += day_text + "\n"
            full_text += footer_text
            logger.debug(f"Full text length for user {user_id} ({program_type}): {len(full_text)}")
            if len(full_text) <= 4000:
                await bot.send_message(message.chat.id, full_text, reply_markup=markup)
                logger.info(f"Displayed {program_type} program for user {user_id} in single message")
            else:
                await send_split_message(bot, message.chat.id, full_text, reply_markup=markup)
                logger.info(f"Displayed {program_type} program for user {user_id} in split messages")
            return True

        for idx, (day_num, day_name, exercises, muscle_seq) in enumerate(days_config):
            day_text = await format_day(day_num, day_name, exercises, muscle_seq, sets_reps)
            text = (intro_text + "\n" + day_text) if idx == 0 else day_text
            reply_markup = markup if idx == len(days_config) - 1 else None
            footer = footer_text if idx == len(days_config) - 1 else ""
            await send_split_message(bot, message.chat.id, text + footer, reply_markup=reply_markup)
        logger.info(f"Displayed {program_type} program for user {user_id}")
        return True

    logger.warning(f"Invalid program structure for user {user_id}: {program}")
    return False

@dp.message(Command("tutorials"))
async def tutorials_cmd(message: types.Message):
    await message.answer_photo(
        photo=FSInputFile(cfg.tutorials_image),
        caption=(
            "🎥 <b>Туторы и замены упражнений</b>\n"
            "Ознакомьтесь с техникой на нашем канале:\n"
            "<a href='https://t.me/+IkIXHNQL3vgyYzQ8'>ТуторыЗамены</a>"
        ),
        reply_markup=nav.get_tutorials_btn()
    )

class DonateStates(StatesGroup):
    waiting_for_amount = State()

@dp.message(Command("donate"))
async def donate_cmd(message: types.Message, state: FSMContext):
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_donate")]
    ])
    await message.answer_photo(
        photo=FSInputFile(cfg.donate_image),
        caption=(
            "💸 <b>Поддержите проект!</b>\n"
            "Введите количество ⭐️ для пожертвования (целое число):"
        ),
        reply_markup=markup
    )
    await state.set_state(DonateStates.waiting_for_amount)

@dp.message(DonateStates.waiting_for_amount, F.text.regexp(r"^\d+$"))
async def process_amount(message: types.Message, state: FSMContext):
    amount = int(message.text)
    if amount < 1:
        await message.answer("❗ Минимум 1 звезда. Попробуйте снова.")
        return

    price = [LabeledPrice(label=f"Пожертвование {amount} ⭐️", amount=amount)]
    try:
        await bot.send_invoice(
            chat_id=message.chat.id,
            title=f"Пожертвование {amount} ⭐️",
            description="Спасибо за поддержку нашего проекта!",
            payload=f"donate_{amount}_stars",
            provider_token="",  # Update with your provider token
            currency="XTR",
            prices=price,
            start_parameter="donate_stars"
        )
        await state.clear()
    except TelegramBadRequest as e:
        logger.error(f"Error sending invoice: {e}")
        await message.answer("❌ Ошибка при создании платежа. Попробуйте позже.")

@dp.callback_query(F.data == "cancel_donate")
async def cancel_donate_callback(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.delete()
    except TelegramBadRequest as e:
        logger.warning(f"Failed to delete message: {e}")

    await callback.message.answer("❌ Пожертвование отменено.\n💪 Что дальше? /programma")
    await state.clear()
    await callback.answer()

@dp.pre_checkout_query()
async def checkout(pre_q: types.PreCheckoutQuery):
    try:
        await bot.answer_pre_checkout_query(pre_q.id, ok=True)
    except Exception as e:
        logger.error(f"Error in pre-checkout: {e}")
        await bot.answer_pre_checkout_query(pre_q.id, ok=False, error_message="Payment error")

@dp.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def payment_done(message: types.Message):
    amount = message.successful_payment.total_amount
    await message.answer(
        f"✅ <b>Спасибо за пожертвование {amount} ⭐️!</b>\n"
        "Ваш вклад помогает нам развиваться! 💪",
        reply_markup=ReplyKeyboardRemove()
    )

@dp.callback_query(F.data == "check_subscription")
async def check_subscription_handler(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    first_name = callback.from_user.first_name or "User"

    is_subscribed = await check_sub(cfg.CHANNEL, user_id)
    logger.info(f"User {user_id} subscription check result: {is_subscribed}")

    if is_subscribed:
        text = (
            f"👋 <b>Привет, {first_name}!</b>\n"
            f"{cfg.START_MESS_SUB}\n"
            f"📊 Количество составленных тренировок сейчас: {count_programs()}\n"
            "🔥 Готов составить или посмотреть программу?"
        )
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏋️ Составить/Посмотреть", callback_data="start_programma")]
        ])
    else:
        text = (
            f"❗ <b>{first_name}, подпишись на каналы!</b>\n"
            f"{cfg.NOT_SUB_MESS}\n"
            "После подписки нажми 'Проверить подписку'."
        )
        markup = nav.get_channel_btn()

    current_text = callback.message.text or ""
    current_markup = callback.message.reply_markup

    markup_equal = are_markups_equal(markup, current_markup)
    logger.debug(f"Text changed: {text != current_text}, Markup equal: {markup_equal}")

    if text != current_text or not markup_equal:
        try:
            if callback.message.text:
                await callback.message.edit_text(text, reply_markup=markup)
            elif callback.message.caption:
                await callback.message.edit_caption(caption=text, reply_markup=markup)
            else:
                await callback.message.answer(text, reply_markup=markup)
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                logger.debug(f"Skipped edit for user {user_id}: message not modified")
            else:
                logger.warning(f"Error editing message for user {user_id}: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error editing message for user {user_id}: {e}")
    await callback.answer()

@dp.callback_query(F.data == "start_programma")
async def start_programma_callback(callback: types.CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)
    first_name = callback.from_user.first_name or "User"

    logger.info(f"Start programma callback for user {user_id}")

    if not await check_sub(cfg.CHANNEL, user_id):
        await callback.message.edit_caption(
            caption=(
                f"❗ <b>{first_name}, подпишись на каналы!</b>\n"
                f"{cfg.NOT_SUB_MESS}"
            ),
            reply_markup=nav.get_channel_btn()
        )
        await callback.answer()
        return

    if await display_program(callback.message, user_id, first_name):
        await callback.answer()
        return

    await callback.message.answer(
        "🏋️ <b>Создаем программу!</b>\n"
        "Сколько дней в неделю ты готов тренироваться?",
        reply_markup=nav.get_days_keyboard()
    )
    await state.set_state(TrainingProgramStates.choosing_days)
    await callback.answer()

@dp.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    first_name = message.from_user.first_name or "User"
    logger.info(f"Start command received for user {user_id}")

    if message.chat.type == "private":
        if await check_sub(cfg.CHANNEL, user_id):
            await message.answer_photo(
                photo=FSInputFile(cfg.start_image),
                caption=(
                    f"👋 <b>Привет, {first_name}!</b>\n"
                    f"{cfg.START_MESS_SUB}\n"
                    f"📊 Количество составленных тренировок сейчас: {count_programs()}\n"
                    "🔥 Готов составить или посмотреть программу?"
                ),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🏋️ Составить/Посмотреть", callback_data="start_programma")]
                ])
            )
        else:
            await message.answer_photo(
                photo=FSInputFile(cfg.start_image),
                caption=(
                    f"❗ <b>Привет, {first_name}!</b>\n"
                    f"{cfg.NOT_SUB_MESS}"
                ),
                reply_markup=nav.get_channel_btn()
            )

class TrainingProgramStates(StatesGroup):
    choosing_days = State()
    choosing_program = State()

@dp.message(Command("programma"))
async def programma_cmd(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    first_name = message.from_user.first_name or "User"

    logger.info(f"Programma command for user {user_id}: {user_program.get(user_id)}")

    if not await check_sub(cfg.CHANNEL, user_id):
        await message.answer_photo(
            photo=FSInputFile(cfg.start_image),
            caption=(
                f"❗ <b>{first_name}, подпишись на каналы!</b>\n"
                f"{cfg.NOT_SUB_MESS}"
            ),
            reply_markup=nav.get_channel_btn()
        )
        return

    if await display_program(message, user_id, first_name):
        return

    logger.info(f"No valid program found for user {user_id}, proceeding to day selection")
    await message.answer(
        "🏋️ <b>Создаем программу!</b>\n"
        "Сколько дней в неделю ты готов тренироваться?",
        reply_markup=nav.get_days_keyboard()
    )
    await state.set_state(TrainingProgramStates.choosing_days)

@dp.callback_query(TrainingProgramStates.choosing_days, F.data.startswith("days_"))
async def handle_days_selection(callback: types.CallbackQuery, state: FSMContext):
    days = int(callback.data.split("_")[1])
    await state.update_data(days=days)

    await callback.message.edit_text(
        f"✅ <b>Вы выбрали {days} дня(дней)</b>\n"
        "Теперь выберите тип программы:",
        reply_markup=nav.get_program_keyboard(days)
    )
    await state.set_state(TrainingProgramStates.choosing_program)
    await callback.answer()

@dp.callback_query(TrainingProgramStates.choosing_program, F.data == "back_to_days")
async def handle_back_to_days(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(TrainingProgramStates.choosing_days)
    await callback.message.edit_text(
        "🏋️ <b>Сколько дней в неделю?</b>",
        reply_markup=nav.get_days_keyboard()
    )
    await callback.answer()

async def main():
    register_fullbody2_handlers(dp)
    register_fullbody3_handlers(dp)
    register_hybrid3_handlers(dp)
    register_upperlower2_handlers(dp)
    register_pushpull2_handlers(dp)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())