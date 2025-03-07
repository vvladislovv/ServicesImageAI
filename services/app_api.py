from fastapi import FastAPI, HTTPException, Depends, status, APIRouter
from fastapi.security import APIKeyHeader
import uvicorn
from config.config import get_config
from services.logging import logs_bot
from aiohttp import ClientSession
from contextlib import asynccontextmanager
import asyncio
from config.confpaypass import get_paypass
from datetime import datetime
from database.settingsdata import get_table_data, get_state_ai, add_to_table
from services.api_models import (
    ModelUpdate, BroadcastMessage, TimeRange, UsageStats,
    UserDetail, SubscriptionUpdate, ChatHistory
)
config = get_config()

# Настройка аутентификации
API_KEY = config.telegram.api_key
api_key_header = APIKeyHeader(name="X-API-Key")

# Создаем роутеры для группировки эндпоинтов
admin_router = APIRouter(prefix="/admin", tags=["admin"])
analytics_router = APIRouter(prefix="/analytics", tags=["analytics"])
users_router = APIRouter(prefix="/users", tags=["users"])

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом FastAPI.
    
    Компоненты:
    - ClientSession: Создает сессию для HTTP запросов
    - logs_bot: Логирует события запуска и остановки
    
    Вызов: Автоматически вызывается FastAPI при старте/остановке
    """
    global session
    session = ClientSession()
    await logs_bot("info", "FastAPI started")
    yield
    await session.close()
    await logs_bot("info", "FastAPI stopped")

app = FastAPI(
    title="AI Bot API",
    description="API для управления и мониторинга AI бота",
    version="1.0.0",
    lifespan=lifespan
)



async def run_fastapi():
    """
    Запускает FastAPI сервер асинхронно.
    
    Эта функция настраивает и запускает FastAPI сервер с указанными параметрами.
    """
    try:
        # Создаем сервер напрямую без использования строки импорта
        server = uvicorn.Server(
            uvicorn.Config(
                app=app,  # Используем объект app напрямую
                host="0.0.0.0",
                port=8000,
                reload=False,  # Отключаем автоперезагрузку в Docker
                log_level="info"
            )
        )
        await logs_bot("info", "FastAPI server starting")
        await server.serve()
    except Exception as e:
        await logs_bot("error", f"FastAPI server error: {e}")

def verify_api_key(api_key: str = Depends(api_key_header)):
    """Проверка API ключа.
    
    Компоненты:
    - api_key_header: Заголовок с API ключом
    - HTTPException: Возвращает ошибку при неверном ключе
    
    Вызов: 
    Автоматически вызывается через Depends() в защищенных эндпоинтах
    """
    if api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )
    return api_key

@app.get("/", tags=["general"])
async def read_root():
    """Корневой эндпоинт.
    
    Компоненты: Нет
    
    Пример вызова:
    GET /
    """
    return {"message": "AI Bot API", "version": "1.0.0"}

@app.get("/ping", tags=["general"])
async def ping(api_key: str = Depends(verify_api_key)):
    """Эндпоинт для проверки работоспособности API.
    
    Компоненты:
    - verify_api_key: Проверка авторизации
    - logs_bot: Логирование ошибок
    
    Пример вызова:
    GET /ping
    Заголовок: X-API-Key: ваш_api_ключ
    """
    try:
        return {"message": "PONG!", "status": "OK"}
    except Exception as e:
        await logs_bot("error", f"Ping endpoint error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Error"
        )

@admin_router.post("/update_model")
async def update_model(model_data: ModelUpdate, api_key: str = Depends(verify_api_key)):
    """Обновление доступных запросов для определенной модели.
    
    Компоненты:
    - get_table_data: Получение данных пользователей
    - get_state_ai: Получение текущего состояния AI
    - add_to_table: Обновление данных в таблице
    
    Пример вызова:
    POST /admin/update_model
    Заголовок: X-API-Key: ваш_api_ключ
    Тело запроса:
    {
        "model_name": "gpt-4",
        "available_requests": 50
    }
    """
    try:
        users = await get_table_data("Users")
        
        for user in users:
            user_id = user.get("chatId")
            if user_id:
                ai_state = await get_state_ai(user_id)
                ai_state[model_data.model_name] = model_data.available_requests
                await add_to_table("StaticAIUsers", {
                    "chatId": user_id,
                    "dataGpt": ai_state
                })
        
        return {"status": "success", "message": f"Updated {len(users)} users"}
    except Exception as e:
        await logs_bot("error", f"Update model endpoint error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating model: {str(e)}"
        )


@admin_router.post("/update_subscription")
async def update_subscription(
    sub_data: SubscriptionUpdate, 
    api_key: str = Depends(verify_api_key)
):
    """Обновление подписки пользователя.
    
    Компоненты:
    - get_table_data: Получение данных пользователя
    - get_state_ai: Получение состояния AI
    - add_to_table: Обновление данных в таблице
    
    Пример вызова:
    POST /admin/update_subscription
    Заголовок: X-API-Key: ваш_api_ключ
    Тело запроса:
    {
        "user_id": 123,
        "tariff": "Premium",
        "expiry_date": "2024-12-31"  // опционально
    }
    """
    try:
        users = await get_table_data("Users")
        users = [u for u in users if u.get("chatId") == sub_data.user_id]
        if not users:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {sub_data.user_id} not found"
            )
        
        update_data = {
            "chatId": sub_data.user_id,
            "tarif": sub_data.tariff
        }
        
        if sub_data.expiry_date:
            try:
                expiry_date = datetime.strptime(sub_data.expiry_date, "%Y-%m-%d")
                update_data["expiry_date"] = expiry_date
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid date format: {str(e)}. Use YYYY-MM-DD"
                )
        
        # Обновляем данные в базе
        await add_to_table("UsersPayPass", update_data)
        
        # Обновляем лимиты для Premium подписки
        if sub_data.tariff == "Premium":
            # Получаем текущие данные пользователя
            existing_data = await get_state_ai(sub_data.user_id)
            
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
                "chatId": sub_data.user_id,
                "dataGpt": limits,
                "updated_at": datetime.now().replace(second=0, microsecond=0)
            }
            
            # Сохраняем в базу данных
            await add_to_table("StaticAIUsers", user_data)
        
        return {
            "status": "success", 
            "message": f"Updated subscription for user {sub_data.user_id}",
            "new_tariff": sub_data.tariff
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await logs_bot("error", f"Update subscription endpoint error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating subscription: {str(e)}"
        )

# Эндпоинты для аналитики
@analytics_router.get("/usage", response_model=UsageStats)
async def get_usage_stats(
    time_range: TimeRange = Depends(),
    api_key: str = Depends(verify_api_key)
):
    """Получение статистики использования за указанный период."""
    try:
        # Преобразование строк в даты
        start_date = datetime.strptime(time_range.start_date, "%Y-%m-%d")
        end_date = datetime.strptime(time_range.end_date, "%Y-%m-%d")
        
        # Получаем историю чатов
        chat_history = await get_table_data("ChatHistory")
        
        # Фильтруем по дате
        filtered = []
        for h in chat_history:
            if not h.get("timestamp"):
                continue
            # Преобразуем строку в datetime, если необходимо
            if isinstance(h["timestamp"], str):
                h_date = datetime.fromisoformat(h["timestamp"])
            else:
                h_date = h["timestamp"]
                
            if start_date <= h_date <= end_date:
                filtered.append(h)
        
        # Считаем статистику
        total_requests = len(filtered)
        
        requests_by_model = {}
        for h in filtered:
            model = h.get("model", "unknown")
            requests_by_model[model] = requests_by_model.get(model, 0) + 1
        
        requests_by_day = {}
        for h in filtered:
            h_date = h["timestamp"] if isinstance(h["timestamp"], datetime) else datetime.fromisoformat(h["timestamp"])
            date_str = h_date.strftime("%Y-%m-%d")
            requests_by_day[date_str] = requests_by_day.get(date_str, 0) + 1
        
        response_times = [
            h.get("response_time", 0) 
            for h in filtered 
            if h.get("response_time")
        ]
        avg_response_time = sum(response_times)/len(response_times) if response_times else 0
        
        return UsageStats(
            total_requests=total_requests,
            requests_by_model=requests_by_model,
            requests_by_day=requests_by_day,
            average_response_time=avg_response_time
        )
        
    except Exception as e:
        await logs_bot("error", f"Usage stats error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing stats: {str(e)}"
        )

# Эндпоинты для работы с пользователями
@users_router.get("/{user_id}/chat_history", response_model=ChatHistory)
async def get_chat_history(user_id: int, limit: int = 10, api_key: str = Depends(verify_api_key)):
    """Получение истории чата пользователя."""
    try:
        users = await get_table_data("Users")
        users = [u for u in users if u.get("chatId") == user_id]
        if not users:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )
        
        history = await get_table_data("ChatHistory")
        history = [h for h in history if h.get("chatId") == user_id]
        
        history.sort(key=lambda x: x.get("timestamp", datetime.min), reverse=True)
        
        limited_history = history[:limit]
        
        messages = []
        for h in limited_history:
            messages.append({
                "user_message": h.get("message_text", ""),
                "bot_response": h.get("response_text", ""),
                "model": h.get("model", "unknown"),
                "timestamp": h.get("timestamp", "").isoformat() if h.get("timestamp") else None
            })
        
        return ChatHistory(
            user_id=user_id,
            messages=messages,
            total_messages=len(history)
        )
    except HTTPException:
        raise
    except Exception as e:
        await logs_bot("error", f"Chat history endpoint error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting chat history: {str(e)}"
        )

@users_router.get("/{user_id}", response_model=UserDetail)
async def get_user_detail(user_id: int, api_key: str = Depends(verify_api_key)):
    """Получение детальной информации о конкретном пользователе."""
    try:
        users = await get_table_data("Users")
        users = [u for u in users if u.get("chatId") == user_id]
        if not users:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )
        
        user = users[0]
        
        history = await get_table_data("ChatHistory")
        history = [h for h in history if h.get("chatId") == user_id]
        
        ai_state = await get_state_ai(user_id)
        
        model_counts = {}
        for h in history:
            model = h.get("model", "unknown")
            model_counts[model] = model_counts.get(model, 0) + 1
        
        favorite_model = max(model_counts.items(), key=lambda x: x[1])[0] if model_counts else "none"
        
        return UserDetail(
            user_id=user_id,
            username=user.get("username"),
            first_name=user.get("first_name"),
            last_name=user.get("last_name"),
            requests_count=len(history),
            favorite_model=favorite_model,
            remaining_requests=ai_state
        )
    except HTTPException:
        raise
    except Exception as e:
        await logs_bot("error", f"User detail endpoint error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting user details: {str(e)}"
        )

# Подключаем роутеры к приложению
app.include_router(admin_router)
app.include_router(analytics_router)
app.include_router(users_router)


