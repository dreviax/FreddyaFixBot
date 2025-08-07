from aiogram import Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from settings.config import full_body_program
from storage import user_program
from storage import save_user_program
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SETS_REPS = "2 подхода по 4-8 повторений (Выполнять в 0-2 повторений в запасе)"

class FullBody2States(StatesGroup):
    choosing_muscle_group = State()
    choosing_exercise = State()
    entering_custom_exercise = State()

muscle_sequence = [
    ("Спина", "Верх спины", 1),
    ("Спина", "Широчайшие", 1),
    ("Дельты", "Передняя дельта", 1),
    ("Дельты", "Средняя дельта", 1),
    ("Дельты", "Задняя дельта", 1),
    ("Грудь", "Верх груди", 1),
    ("Грудь", "Низ груди", 1),
    ("Руки", "Бицепс", 1),
    ("Руки", "Трицепс", 1),
    ("Ноги", "Квадрицепсы", 1),
    ("Ноги", "Бицепс бедра", [
        ("Бицепс бедра", 1),
        ("Hinge", 1)
    ]),
    ("Ноги", "Икры", 1),
    ("Ноги", "Приводящие", 1),
    ("Ноги", "Ягодицы", 1),
]

def get_exercise_keyboard(muscle_group: str, subgroup: str, selected_exercises: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    exercises = full_body_program.get(muscle_group, {}).get(subgroup, [])
    logger.debug(f"Exercises for {muscle_group}/{subgroup}: {exercises}")
    
    for idx, exercise in enumerate(exercises):
        if exercise not in selected_exercises:
            callback_data = f"ex_{muscle_group}_{subgroup}_{idx}"
            builder.add(InlineKeyboardButton(
                text=exercise,
                callback_data=callback_data
            ))
    
    builder.add(InlineKeyboardButton(
        text="✍️ Вписать свое упражнение",
        callback_data=f"custom_ex_{muscle_group}_{subgroup}"
    ))
    
    builder.adjust(1)
    return builder.as_markup()

async def start_fullbody2(callback: types.CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)

    data = await state.get_data()
    days = data.get("days", 2)

    await state.clear()  # Очистка FSM перед началом
    await state.set_state(FullBody2States.choosing_muscle_group)
    await state.update_data({
        "current_step": 0,
        "selected": [],
        "exercise_mapping": {},
        "selected_exercises": [],
        "days_per_week": days,
        "user_id": user_id
    })
    logger.info(f"Starting FullBody 2.0 for user {user_id} with {days} days")
    await send_next_muscle(callback, state)
    await callback.answer()

async def send_next_muscle(message: types.CallbackQuery | types.Message, state: FSMContext):
    data = await state.get_data()
    step = data.get("current_step", 0)
    user_id = str(message.from_user.id if isinstance(message, types.Message) else message.from_user.id)

    flat_sequence = []
    for group, subgroup, count in muscle_sequence:
        if isinstance(count, list):
            for sub_subgroup, sub_count in count:
                flat_sequence.append((group, sub_subgroup, sub_count))
        else:
            flat_sequence.append((group, subgroup, count))

    if step >= len(flat_sequence):
        selected = data.get("selected", [])
        days = data.get("days_per_week", 2)

        expected_count = sum(1 if isinstance(count, int) else sum(sub_count for _, sub_count in count) for _, _, count in muscle_sequence)
        if len(selected) != expected_count:
            logger.error(f"Incomplete program for user {user_id}: expected {expected_count}, got {len(selected)} exercises: {selected}")
            await message.answer("❗ Ошибка: не все упражнения выбраны. Начните заново с /programma")
            await state.clear()
            return

        user_program[user_id] = {
            "days": days,
            "program": selected,
            "type": "FullBody 2.0",
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

    exercise_mapping = {}
    for idx, exercise in enumerate(exercises):
        callback_data = f"ex_{muscle_group}_{subgroup}_{idx}"
        exercise_mapping[callback_data] = {
            "muscle_group": muscle_group,
            "subgroup": subgroup,
            "exercise": exercise
        }

    logger.debug(f"Exercise mapping for user {user_id}, {muscle_group}/{subgroup}: {exercise_mapping}")

    await state.update_data({
        "current_muscle": muscle_group,
        "current_subgroup": subgroup,
        "required_count": required_count,
        "selected_for_muscle": [],
        "exercise_mapping": exercise_mapping,
        "selected_exercises": data.get("selected_exercises", [])
    })

    text = (
        f"💪 <b>Выберите {required_count} упражнение для {subgroup}</b>\n"
        f"📋 Доступные варианты:"
    )
    keyboard = get_exercise_keyboard(muscle_group, subgroup, data.get("selected_exercises", []))

    if isinstance(message, types.CallbackQuery):
        await message.message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)

    logger.info(f"Sent muscle group: {muscle_group}, subgroup: {subgroup}, step: {step}, user_id: {user_id}")

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
    
    selected_total = data.get("selected", [])
    selected_exercises = data.get("selected_exercises", [])
    
    logger.debug(f"User {callback.from_user.id} selected exercise: {exercise} for {muscle_group}/{subgroup}, callback_data: {callback.data}")
    
    if exercise not in selected_for_muscle:
        selected_for_muscle.append(exercise)
        selected_total.append(f"{subgroup}: {exercise}")
        selected_exercises.append(exercise)
        
        await state.update_data({
            "selected_for_muscle": selected_for_muscle,
            "selected": selected_total,
            "selected_exercises": selected_exercises
        })
    
    logger.info(f"Updated selected exercises for user {callback.from_user.id}: {selected_total}")

    if len(selected_for_muscle) >= required_count:
        logger.debug(f"Completed selection for {muscle_group}/{subgroup}: {selected_for_muscle}")
        await state.update_data({"current_step": data.get("current_step", 0) + 1})
        await send_next_muscle(callback, state)
    else:
        await callback.message.edit_text(
            f"✅ <b>Выбрано {len(selected_for_muscle)}/{required_count} для {subgroup}</b>",
            reply_markup=get_exercise_keyboard(
                muscle_group, 
                subgroup, 
                selected_exercises
            )
        )
    
    await callback.answer()

async def custom_exercise_button_pressed(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    muscle_group = data.get("current_muscle")
    subgroup = data.get("current_subgroup")
    required_count = data.get("required_count", 1)
    selected_for_muscle = data.get("selected_for_muscle", [])

    if len(selected_for_muscle) >= required_count:
        await callback.answer("❗ Вы уже выбрали максимум упражнений для этой группы!")
        return

    message = await callback.message.edit_text(
        f"✍️ <b>Введите свое упражнение для {subgroup}</b>\n"
        "Напишите название (например, 'Жим ногами в тренажере'):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_custom_exercise")]
        ])
    )

    await state.update_data({"request_message_id": message.message_id})
    await state.set_state(FullBody2States.entering_custom_exercise)
    await callback.answer()

