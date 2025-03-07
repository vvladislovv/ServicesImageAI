from aiogram import Router, types
from aiogram.filters import Command
from database.settingsdata import add_to_table, get_state_ai, get_table_data
from config.confpaypass import get_paypass
from services.logging import logs_bot
from services.openai_services import new_message
from datetime import datetime
from Messages.localization import MESSAGES
from config.confpaypass import get_default_limits
import os

router = Router(name=__name__)

# Получаем список администраторов из .env
ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором"""
    return user_id in ADMIN_IDS

async def check_admin_access(message: types.Message) -> bool:
    """Проверяет доступ и отправляет сообщение, если доступ запрещен"""
    if not is_admin(message.from_user.id):
        #await new_message(message, "⛔ У вас нет прав доступа к этой команде.", None)
        return False
    return True

# команды для админки (работают)

@router.message(Command("adminpanel"))
async def command_start(message: types.Message):
    """Доступные команды админки:
    /allid - Получить список всех ID пользователей
    /reset [user_id] - Сбросить статистику пользователя
    /state - Показать текущее состояние
    /allboost - Активировать все модели с +100 запросами"""
    if not await check_admin_access(message):
        return
    await new_message(message, MESSAGES['ru']['admin']['help_text'], None)  


@router.message(Command("allid"))
async def command_allid(message: types.Message):
    """Получить список всех ID пользователей
    Использование: /allid"""
    if not await check_admin_access(message):
        return
    try:
        # Получаем данные пользователей через get_table_data
        users = await get_table_data("Users")
        
        # Извлекаем chatId из данных
        user_ids = [str(user.get("chatId", "Unknown")) for user in users]
        
        # Формируем сообщение с перечислением всех ID
        if user_ids:
            message_text = "Все ID пользователей:\n" + "\n".join(user_ids)
        else:
            message_text = "В базе данных нет пользователей"
            
        await new_message(message, message_text, None)
        await logs_bot("info", f"Admin {message.from_user.id} requested all user IDs")
        
    except Exception as e:
        await logs_bot("error", f"Error in allid command: {str(e)}")
        await new_message(message, f"Произошла ошибка при получении ID пользователей: {str(e)}", None)


@router.message(Command("reset"))
async def command_reset(message: types.Message):
    if not await check_admin_access(message):
        return
    try:
        # Получаем текст сообщения и проверяем, есть ли ID пользователя
        command_parts = message.text.split()
        
        if len(command_parts) > 1:
            # Если указан ID пользователя
            user_id = command_parts[1]
            try:
                user_id = int(user_id)
                # Сбрасываем статистику для указанного пользователя
                reset_data = get_default_limits()  # Убрали await, так как это синхронная функция
                await add_to_table("StaticAIUsers", {"chatId": user_id, "dataGpt": reset_data})
                await new_message(message, f"Статистика для пользователя {user_id} сброшена до значений по умолчанию", None)
                await logs_bot("info", f"Admin {message.from_user.id} reset stats for user {user_id}")
            except ValueError:
                await new_message(message, "Ошибка: ID пользователя должен быть числом", None)
        else:
            # Если ID не указан, сбрасываем статистику для текущего пользователя
            user_id = message.from_user.id
            reset_data = get_default_limits()  # Убрали await, так как это синхронная функция
            await add_to_table("StaticAIUsers", {"chatId": user_id, "dataGpt": reset_data})
            await new_message(message, "Ваша статистика сброшена до значений по умолчанию", None)
            await logs_bot("info", f"User {user_id} reset their own stats")
    except Exception as e:
        await logs_bot("error", f"Error in reset command: {str(e)}")
        await new_message(message, f"Произошла ошибка при сбросе статистики: {str(e)}", None)

@router.message(Command("state"))
async def command_state(message: types.Message):
    if not await check_admin_access(message):
        return
    try:
        # Разбиваем команду на части
        command_parts = message.text.split()
        
        # Если указан ID пользователя
        if len(command_parts) > 1:
            try:
                chat_id = int(command_parts[1])  # Получаем ID из команды
                state_info = f"Состояние пользователя {chat_id}:\n\n"
            except ValueError:
                await new_message(message, "Ошибка: ID пользователя должен быть числом", None)
                return
        else:
            # Если ID не указан, берем текущего пользователя
            chat_id = message.from_user.id
            state_info = "Ваше текущее состояние:\n\n"
        
        # Получаем данные состояния
        data_gpt = await get_state_ai(chat_id)
        
        # Форматируем данные для вывода
        for model, count in data_gpt.items():
            state_info += f"{model}: {count}\n"
        
        await new_message(message, state_info, None)
    except Exception as e:
        await logs_bot("error", f"Error in state command: {e}")
        await new_message(message, f"Ошибка: {str(e)}", None)


@router.message(Command("allboost"))
async def command_allboost(message: types.Message):
    if not await check_admin_access(message):
        return
    try:
        # Разбиваем команду на части
        command_parts = message.text.split()
        
        # Если указан ID пользователя
        if len(command_parts) > 1:
            try:
                chat_id = int(command_parts[1])  # Получаем ID из команды
            except ValueError:
                await new_message(message, "Ошибка: ID пользователя должен быть числом", None)
                return
        else:
            # Если ID не указан, берем текущего пользователя
            chat_id = message.from_user.id
        
        # Получаем текущие данные пользователя
        existing_data = await get_state_ai(chat_id)
        
        # Получаем данные о всех моделях из Pro подписки
        paypass = get_paypass("Pro")
        paypass_dict = paypass.dict()
        
        # Создаем словарь с лимитами 100 для всех моделей
        limits = {}
        
        # Маппинг имен моделей из PayPass в API-имена
        model_mapping = {
            'gpt_4o_mini': 'gpt-4o-mini',
            'gpt_4o': 'gpt-4o',
            'claude_3_5_sonnet': 'claude-3-5-sonnet',
            'claude_3_haiku': 'claude-3-haiku',
            'gemini_1_5_flash': 'gemini-1.5-flash',
            'deepseek_v3': 'deepseek-v3',
            'deepseek_r1': 'deepseek-r1',
            'o1_mini': 'o1-mini',
            'o1': 'o1',
            'tts': 'tts',
            'tts_hd': 'tts-hd',
            'o3_mini': 'o3-mini'
        }
        
        # Заполняем словарь лимитов
        for model_name, api_name in model_mapping.items():
            if model_name in paypass_dict and model_name not in ["image_recognition", "speech_to_text"]:
                current_value = existing_data.get(api_name, 0)
                limits[api_name] = current_value + 100
        
        # Создаем или обновляем запись пользователя
        user_data = {
            "chatId": chat_id,
            "dataGpt": limits,
            "updated_at": datetime.utcnow()
        }
        
        # Сохраняем в базу данных
        await add_to_table("StaticAIUsers", user_data)
        
        await new_message(message, f"✅ Все модели AI активированы с лимитом +100 запросов для пользователя {chat_id}!", None) 
        await logs_bot("info", f"Admin {message.from_user.id} activated all models with +100 requests for user {chat_id}")
        
    except Exception as e:
        await new_message(message, f"⚠️ Произошла ошибка при активации моделей: {str(e)}", None)
        await logs_bot("error", f"Error in allboost command: {str(e)}")
