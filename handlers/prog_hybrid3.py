from aiogram import Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from settings.config import full_body_program
from storage import user_program, save_user_program
import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SETS_REPS = "3 подхода по 3-6 повторений (Выполнять в 0-2 повторений в запасе)"

class HybridStates(StatesGroup):
    choosing_muscle_group = State()
    choosing_exercise = State()
    entering_custom_exercise = State()

muscle_sequence_day1 = [
    ("Спина", "Верх спины", 1),
    ("Спина", "Широчайшие", 1),
    ("Дельты", "Передняя дельта", 1),
    ("Дельты", "Средняя дельта", 1),
    ("Дельты", "Задняя дельта", 1),
    ("Грудь", "Верх груди", 1),
    ("Грудь", "Низ груди", 1),
    ("Руки", "Бицепс", 1),
    ("Руки", "Трицепс", 1),
    ("Ноги", "Ягодицы", 1),
    ("Ноги", "Квадрицепсы", [
        ("Квадрицепсы (приседания)", 1),
        ("Квадрицепсы (разгибания)", 1)
    ]),
    ("Ноги", "Бицепс бедра", [
        ("Бицепс бедра", 1),
        ("Hinge", 1)
    ]),
    ("Ноги", "Приводящие", 1),
    ("Ноги", "Икры", 1),
]

muscle_sequence_day2 = [
    ("Спина", "Верх спины", 1),
    ("Спина", "Широчайшие", 1),
    ("Дельты", "Передняя дельта", 1),
    ("Дельты", "Средняя дельта", 1),
    ("Дельты", "Задняя дельта", 1),
    ("Грудь", "Верх груди", 1),
    ("Грудь", "Низ груди", 1),
    ("Руки", "Бицепс", 1),
    ("Руки", "Трицепс", 1),
]

muscle_sequence_day3 = [
    ("Ноги", "Ягодицы", 1),
    ("Ноги", "Квадрицепсы", [
        ("Квадрицепсы (приседания)", 1),
        ("Квадрицепсы (разгибания)", 1)
    ]),
    ("Ноги", "Бицепс бедра", [
        ("Бицепс бедра", 1),
        ("Hinge", 1)
    ]),
    ("Ноги", "Приводящие", 1),
    ("Ноги", "Икры", 1),
]

# Транслитерация для callback_data
TRANSLIT_MAP = {
    'Спина': 'Spina', 'Широчайшие': 'Shirochayshie', 'Верх спины': 'Verh_spiny',
    'Дельты': 'Delty', 'Передняя дельта': 'Perednyaya_delta', 'Средняя дельта': 'Srednyaya_delta',
    'Задняя дельта': 'Zadnyaya_delta', 'Грудь': 'Grud', 'Верх груди': 'Verh_grudi',
    'Низ груди': 'Niz_grudi', 'Руки': 'Ruki', 'Бицепс': 'Bitseps', 'Трицепс': 'Tritseps',
    'Ноги': 'Nogi', 'Ягодицы': 'Yagoditsy', 'Квадрицепсы': 'Kvadricep', 'Квадрицепсы (приседания)': 'Kvadricep_prised',
    'Квадрицепсы (разгибания)': 'Kvadricep_razgib', 'Бицепс бедра': 'Bitseps_bedra', 'Hinge': 'Hinge',
    'Приводящие': 'Privodyashchie', 'Икры': 'Ikry'
}

def translit(text: str) -> str:
    return TRANSLIT_MAP.get(text, re.sub(r'[^\w]', '_', text))

