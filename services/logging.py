from pydantic import BaseModel
from typing import Any, Dict
from datetime import datetime
from config.config import get_config
from pymongo import MongoClient

config = get_config()

client = MongoClient(config.db.uri)
db = client[config.db.name]

class LogsJson(BaseModel):
    data: Dict[str, str]
    created_at: str = datetime.now().strftime("%H:%M %d-%m-%Y")

async def logs_bot(TypeLog: str, Text: str) -> None:
    """Логирование событий."""
    try:
        valid_log_types = ["error", "warning", "info", "debug"]
        if TypeLog.lower() not in valid_log_types:
            TypeLog = "warning"  

        # Создаем запись лога
        log_data = {"level": TypeLog, "message": Text}
        log_entry = LogsJson(data=log_data)
        
        # Сохраняем в базу данных
        await add_logs_data("logs_json", log_entry.model_dump())
    except Exception as e:
        print(f"Logging error: {str(e)}")

async def add_logs_data(collection_name: str, data: dict) -> Any:
    """
    Общая функция для добавления данных в коллекцию MongoDB.
    
    Аргументы:
        collection_name: str - Название коллекции
        data: dict - Данные для вставки
        
    Возвращает:
        Созданную запись или False, если не удалось вставить данные
    """
    try:
        collection = db[collection_name]
        # Для остальных коллекций - обычная вставка
        result = collection.insert_one(data)
        return result.inserted_id
    except Exception as e:
        error_msg = f"Database insertion error in {collection_name}: {str(e)}"
        await logs_bot("error", error_msg)
        return False