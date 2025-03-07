from services.logging import logs_bot
from database.settingsdata import add_to_table, user_exists, save_voice_to_mongodb
from datetime import datetime, timedelta
import uuid


async def create_user_data(message) -> dict:
    from config.confpaypass import get_default_limits

    """
    Creates and stores initial user data across multiple database tables.
    Only creates data if it doesn't already exist.
    
    This function:
    1. Creates user profile data
    2. Initializes AI settings for the user
    3. Sets up payment/pass information
    4. Configures static AI data
    5. Starts chat history
    6. Logs the user's start
    7. Saves all data to respective database tables
    
    Args:
        message: Telegram message object containing user information
        
    Returns:
        dict: Dictionary containing all created user data
    """

    # Common user ID to be used across all tables
    chat_id = message.from_user.id
    created_at = datetime.now().strftime("%H:%M %d-%m-%Y")
    updated_pass_at = (datetime.now() + timedelta(days=7)).strftime("%H:%M %d-%m-%Y")

    user_data = {
        "chatId": int(chat_id),
        "username": message.from_user.username,
        "first_name": message.from_user.first_name,
        "last_name": message.from_user.last_name,
        "created_at": created_at,
    }

    user_ai = {
        "chatId": int(chat_id),
        "typeGpt": "gpt-4o-mini",
        "in_progress": False,
        "created_at": created_at,
    }

    user_pay_pass = {
        "chatId": int(chat_id),
        "id_pass": str(uuid.uuid4()),
        "tarif": "NoBase",
        "updated_pass": updated_pass_at,
        "expiration_date": updated_pass_at,  # Initial expiration date (7 days trial)
        "created_at": created_at,
    }

    static_ai_user = {"chatId": int(chat_id), "dataGpt": get_default_limits()}

    # Инициализируем историю чата только если она еще не существует
    chat_history = {
        "chatId": int(chat_id),
        "message_text": "",
        "response_text": "",
        "context": [
            "re",
            "Привет! Как я могу помочь?",
        ],  # Пустой контекст для новых пользователей
        "model": "gpt-4o-mini",
        "timestamp": created_at,
    }

    # Log user start
    await logs_bot("info", f"User {chat_id} started the bot")

    # Проверяем и сохраняем данные только если они не существуют
    tables_data = [
        ("Users", user_data),
        ("UsersAI", user_ai),
        ("UsersPayPass", user_pay_pass),
        ("StaticAIUsers", static_ai_user),
    ]

    for table_name, data in tables_data:
        # Проверяем, существует ли запись
        if not await user_exists(table_name, chat_id):
            await add_to_table(table_name, data)
            await logs_bot(
                "info", f"Created new record in {table_name} for user {chat_id}"
            )
        else:
            await logs_bot(
                "debug",
                f"User {chat_id} already exists in {table_name}, skipping creation",
            )

    # Возвращаем созданные данные
    return {
        "Users": user_data,
        "UsersAI": user_ai,
        "UsersPayPass": user_pay_pass,
        "StaticAIUsers": static_ai_user,
        "ChatHistory": chat_history,
    }


async def download_voice_user(message):
    """
    Скачивает голосовое сообщение пользователя и сохраняет в MongoDB

    Args:
        message: Объект сообщения с голосовым сообщением

    Returns:
        str: Виртуальный путь к файлу (для совместимости)
    """
    try:
        # Получаем информацию о голосовом файле
        voice_file_id = message.voice.file_id
        voice_file_info = await message.bot.get_file(voice_file_id)
        user_id = message.from_user.id

        # Скачиваем файл во временный буфер
        import io

        file_bytes = io.BytesIO()
        await message.bot.download_file(voice_file_info.file_path, file_bytes)

        # Получаем имя файла
        voice_name = voice_file_info.file_path.split("/")[-1]

        # Логируем для отладки
        await logs_bot(
            "debug",
            f"Downloaded voice file: {voice_name}, size: {len(file_bytes.getvalue())} bytes",
        )

        # Сохраняем в MongoDB
        virtual_path = await save_voice_to_mongodb(
            user_id, file_bytes.getvalue(), voice_name
        )

        await logs_bot(
            "info", f"Voice message saved to MongoDB with path: {virtual_path}"
        )
        return virtual_path

    except Exception as e:
        await logs_bot("error", f"Error in download_voice_user: {str(e)}")
        import traceback

        await logs_bot("error", traceback.format_exc())
        return None


def escape_markdown(text: str) -> str:
    """
    Экранирует специальные символы для Markdown V2

    Args:
        text: Исходный текст

    Returns:
        str: Экранированный текст
    """
    if not text:
        return ""

    # Список символов, которые нужно экранировать
    special_chars = [
        "_",
        "*",
        "[",
        "]",
        "(",
        ")",
        "~",
        "`",
        ">",
        "#",
        "+",
        "-",
        "=",
        "|",
        "{",
        "}",
        ".",
        "!",
        "/",
    ]

    # Экранируем каждый специальный символ
    for char in special_chars:
        text = text.replace(char, f"\\{char}")

    return text


async def format_expiry_date(timestamp: str) -> str:
    """Форматирует дата из MongoDB в русский формат"""
    if not timestamp:
        return "Не установлено"

    months = {
        "January": "Январь",
        "February": "Февраль",
        "March": "Март",
        "April": "Апрель",
        "May": "Май",
        "June": "Июнь",
        "July": "Июль",
        "August": "Август",
        "September": "Сентябрь",
        "October": "Октябрь",
        "November": "Ноябрь",
        "December": "Декабрь",
    }

    try:
        date_obj = datetime.strptime(timestamp, "%Y-%m-%d")
        return date_obj.strftime("%d %B %Y").replace(
            date_obj.strftime("%B"), months[date_obj.strftime("%B")]
        )
    except:
        return "Ошибка формата даты"