def get_exercise_keyboard(muscle_group: str, subgroup: str, selected_exercises: list, day: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    exercises = full_body_program.get(muscle_group, {}).get(subgroup, [])
    logger.debug(f"Exercises for {muscle_group}/{subgroup} (Day {day}): {exercises}")
    
    muscle_group_translit = translit(muscle_group)
    subgroup_translit = translit(subgroup)
    
    for idx, exercise in enumerate(exercises):
        if exercise not in selected_exercises:
            callback_data = f"ex_{muscle_group_translit}_{subgroup_translit}_{idx}_{day}"
            if len(callback_data.encode('utf-8')) > 64:
                logger.error(f"Callback data too long: {callback_data}")
                raise ValueError("Callback data exceeds Telegram limit")
            logger.debug(f"Adding button with callback_data: {callback_data} for exercise: {exercise}")
            builder.add(InlineKeyboardButton(
                text=exercise,
                callback_data=callback_data
            ))
    
    callback_data_custom = f"custom_ex_{muscle_group_translit}_{subgroup_translit}_{day}"
    if len(callback_data_custom.encode('utf-8')) > 64:
        logger.error(f"Custom callback data too long: {callback_data_custom}")
        raise ValueError("Custom callback data exceeds Telegram limit")
    builder.add(InlineKeyboardButton(
        text="✍️ Вписать свое упражнение",
        callback_data=callback_data_custom
    ))
    
    builder.adjust(1)
    return builder.as_markup()

async def start_hybrid3(callback: types.CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)
    data = await state.get_data()
    days = data.get("days", 3)
    
    await state.clear()  # Очистка FSM перед началом
    await state.set_state(HybridStates.choosing_muscle_group)
    await state.update_data({
        "current_step": 0,
        "selected": {"day1": [], "day2": [], "day3": []},
        "exercise_mapping": {},
        "selected_exercises": [],
        "days_per_week": days,
        "user_id": user_id,
        "current_day": 1
    })
    logger.info(f"Started hybrid3 for user {user_id} with {days} days")
    await send_next_muscle(callback, state)
    await callback.answer()

async def send_next_muscle(message: types.CallbackQuery | types.Message, state: FSMContext):
    data = await state.get_data()
    step = data.get("current_step", 0)
    user_id = str(message.from_user.id if isinstance(message, types.Message) else message.from_user.id)
    current_day = data.get("current_day", 1)

    muscle_seq = (
        muscle_sequence_day1 if current_day == 1 else
        muscle_sequence_day2 if current_day == 2 else
        muscle_sequence_day3
    )

    flat_sequence = []
    for group, subgroup, count in muscle_seq:
        if isinstance(count, list):
            for sub_subgroup, sub_count in count:
                flat_sequence.append((group, sub_subgroup, sub_count))
        else:
            flat_sequence.append((group, subgroup, count))

    if step >= len(flat_sequence):
        if current_day < 3:
            await state.update_data({
                "current_step": 0,
                "current_day": current_day + 1,
                "selected_exercises": []
            })
            logger.info(f"Moving to Day {current_day + 1} for user {user_id}")
            await send_next_muscle(message, state)
            return
        else:
            selected = data.get("selected", {"day1": [], "day2": [], "day3": []})
            days = data.get("days_per_week", 3)

            expected_counts = {
                "day1": sum(1 if isinstance(count, int) else len(count) for _, _, count in muscle_sequence_day1),
                "day2": sum(1 if isinstance(count, int) else len(count) for _, _, count in muscle_sequence_day2),
                "day3": sum(1 if isinstance(count, int) else len(count) for _, _, count in muscle_sequence_day3)
            }
            for day in ["day1", "day2", "day3"]:
                if len(selected[day]) != expected_counts[day]:
                    logger.error(f"Incomplete program for user {user_id} on {day}: expected {expected_counts[day]}, got {len(selected[day])} exercises: {selected[day]}")
                    await message.answer("❗ Ошибка: не все упражнения выбраны. Начните заново с /programma")
                    await state.clear()
                    return

            user_program[user_id] = {
                "days": days,
                "program": {
                    "day1": selected["day1"],
                    "day2": selected["day2"],
                    "day3": selected["day3"]
                },
                "type": "3 day гибрид верх/низа и фулбади",
                "sets_reps": SETS_REPS
            }
            save_user_program()

            logger.info(f"Saved program for user {user_id}: {user_program[user_id]}")

            if isinstance(message, types.CallbackQuery):
                await message.message.edit_text("/programma - просмотреть программу")
            else:
                await message.answer("/programma - просмотреть программу")
            await state.clear()
            logger.info(f"Program completed for user {user_id}")
            return

    muscle_group, subgroup, required_count = flat_sequence[step]
    exercises = full_body_program.get(muscle_group, {}).get(subgroup, [])

    if not exercises:
        logger.warning(f"No exercises found for {muscle_group}/{subgroup} in full_body_program")
        await state.update_data({"current_step": step + 1})
        await send_next_muscle(message, state)
        return

    muscle_group_translit = translit(muscle_group)
    subgroup_translit = translit(subgroup)

    exercise_mapping = {}
    for idx, exercise in enumerate(exercises):
        callback_data = f"ex_{muscle_group_translit}_{subgroup_translit}_{idx}_{current_day}"
        if len(callback_data.encode('utf-8')) > 64:
            logger.error(f"Callback data too long: {callback_data}")
            raise ValueError("Callback data exceeds Telegram limit")
        exercise_mapping[callback_data] = {
            "muscle_group": muscle_group,
            "subgroup": subgroup,
            "exercise": exercise,
            "day": current_day
        }

    logger.debug(f"Exercise mapping for user {user_id}, {muscle_group}/{subgroup} (Day {current_day}): {exercise_mapping}")

    await state.update_data({
        "current_muscle": muscle_group,
        "current_subgroup": subgroup,
        "required_count": required_count,
        "selected_for_muscle": [],
        "exercise_mapping": exercise_mapping,
        "selected_exercises": data.get("selected_exercises", [])
    })

    text = f"💪 <b>Выберите {required_count} упражнение для {subgroup} (День {current_day})</b>\n📋 Доступные варианты:"
    keyboard = get_exercise_keyboard(muscle_group, subgroup, data.get("selected_exercises", []), current_day)

    if isinstance(message, types.CallbackQuery):
        await message.message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)

    logger.info(f"Sent muscle group: {muscle_group}, subgroup: {subgroup}, step: {step}, user_id: {user_id}, day: {current_day}")

