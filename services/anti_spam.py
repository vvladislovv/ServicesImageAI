from collections import defaultdict
from datetime import datetime
from typing import Dict, Tuple

class AntiSpam:
    def __init__(self):
        # Словарь для хранения количества сообщений и времени последнего сообщения
        self.user_messages: Dict[int, Tuple[int, datetime]] = defaultdict(lambda: (0, datetime.min))
        self.MESSAGE_LIMIT = 3  # Максимальное количество сообщений
        self.COOLDOWN_SECONDS = 3  # Время ожидания в секундах

    async def check_spam(self, user_id: int) -> Tuple[bool, float]:
        """
        Проверяет, не является ли сообщение спамом
        
        Returns:
            Tuple[bool, float]: (можно_ли_отправить_сообщение, время_ожидания_в_секундах)
        """
        current_time = datetime.now()
        message_count, last_time = self.user_messages[user_id]
        
        # Сброс счетчика, если прошло больше COOLDOWN_SECONDS
        if (current_time - last_time).total_seconds() >= self.COOLDOWN_SECONDS:
            message_count = 0
        
        # Увеличиваем счетчик
        message_count += 1
        
        # Обновляем данные пользователя
        self.user_messages[user_id] = (message_count, current_time)
        
        # Если превышен лимит сообщений
        if message_count > self.MESSAGE_LIMIT:
            time_passed = (current_time - last_time).total_seconds()
            time_remaining = max(0, self.COOLDOWN_SECONDS - time_passed)
            return False, time_remaining
            
        return True, 0

    async def reset_user(self, user_id: int):
        """Сбрасывает счетчик сообщений для пользователя"""
        self.user_messages[user_id] = (0, datetime.min)

# Создаем глобальный экземпляр
spam_controller = AntiSpam() 