async def process_custom_exercise(message: types.Message, state: FSMContext):
    data = await state.get_data()
    muscle_group = data.get("current_muscle")
    subgroup = data.get("current_subgroup")
    required_count = data.get("required_count", 1)
    custom_exercise = message.text.strip()

    if not custom_exercise or len(custom_exercise) > 100:
        await message.answer(
            "❗ Название упражнения не может быть пустым или длиннее 100 символов!\n"
            "Попробуйте снова:"
        )
        return

    selected_for_muscle = data.get("selected_for_muscle", [])
    selected_total = data.get("selected", [])
    selected_exercises = data.get("selected_exercises", [])

    logger.debug(f"User {message.from_user.id} added custom exercise: {custom_exercise} for {muscle_group}/{subgroup}")

    if custom_exercise not in selected_for_muscle:
        selected_for_muscle.append(custom_exercise)
        selected_total.append(f"{subgroup}: {custom_exercise}")
        selected_exercises.append(custom_exercise)

        await state.update_data({
            "selected_for_muscle": selected_for_muscle,
            "selected": selected_total,
            "selected_exercises": selected_exercises
        })

    logger.info(f"Updated selected exercises for user {message.from_user.id}: {selected_total}")

    request_message_id = data.get("request_message_id")
    if request_message_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=request_message_id)
        except Exception as e:
            logger.error(f"Failed to delete request message {request_message_id}: {e}")

    await message.delete()

    if len(selected_for_muscle) >= required_count:
        logger.debug(f"Completed custom selection for {muscle_group}/{subgroup}: {selected_for_muscle}")
        await state.update_data({"current_step": data.get("current_step", 0) + 1})
        await state.set_state(FullBody2States.choosing_muscle_group)
        await send_next_muscle(message, state)
    else:
        await state.set_state(FullBody2States.choosing_muscle_group)
        await message.answer(
            f"✅ <b>Выбрано {len(selected_for_muscle)}/{required_count} для {subgroup}</b>",
            reply_markup=get_exercise_keyboard(
                muscle_group,
                subgroup,
                selected_exercises
            )
        )

async def cancel_custom_exercise(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    muscle_group = data.get("current_muscle")
    subgroup = data.get("current_subgroup")
    selected_exercises = data.get("selected_exercises", [])

    await state.set_state(FullBody2States.choosing_muscle_group)
    await callback.message.edit_text(
        f"💪 <b>Выберите {data.get('required_count')} упражнение для {subgroup}</b>",
        reply_markup=get_exercise_keyboard(
            muscle_group,
            subgroup,
            selected_exercises
        )
    )
    await callback.answer()

async def clear_program(callback: types.CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)

    if user_id in user_program:
        del user_program[user_id]
        save_user_program()
        logger.info(f"Program removed for user {user_id}")

    await callback.message.edit_text(
        "🗑 <b>Программа удалена!</b>\n"
        "Создайте новую с помощью /programma или /start",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏋️ Новая программа", callback_data="start_programma")]
        ])
    )
    await state.clear()
    await callback.answer()

def register_fullbody2_handlers(dp: Dispatcher):
    dp.callback_query.register(start_fullbody2, F.data == "prog_fullbody2")
    dp.callback_query.register(
        exercise_selected, 
        FullBody2States.choosing_muscle_group,
        F.data.startswith("ex_")
    )
    dp.callback_query.register(
        custom_exercise_button_pressed,
        FullBody2States.choosing_muscle_group,
        F.data.startswith("custom_ex_")
    )
    dp.message.register(
        process_custom_exercise,
        FullBody2States.entering_custom_exercise
    )
    dp.callback_query.register(
        cancel_custom_exercise,
        FullBody2States.entering_custom_exercise,
        F.data == "cancel_custom_exercise"
    )
    dp.callback_query.register(
        clear_program,
        F.data == "clear_program"
    )