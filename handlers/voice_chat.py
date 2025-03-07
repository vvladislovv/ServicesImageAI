from aiogram import Router, F, types
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from Messages.settingsmsg import new_message, update_message, send_typing_action
from services.logging import logs_bot
from services.openai_services import OpenAIService
from Messages.inlinebutton import (
    tts_quality_menu,
    ai_menu_back,
    create_tts_example_keyboard,
    get_general_menu,
)
from database.settingsdata import (
    get_state_ai,
    add_to_table,
    get_voice_from_mongodb,
    get_voice_example,
    save_voice_example,
)
import asyncio

router = Router(name=__name__)
openai_service = OpenAIService()


# Определение состояний для FSM
class TTSStates(StatesGroup):
    waiting_for_quality = State()  # Ожидание выбора качества (HD или обычное)
    waiting_for_voice = State()  # Ожидание выбора голоса
    waiting_for_text = State()  # Ожидание ввода текста для озвучивания


# Голоса для TTS
TTS_VOICES = {
    "alloy": "Alloy (нейтральный)",
    "echo": "Echo (мужской)",
    "fable": "Fable (британский)",
    "onyx": "Onyx (глубокий)",
    "nova": "Nova (женский)",
    "shimmer": "Shimmer (мелодичный)",
}


# Функция для генерации всех примеров голосов
async def generate_all_examples():
    """Генерирует примеры для всех голосов и качеств"""
    try:
        # Список голосов
        voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]

        # Список качеств
        qualities = ["tts", "tts-hd"]

        # Текст примера
        example_text = "Здравствуйте! Это тестовый текст для проверки голосового восприятия. Мы будем говорить о разных темах, чтобы протестировать звучание и четкость произнесения. Первое предложение: 'Солнце встает на востоке, а заходит на западе.'"

        await logs_bot("info", "Starting generation of all voice examples")

        for voice in voices:
            for quality in qualities:
                await logs_bot("info", f"Generating example for {voice} ({quality})...")

                # Проверяем, существует ли уже пример
                existing_path = await get_voice_example(voice, quality)
                if existing_path:
                    await logs_bot(
                        "info", f"Example for {voice} ({quality}) already exists"
                    )
                    continue

                # Генерируем голосовое сообщение
                virtual_path = await openai_service.text_to_speech(
                    example_text, voice, quality
                )

                if virtual_path:
                    # Сохраняем пример
                    await save_voice_example(voice, quality, virtual_path)
                    await logs_bot("info", f"Example saved for {voice} ({quality})")
                else:
                    await logs_bot(
                        "error", f"Failed to generate example for {voice} ({quality})"
                    )

                # Небольшая пауза между запросами
                await asyncio.sleep(1)

        await logs_bot("info", "All voice examples generated successfully")
        return True
    except Exception as e:
        await logs_bot("error", f"Error generating voice examples: {str(e)}")
        return False


# Обработчик кнопки "Генерация речи"
@router.callback_query(F.data == "TSSGenerat")
async def tts_start(call: CallbackQuery, state: FSMContext):
    """Начало процесса генерации речи"""
    try:
        # Проверяем наличие доступа к TTS
        chat_id = call.from_user.id
        data_gpt = await get_state_ai(chat_id)

        # Проверяем наличие tts и tts_hd в данных пользователя
        has_tts_access = data_gpt.get("tts", 0) > 0
        has_tts_hd_access = data_gpt.get("tts-hd", 0) > 0

        if not (has_tts_access or has_tts_hd_access):
            await call.answer(
                "У вас нет доступа к функции генерации речи", show_alert=True
            )
            return

        # Создаем клавиатуру для выбора качества и отправляем сообщение
        keyboard = await tts_quality_menu(has_tts_access, has_tts_hd_access)
        await update_message(
            call.message, "Выберите качество генерации речи:", keyboard
        )

        # Устанавливаем состояние ожидания выбора качества
        await state.set_state(TTSStates.waiting_for_quality)

    except Exception as e:
        await logs_bot("error", f"Error in tts_start: {str(e)}")
        await call.answer("Произошла ошибка при запуске генерации речи")


