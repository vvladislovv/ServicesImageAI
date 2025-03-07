from pydantic_settings import BaseSettings
from Messages.settingsmsg import new_message

# PayPass
class PayPassConfig:
    BASE_PRICE: int = 590
    PRO_PRICE: int = 990

class PayPass(BaseSettings):
    o3_mini: int
    gpt_4o_mini: int
    gemini_1_5_flash: int
    o1_mini: int
    o1: int
    claude_3_5_sonnet: int
    image_recognition: bool
    speech_to_text: bool
    claude_3_haiku: int
    gpt_4o: int
    tts: int
    tts_hd: int
    deepseek_v3: int
    deepseek_r1: int


def get_paypass(type_pass: str):
    """
    Возвращает настройки лимитов в зависимости от типа подписки

    type_pass: str
    Base - Базовая подписка - 590
    Pro - Профессиональная подписка - 990
     """
    if type_pass == "Base":
        return PayPass(
            o3_mini=30,
            gpt_4o_mini=30,
            gemini_1_5_flash=5,
            o1_mini=10,
            o1=3,
            claude_3_5_sonnet=15,
            claude_3_haiku=15,
            gpt_4o=15,
            tts=10,
            tts_hd=10,
            deepseek_v3=50,
            deepseek_r1=50,
            image_recognition=True,
            speech_to_text=True
        )
    elif type_pass == "Pro":
        return PayPass(
            o3_mini=60,
            gpt_4o_mini=60,
            gemini_1_5_flash=10,
            o1_mini=20,
            o1=6,
            claude_3_5_sonnet=30,
            claude_3_haiku=30,
            gpt_4o=30,
            deepseek_v3=60,
            deepseek_r1=60,
            tts=10,
            tts_hd=10,
            image_recognition=True,
            speech_to_text=True
        )
    elif type_pass == "NoBase":
        return PayPass(
            o3_mini=15,
            gpt_4o_mini=15,
            gemini_1_5_flash=15,
            o1_mini=0,
            o1=0,
            gpt_4o=0,
            claude_3_5_sonnet=0,
            claude_3_haiku=0,
            deepseek_v3=15,
            deepseek_r1=15,
            tts=0,
            tts_hd=0,
            image_recognition=False,
            speech_to_text=False
        )

async def send_paypass_info(user_id: int, paypass_data: dict):
    try:
        text = f"Информация о подписке: {paypass_data}"
        await new_message(user_id, text)
    except Exception as e:
        await new_message(user_id, f"Ошибка при отправке информации о подписке: {str(e)}")

def get_default_limits():
    """
    Возвращает словарь с лимитами по умолчанию (NoBase)
    
    Returns:
        dict: Словарь с API-именами моделей и их лимитами
    """
    paypass = get_paypass("NoBase")
    
    # Получаем все атрибуты PayPass
    paypass_dict = paypass.dict()
    
    # Преобразуем имена моделей из PayPass в API-имена
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
        if model_name in paypass_dict:
            limits[api_name] = paypass_dict[model_name]
    
    return limits




