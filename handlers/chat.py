import asyncio
from aiogram import Router, types, F
from aiogram.filters import CommandStart
from Messages.localization import MESSAGES
from Messages.utils import create_user_data
from Messages.settingsmsg import new_message, update_message, send_typing_action
from services.logging import logs_bot
from handlers.voice_chat import tts_process_text
from aiogram.fsm.context import FSMContext
from database.settingsdata import get_state_ai, get_table_data, add_to_table
from services.openai_services import AI_choice
from services.anti_spam import spam_controller
from Messages.inlinebutton import get_general_menu, ai_menu_back

router = Router(name=__name__)


@router.message(CommandStart())
async def command_start(message: types.Message):
    """Обработчик команды /start."""
    try:
        # Отправляем приветственное сообщение
        await send_typing_action(message, "typing")
        await new_message(message, MESSAGES["ru"]["start"], await get_general_menu())

        # Сохраняем информацию о пользователе
        await create_user_data(message)

    except Exception as e:
        await logs_bot("error", f"Error in start command: {e}")


@router.message(F.text | F.voice | F.audio | F.photo)
async def handle_message(message: types.Message, state: FSMContext):
    try:
        # Проверяем, находится ли пользователь в состоянии ожидания ввода текста для TTS
        current_state = await state.get_state()
        if current_state == "TTSStates:waiting_for_text":
            await tts_process_text(message, state)
            return

        # Проверка на спам
        can_send, wait_time = await spam_controller.check_spam(message.from_user.id)
        if not can_send:
            await new_message(
                message,
                f"Пожалуйста, подождите {wait_time:.1f} секунд перед отправкой следующего сообщения",
                None,
            )
            return

        chat_id = message.from_user.id
        await create_user_data(message)
        data_gpt = await get_state_ai(chat_id)

        # Получаем данные конкретного пользователя по chat_id
        user_ai_list = await get_table_data("UsersAI")
        user_ai = next((u for u in user_ai_list if u.get("chatId") == chat_id), {})

        type_gpt = user_ai.get("typeGpt", "gpt-4o-mini")
        remaining_requests = data_gpt.get(type_gpt, 0)

        if remaining_requests <= 0:
            await new_message(
                message,
                "⚠️ У вас закончились доступные запросы для этого типа AI. "
                "Пожалуйста, обновите подписку.",
            )
            return

        # Устанавливаем in_progress в True перед обработкой для конкретного пользователя
        await add_to_table("UsersAI", {"chatId": chat_id, "in_progress": True})

        try:
            # Запускаем статус "печатает"

            await send_typing_action(message, "typing")
            # Запускаем запрос к OpenAI
            response, msg_old = await AI_choice(message, type_gpt)
            # stop_typing = await maintain_typing_status(message)

            # Останавливаем статус "печатает" после получения ответа

            if response is not None and msg_old is not None:
                # Получаем текущие данные пользователя
                user_data = await get_state_ai(message.from_user.id)

                # Уменьшаем количество доступных запросов только для указанной модели
                if type_gpt in user_data:
                    user_data[type_gpt] -= 1

                # Обновляем статистику в StaticAIUsers
                await add_to_table(
                    "StaticAIUsers",
                    {"chatId": message.from_user.id, "dataGpt": user_data},
                )

                await asyncio.sleep(0.10)
                # Обновляем сообщение с клавиатурой для последнего сообщения
                keyboard = await ai_menu_back()

                await update_message(msg_old, str(response), keyboard)
            else:
                error_msg = "Не удалось обработать ваш запрос. Попробуйте позже."
                await new_message(message, error_msg, None)

        finally:
            # Устанавливаем in_progress в False после обработки
            await add_to_table("UsersAI", {"chatId": chat_id, "in_progress": False})

    except Exception as e:
        await logs_bot("error", f"Error in handle_message: {str(e)}")

        # Добавляем информацию о модели в сообщение об ошибке
        error_msg = "⚠️ Произошла ошибка при обработке запроса.\n_Пожалуйста, попробуйте позже или выберите другую модель_."

        await new_message(message, error_msg, None)