# Обработчик выбора качества
@router.callback_query(TTSStates.waiting_for_quality, F.data.startswith("tts_quality_"))
async def tts_select_quality(call: CallbackQuery, state: FSMContext):
    """Обработка выбора качества и предложение выбрать голос"""
    try:
        # Определяем выбранное качество
        quality = "tts-hd" if call.data == "tts_quality_hd" else "tts"

        # Проверяем наличие доступа к выбранному качеству
        chat_id = call.from_user.id
        data_gpt = await get_state_ai(chat_id)

        if data_gpt.get(quality, 0) <= 0:
            await call.answer(f"У вас нет доступа к {quality}", show_alert=True)
            return

        # Сохраняем выбранное качество в состоянии
        await state.update_data(quality=quality)

        # Создаем клавиатуру для выбора голоса
        keyboard = []
        row = []

        for voice_id, voice_name in TTS_VOICES.items():
            button = types.InlineKeyboardButton(
                text=voice_name, callback_data=f"tts_voice_{voice_id}"
            )

            row.append(button)
            if len(row) == 2:  # По две кнопки в ряду
                keyboard.append(row)
                row = []

        # Добавляем оставшиеся кнопки и кнопку возврата
        if row:
            keyboard.append(row)

        keyboard.append(
            [
                types.InlineKeyboardButton(
                    text="⬅️ Вернуться к выбору качества", callback_data="TSSGenerat"
                )
            ]
        )

        markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)

        # Отправляем сообщение с выбором голоса
        await update_message(
            call.message,
            f"Выбрано {'HD' if quality == 'tts-hd' else 'стандартное'} качество. Теперь выберите голос:",
            markup,
        )

        # Устанавливаем состояние ожидания выбора голоса
        await state.set_state(TTSStates.waiting_for_voice)

    except Exception as e:
        await logs_bot("error", f"Error in tts_select_quality: {str(e)}")
        await call.answer("Произошла ошибка при выборе качества")


# Обработчик выбора голоса
@router.callback_query(TTSStates.waiting_for_voice, F.data.startswith("tts_voice_"))
async def tts_select_voice(call: CallbackQuery, state: FSMContext):
    """Обработка выбора голоса и запрос текста для озвучивания"""
    try:
        # Логируем выбор голоса
        await logs_bot("info", f"Voice selected: {call.data}")

        # Извлекаем ID голоса из callback_data и сохраняем в состоянии
        voice_id = call.data.replace("tts_voice_", "")
        await state.update_data(voice=voice_id)

        # Получаем данные о выбранном качестве
        data = await state.get_data()
        await logs_bot("info", f"State data after voice selection: {data}")

        quality = data.get("quality", "tts")

        # Создаем клавиатуру с примером и возвратом
        markup = await create_tts_example_keyboard(quality)

        # Отправляем сообщение с инструкцией ввести текст
        voice_name = TTS_VOICES.get(voice_id, voice_id)
        await update_message(
            call.message,
            f"Выбран голос: *{voice_name}*.\n\n"
            f"Теперь введите текст, который хотите озвучить.\n"
            f"Максимальная длина текста: 1000 символов.\n\n"
            f"Вы также можете послушать пример этого голоса, нажав на кнопку ниже.",
            markup,
        )

        # Добавляем явное сообщение пользователю, что бот ожидает ввода текста
        await new_message(
            call.message, "✏️ Пожалуйста, введите текст для озвучивания:", None
        )

        # Устанавливаем состояние ожидания ввода текста
        await state.set_state(TTSStates.waiting_for_text)
        await logs_bot("info", f"State set to waiting_for_text")

    except Exception as e:
        await logs_bot("error", f"Error in tts_select_voice: {str(e)}")
        await call.answer("Произошла ошибка при выборе голоса")


# Обработчик примера
@router.callback_query(TTSStates.waiting_for_text, F.data == "tts_example")
async def tts_example(call: CallbackQuery, state: FSMContext):
    """Воспроизведение примера голосового сообщения"""
    try:
        # Получаем данные из состояния
        data = await state.get_data()
        quality = data.get("quality", "tts")
        voice = data.get("voice", "alloy")

        # Проверяем, есть ли уже сохраненный пример для этого голоса
        virtual_path = await get_voice_example(voice, quality)

        # Если пример не найден, генерируем новый
        if not virtual_path:
            await call.answer("Генерация примера...")

            # Проверяем наличие доступа к выбранному качеству
            chat_id = call.from_user.id
            data_gpt = await get_state_ai(chat_id)

            if data_gpt.get(quality, 0) <= 0:
                await call.answer(
                    f"У вас закончились доступные запросы для {quality}",
                    show_alert=True,
                )
                return

            # Генерируем голосовое сообщение
            virtual_path = await openai_service.text_to_speech(
                "Привет, мир!", voice, quality
            )

            if virtual_path:
                # Сохраняем пример для будущего использования
                await save_voice_example(voice, quality, virtual_path)

                # Уменьшаем счетчик только при первой генерации
                user_data = await get_state_ai(chat_id)
                if quality in user_data:
                    user_data[quality] -= 1
                    await logs_bot(
                        "info", f"Decreasing {quality} count to {user_data[quality]}"
                    )

                await add_to_table(
                    "StaticAIUsers", {"chatId": chat_id, "dataGpt": user_data}
                )
            else:
                await call.answer("Не удалось сгенерировать пример", show_alert=True)
                return
        else:
            # Если пример уже есть, просто сообщаем пользователю
            await call.answer("Воспроизведение примера...")

        # Получаем данные голосового сообщения из MongoDB
        voice_data = await get_voice_from_mongodb(virtual_path)

        if not voice_data:
            await logs_bot("error", f"Voice data not found for path: {virtual_path}")
            await call.answer(
                "Ошибка при получении голосового сообщения", show_alert=True
            )
            return

        # Отправляем голосовое сообщение
        try:
            # Создаем объект BufferedInputFile из бинарных данных
            from aiogram.types import BufferedInputFile

            voice_file = BufferedInputFile(voice_data, filename=f"voice_{voice}.mp3")

            # Получаем название голоса из словаря
            voice_name_raw = TTS_VOICES.get(voice, voice)

            # Создаем подпись без Markdown-форматирования
            caption = f"🔊 Пример голоса: {voice_name_raw}"

            # Отправляем голосовое сообщение
            await call.message.answer_voice(
                voice_file, caption=caption, parse_mode=None
            )

        except Exception as send_error:
            await logs_bot("error", f"Error sending voice message: {send_error}")
            await call.answer(
                "Ошибка при отправке голосового сообщения", show_alert=True
            )

    except Exception as e:
        await logs_bot("error", f"Error in tts_example: {str(e)}")
        await call.answer(
            "Произошла ошибка при воспроизведении примера", show_alert=True
        )