async def exercise_selected(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    required_count = data.get("required_count", 1)
    selected_for_muscle = data.get("selected_for_muscle", [])
    
    logger.debug(f"Received callback_data: {callback.data}, available mappings: {data.get('exercise_mapping', {}).keys()}")

    if len(selected_for_muscle) >= required_count:
        await callback.answer("❗ Вы уже выбрали максимум упражнений для этой группы!")
        return
    
    exercise_data = data.get("exercise_mapping", {}).get(callback.data)
    if not exercise_data:
        await callback.answer("❌ Упражнение не найдено!")
        logger.error(f"Exercise not found for callback_data: {callback.data}, user_id: {callback.from_user.id}, mapping: {data.get('exercise_mapping', {})}")
        return
    
    muscle_group = exercise_data["muscle_group"]
    subgroup = exercise_data["subgroup"]
    exercise = exercise_data["exercise"]
    day = exercise_data["day"]
    
    selected = data.get("selected", {"day1": [], "day2": [], "day3": []})
    selected_total = selected[f"day{day}"]
    selected_exercises = data.get("selected_exercises", [])
    
    logger.debug(f"User {callback.from_user.id} selected exercise: {exercise} for {muscle_group}/{subgroup} (Day {day}), callback_data: {callback.data}")
    
    if exercise not in selected_for_muscle:
        selected_for_muscle.append(exercise)
        selected_total.append(f"{subgroup}: {exercise}")
        selected_exercises.append(exercise)
        
        await state.update_data({
            "selected_for_muscle": selected_for_muscle,
            "selected": {f"day{d}": selected[f"day{d}"] for d in range(1, 4)},
            "selected_exercises": selected_exercises
        })
    
    logger.info(f"Updated selected exercises for user {callback.from_user.id} (Day {day}): {selected_total}")

    if len(selected_for_muscle) >= required_count:
        logger.debug(f"Completed selection for {muscle_group}/{subgroup} (Day {day}): {selected_for_muscle}")
        await state.update_data({"current_step": data.get("current_step", 0) + 1})
        await send_next_muscle(callback, state)
    else:
        await callback.message.edit_text(
            f"✅ <b>Выбрано {len(selected_for_muscle)}/{required_count} для {subgroup} (День {day})</b>",
            reply_markup=get_exercise_keyboard(
                muscle_group, subgroup, selected_exercises, day
            )
        )
    
    await callback.answer()

async def custom_exercise_button_pressed(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    muscle_group = data.get("current_muscle")
    subgroup = data.get("current_subgroup")
    required_count = data.get("required_count", 1)
    selected_for_muscle = data.get("selected_for_muscle", [])
    day = data.get("current_day", 1)

    if len(selected_for_muscle) >= required_count:
        await callback.answer("❗ Вы уже выбрали максимум упражнений для этой группы!")
        return

    muscle_group_translit = translit(muscle_group)
    subgroup_translit = translit(subgroup)
    callback_data_custom = f"custom_ex_{muscle_group_translit}_{subgroup_translit}_{day}"
    if len(callback_data_custom.encode('utf-8')) > 64:
        logger.error(f"Custom callback data too long: {callback_data_custom}")
        raise ValueError("Custom callback data exceeds Telegram limit")

    message = await callback.message.edit_text(
        f"✍️ <b>Введите свое упражнение для {subgroup} (День {day})</b>\n"
        "Напишите название (например, 'Жим ногами в тренажере'):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_custom_exercise")]
        ])
    )

    await state.update_data({"request_message_id": message.message_id})
    await state.set_state(HybridStates.entering_custom_exercise)
    await callback.answer()

