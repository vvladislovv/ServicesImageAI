from typing import Optional, List, Dict
from pydantic import BaseModel

# Модели для управления ботом
class ModelUpdate(BaseModel):
    model_name: str
    available_requests: int

class BroadcastMessage(BaseModel):
    message_text: str
    target_users: Optional[List[int]] = None  # Если None, то всем пользователям

# Модели для аналитики
class TimeRange(BaseModel):
    start_date: str  # формат YYYY-MM-DD
    end_date: str    # формат YYYY-MM-DD

class UsageStats(BaseModel):
    total_requests: int
    requests_by_model: Dict[str, int]
    requests_by_day: Dict[str, int]
    average_response_time: float


class UserDetail(BaseModel):
    user_id: int
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    requests_count: int
    favorite_model: str
    remaining_requests: dict

# Модели для управления подписками
class SubscriptionUpdate(BaseModel):
    user_id: int
    tariff: str
    expiry_date: Optional[str] = None  # формат YYYY-MM-DD

# Модель для истории чата
class ChatHistory(BaseModel):
    user_id: int
    messages: List[dict]
    total_messages: int 