# Обработчик ввода текста
@router.message(TTSStates.waiting_for_text)
async def tts_process_text(message: Message, state: FSMContext):
    """Обработка введенного текста и генерация голосового сообщения"""
    try:
        # Логируем начало обработки
        await logs_bot("info", f"Processing text input: '{message.text[:30]}...'")

        # Получаем данные из состояния
        data = await state.get_data()
        await logs_bot("info", f"State data: {data}")

        quality = data.get("quality", "tts")
        voice = data.get("voice", "alloy")

        # Проверяем наличие доступа к выбранному качеству
        chat_id = message.from_user.id
        data_gpt = await get_state_ai(chat_id)

        if data_gpt.get(quality, 0) <= 0:
            await new_message(
                message, f"У вас закончились доступные запросы для {quality}."
            )
            await state.clear()
            return

        # Проверяем текст
        if not message.text or len(message.text.strip()) == 0:
            await new_message(message, "Пожалуйста, введите текст для озвучивания.")
            return

        if len(message.text) > 1000:
            await new_message(
                message, "Текст слишком длинный. Максимальная длина: 1000 символов."
            )
            return

        # Запускаем индикатор "запись голосового сообщения"
        stop_typing = await send_typing_action(message, "typing")

        try:
            # Генерируем голосовое сообщение
            await logs_bot(
                "info",
                f"Generating voice message with text: '{message.text[:30]}...', voice: {voice}, quality: {quality}",
            )
            success = await generate_voice_message(
                message, message.text, voice, quality
            )
            await logs_bot("info", f"Voice generation result: {success}")

            # Если генерация успешна, уменьшаем счетчик
            if success:
                user_data = await get_state_ai(chat_id)
                if quality in user_data:
                    user_data[quality] -= 1
                    await logs_bot(
                        "info", f"Decreasing {quality} count to {user_data[quality]}"
                    )

                await add_to_table(
                    "StaticAIUsers", {"chatId": chat_id, "dataGpt": user_data}
                )
                # Очищаем состояние ТОЛЬКО если генерация успешна
                await logs_bot("info", "Clearing state after successful generation")
                await state.clear()
            else:
                # Если генерация не удалась, НЕ очищаем состояние, чтобы пользователь мог попробовать снова
                await logs_bot("warning", "Voice generation failed, keeping state")
                await new_message(
                    message,
                    "Не удалось сгенерировать голосовое сообщение. Попробуйте еще раз.",
                )
        finally:
            # Останавливаем индикатор
            await stop_typing()

    except Exception as e:
        await logs_bot("error", f"Error in tts_process_text: {str(e)}")
        await new_message(
            message, "Произошла ошибка при генерации голосового сообщения."
        )
        # Очищаем состояние при критической ошибке
        await state.clear()