async def process_custom_exercise(message: types.Message, state: FSMContext):
    data = await state.get_data()
    custom_exercise = message.text.strip()
    day = data.get("current_day", 1)
    muscle_group = data.get("current_muscle")
    subgroup = data.get("current_subgroup")
    required_count = data.get("required_count", 1)

    if not custom_exercise or len(custom_exercise) > 100:
        await message.answer(
            "❗ Название упражнения не может быть пустым или длиннее 100 символов!\nПопробуйте снова:"
        )
        return

    selected_for_muscle = data.get("selected_for_muscle", [])
    selected = data.get("selected", {"day1": [], "day2": [], "day3": []})
    selected_total = selected[f"day{day}"]
    selected_exercises = data.get("selected_exercises", [])

    logger.debug(f"User {message.from_user.id} added custom exercise: {custom_exercise} for {muscle_group}/{subgroup} (Day {day})")

    if custom_exercise not in selected_for_muscle:
        selected_for_muscle.append(custom_exercise)
        selected_total.append(f"{subgroup}: {custom_exercise}")
        selected_exercises.append(custom_exercise)

        await state.update_data({
            "selected_for_muscle": selected_for_muscle,
            "selected": {f"day{d}": selected[f"day{d}"] for d in range(1, 4)},
            "selected_exercises": selected_exercises
        })

    logger.info(f"Updated selected exercises for user {message.from_user.id} (Day {day}): {selected_total}")

    request_message_id = data.get("request_message_id")
    if request_message_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=request_message_id)
        except Exception as e:
            logger.error(f"Failed to delete request message {request_message_id}: {e}")

    await message.delete()

    if len(selected_for_muscle) >= required_count:
        logger.debug(f"Completed custom selection for {muscle_group}/{subgroup} (Day {day}): {selected_for_muscle}")
        await state.update_data({"current_step": data.get("current_step", 0) + 1})
        await state.set_state(HybridStates.choosing_muscle_group)
        await send_next_muscle(message, state)
    else:
        await state.set_state(HybridStates.choosing_muscle_group)
        await message.answer(
            f"✅ <b>Выбрано {len(selected_for_muscle)}/{required_count} для {subgroup} (День {day})</b>",
            reply_markup=get_exercise_keyboard(
                muscle_group, subgroup, selected_exercises, day
            )
        )

async def cancel_custom_exercise(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    muscle_group = data.get("current_muscle")
    subgroup = data.get("current_subgroup")
    selected_exercises = data.get("selected_exercises", [])
    day = data.get("current_day", 1)

    await state.set_state(HybridStates.choosing_muscle_group)
    await callback.message.edit_text(
        f"💪 <b>Выберите {data.get('required_count')} упражнение для {subgroup} (День {day})</b>",
        reply_markup=get_exercise_keyboard(
            muscle_group, subgroup, selected_exercises, day
        )
    )
    await callback.answer()

async def clear_program(callback: types.CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)
    if user_id in user_program:
        del user_program[user_id]
        save_user_program()
        logger.info(f"Program removed for user {user_id}")
    await state.clear()
    await callback.message.edit_text(
        "🗑 <b>Программа удалена!</b>\nСоздайте новую с помощью /programma или /start",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏋️ Новая программа", callback_data="start_programma")]
        ])
    )
    await callback.answer()

def register_hybrid3_handlers(dp: Dispatcher):
    dp.callback_query.register(start_hybrid3, F.data == "prog_hybrid3")
    dp.callback_query.register(
        exercise_selected, 
        HybridStates.choosing_muscle_group,
        F.data.startswith("ex_")
    )
    dp.callback_query.register(
        custom_exercise_button_pressed,
        HybridStates.choosing_muscle_group,
        F.data.startswith("custom_ex_")
    )
    dp.message.register(
        process_custom_exercise,
        HybridStates.entering_custom_exercise
    )
    dp.callback_query.register(
        cancel_custom_exercise,
        HybridStates.entering_custom_exercise,
        F.data == "cancel_custom_exercise"
    )
    dp.callback_query.register(
        clear_program,
        F.data == "clear_program"
    )