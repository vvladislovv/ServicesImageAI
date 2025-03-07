from dataclasses import dataclass
from environs import Env
from typing import Optional


@dataclass
class DatabaseConfig:
    """Конфигурация базы данных."""
    uri: str
    name: str
    
@dataclass
class OpenAIConfig:
    """Конфигурация OpenAI."""
    api_key: str
    base_url: str = "https://api.proxyapi.ru/openai/v1"

@dataclass
class TelegramConfig:
    """Конфигурация Telegram бота."""
    token: str
    api_key: str
    webhook_url: Optional[str] = None
    
@dataclass
class Config:
    """Основная конфигурация приложения."""
    db: DatabaseConfig
    openai: OpenAIConfig
    telegram: TelegramConfig
    debug: bool = False


@dataclass
class TTSConfig:
    available_voices = {
        "alloy": "Нейтральный голос",
        "echo": "Глубокий мужской голос",
        "fable": "Выразительный голос",
        "onyx": "Серьезный мужской голос",
        "nova": "Женский голос",
        "shimmer": "Мягкий женский голос"
    }
    default_voice = "alloy"
    preview_text = "Привет! Это пример моего голоса."

def load_config(path: str = None) -> Config:
    """
    Загрузка конфигурации из переменных окружения.
    
    Args:
        path: Путь к файлу с переменными окружения
    Returns:
        Config: Объект конфигурации
    """
    env = Env()
    env.read_env(path)

    return Config(
        db=DatabaseConfig(
            uri=env.str("MONGO_URI", "mongodb://localhost:27017"),
            name=env.str("MONGO_DB_NAME", "my_database")
        ),
        openai=OpenAIConfig(
            api_key=env.str("PROXY_API_KEY"),
            base_url="https://api.proxyapi.ru/openai/v1",
        ),
        telegram=TelegramConfig(
            token=env.str("BOT_TOKEN"),
            api_key=env.str("API_KEY"),
            webhook_url=env.str("WEBHOOK_URL", None)
        ),
        debug=env.bool("DEBUG", False)
    )

# Создаем единственный экземпляр конфигурации
config = load_config()

def get_config() -> Config:
    """
    Получение конфигурации приложения.
    
    Returns:
        Config: Объект конфигурации
    """
    return config 