async def generate_voice_message(
    message: Message, text: str, voice: str, model: str = "tts"
):
    """
    Генерирует голосовое сообщение с использованием OpenAI API

    Args:
        message: Объект сообщения для ответа
        text: Текст для озвучивания
        voice: Идентификатор голоса
        model: Модель TTS (tts или tts-hd)

    Returns:
        bool: True если генерация успешна, False в противном случае
    """
    try:
        # Отправляем индикатор "запись голосового сообщения"
        await message.bot.send_chat_action(
            chat_id=message.chat.id, action="record_voice"
        )

        # Добавляем логирование перед вызовом API
        await logs_bot(
            "info",
            f"Calling TTS API with text: '{text[:30]}...', voice: {voice}, model: {model}",
        )

        # Генерируем голосовое сообщение и получаем виртуальный путь
        virtual_path = await openai_service.text_to_speech(text, voice, model)

        # Добавляем логирование результата
        await logs_bot("info", f"TTS API returned virtual path: {virtual_path}")

        if not virtual_path:
            await logs_bot("error", "Failed to generate voice message")
            await new_message(
                message,
                "Не удалось сгенерировать голосовое сообщение. Попробуйте позже.",
            )
            return False

        # Получаем данные голосового сообщения из MongoDB
        voice_data = await get_voice_from_mongodb(virtual_path)

        if not voice_data:
            await logs_bot("error", f"Voice data not found for path: {virtual_path}")
            await new_message(message, "Ошибка при получении голосового сообщения.")
            return False

        # Отправляем голосовое сообщение
        try:
            # Создаем объект BufferedInputFile из бинарных данных
            from aiogram.types import BufferedInputFile

            voice_file = BufferedInputFile(voice_data, filename=f"voice_{voice}.mp3")

            # Получаем название голоса из словаря
            voice_name_raw = TTS_VOICES.get(voice, voice)

            # Создаем подпись без Markdown-форматирования
            caption = f"🔊 Голос: {voice_name_raw}"

            # Создаем клавиатуру с кнопкой "Вернуться в меню"
            keyboard = await ai_menu_back()

            # Отправляем голосовое сообщение с клавиатурой
            await message.answer_voice(voice_file, caption=caption, parse_mode=None)
            await new_message(message, "Готово! Выберите следующее действие:", keyboard)

            return True  # Генерация успешна

        except Exception as send_error:
            await logs_bot("error", f"Error sending voice message: {send_error}")
            await new_message(message, "Ошибка при отправке голосового сообщения.")
            return False

    except Exception as e:
        await logs_bot("error", f"Error in generate_voice_message: {str(e)}")
        await new_message(
            message, "Произошла ошибка при генерации голосового сообщения."
        )
        return False


# Обработчик кнопки "Вернуться к выбору голоса"
@router.callback_query(TTSStates.waiting_for_text, F.data == "back_to_voice_selection")
async def back_to_voice_selection(call: CallbackQuery, state: FSMContext):
    """Возвращает пользователя к выбору голоса без сброса состояния"""
    try:
        # Получаем данные из состояния
        data = await state.get_data()
        quality = data.get("quality", "tts")

        # Создаем клавиатуру для выбора голоса
        keyboard = []
        row = []

        for voice_id, voice_name in TTS_VOICES.items():
            button = types.InlineKeyboardButton(
                text=voice_name, callback_data=f"tts_voice_{voice_id}"
            )

            row.append(button)
            if len(row) == 2:  # По две кнопки в ряду
                keyboard.append(row)
                row = []

        # Добавляем оставшиеся кнопки и кнопку возврата
        if row:
            keyboard.append(row)

        keyboard.append(
            [
                types.InlineKeyboardButton(
                    text="⬅️ Вернуться к выбору качества", callback_data="TSSGenerat"
                )
            ]
        )

        markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)

        # Отправляем сообщение с выбором голоса
        await update_message(
            call.message,
            f"Выбрано {'HD' if quality == 'tts-hd' else 'стандартное'} качество. Теперь выберите голос:",
            markup,
        )

        # Устанавливаем состояние ожидания выбора голоса
        await state.set_state(TTSStates.waiting_for_voice)

    except Exception as e:
        await logs_bot("error", f"Error in back_to_voice_selection: {str(e)}")
        await call.answer("Произошла ошибка при возврате к выбору голоса")


# Обработчик кнопки "Вернуться в главное меню"
@router.callback_query(F.data == "back_to_menu")
async def back_to_main_menu(call: CallbackQuery, state: FSMContext):
    """Возвращает пользователя в главное меню и сбрасывает состояние"""
    try:
        # Получаем текущее состояние
        current_state = await state.get_state()

        # Если пользователь находится в процессе TTS, сбрасываем состояние
        if current_state and current_state.startswith("TTSStates:"):
            await state.clear()

        # Отправляем сообщение с главным меню
        keyboard = await get_general_menu()
        await update_message(call.message, "Выберите действие:", keyboard)

    except Exception as e:
        await logs_bot("error", f"Error in back_to_main_menu: {str(e)}")
        await call.answer("Произошла ошибка при возврате в главное меню")
