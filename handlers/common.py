from aiogram import Router, F
from aiogram.types import CallbackQuery
from Messages.inlinebutton import get_main_keyboard_mode, backstep_menu_message, get_general_menu, get_profile_keyboard, get_pay_keyboard, backstep_menu_message_pass
from Messages.localization import MESSAGES
from database.settingsdata import get_table_data, add_to_table, delete_user_history
from Messages.settingsmsg import new_message, update_message
from services.logging import logs_bot
from aiogram.fsm.context import FSMContext
import asyncio
from handlers.subscription_manager import update_pass_date
from datetime import datetime

router = Router(name=__name__)

@router.callback_query(F.data.in_({
    "Mode", "Mode_new", 
    "claude-3-5-sonnet", "claude-3-haiku", 
    "gpt-4o-mini", "gemini-1.5-flash", "gpt-4o",
    "deepseek-v3", "deepseek-r1", "o1-mini", "o1", "o3-mini"
}))
async def general_main_mode(call: CallbackQuery):
    get_data_user = await get_table_data("UsersAI")
    
    # Находим пользователя в списке записей
    user_data = next((user for user in get_data_user if user.get('chatId') == call.from_user.id), None)
    current_model = user_data.get('typeGpt', 'gpt-4o-mini') if user_data else 'gpt-4o-mini'

    if call.data != "Mode" and call.data != "Mode_new":
        # Проверяем, есть ли у пользователя доступные запросы для выбранной модели
        static_ai_users = await get_table_data("StaticAIUsers")
        user_limits = next((user for user in static_ai_users if user.get('chatId') == call.from_user.id), None)
        
        if user_limits and call.data in user_limits.get('dataGpt', {}):
            remaining_requests = user_limits['dataGpt'].get(call.data, 0)
            
            if remaining_requests <= 0:
                # У пользователя нет запросов для этой модели
                await call.answer(f"У вас закончились запросы для модели {call.data}. Приобретите подписку для продолжения.", show_alert=True)
                return
        
        if call.data == current_model:
            # Если выбрана та же модель, просто отвечаем на callback без обновления сообщения
            await call.answer()
            return
        
        # Если выбрана новая модель
        current_model = call.data
        await add_to_table("UsersAI", {
            "chatId": call.from_user.id,
            "typeGpt": current_model
        })
    
    # Обновляем сообщение только при смене модели или открытии меню
    keyboard = await get_main_keyboard_mode(current_model, call.from_user.id)
    try:
        if call.data == "Mode_new":
            # Сначала удаляем старую клавиатуру
            await call.message.edit_reply_markup(reply_markup=None)
            
            # Добавляем небольшую задержку для визуального эффекта
            await asyncio.sleep(0.2)
            
            await new_message(
                call.message, 
                MESSAGES['ru']['mode_ai'], 
                keyboard
            )
        else:
            await update_message(
                call.message, 
                MESSAGES['ru']['mode_ai'], 
                keyboard
            )
    except Exception as e:
        await call.answer("Произошла ошибка при обновлении сообщения")
        return


@router.callback_query(F.data == "Restart")
async def general_main_restart(call: CallbackQuery):
    try:
        
        # Очищаем историю
        await delete_user_history(call.from_user.id)
        
        # Обновляем сообщение
        await update_message(
            call.message,
            MESSAGES['ru']['reset_context'],
            await backstep_menu_message()
        )
        
    except Exception as e:
        await call.answer("Произошла ошибка при перезапуске")
        await logs_bot("error", f"Error in restart handler: {str(e)}")



@router.callback_query(F.data == "BackButton")
async def utils_back_button(call: CallbackQuery, state :FSMContext):
    await state.clear()
    await update_message(call.message, MESSAGES['ru']['start'], await get_general_menu())

@router.callback_query(F.data == "Help")
async def general_main_help(call: CallbackQuery):
    await update_message(call.message,  MESSAGES['ru']['help'], await backstep_menu_message())

@router.callback_query(F.data == "Profile")
async def general_main_profile(call: CallbackQuery):
    try:
        # Получаем данные пользователя асинхронно
        users_data = await get_table_data("Users")
        users_ai = await get_table_data("UsersAI")
        users_pay_pass = await get_table_data("UsersPayPass")

        # Находим данные конкретного пользователя
        user_data = next((u for u in users_data if u.get("chatId") == call.from_user.id), None)
        user_ai = next((u for u in users_ai if u.get("chatId") == call.from_user.id), None)
        user_pay_pass = next((u for u in users_pay_pass if u.get("chatId") == call.from_user.id), None)
        await update_pass_date(call.from_user.id, user_pay_pass)

        # Проверяем наличие всех необходимых данных
        if not user_data:
            raise ValueError("User data not found")
        if not user_ai:
            raise ValueError("User AI data not found")
        if not user_pay_pass:
            raise ValueError("User payment data not found")
            
        created_at = user_data.get('created_at', 'Неизвестно')
        
        # Форматируем данные
        user_id = call.from_user.id
        gpt_model = user_ai.get('typeGpt', 'gpt-4o-mini')
        subscription = user_pay_pass.get('tarif', 'NoBase')
        updated_pass = user_pay_pass.get('updated_pass', 'Неизвестно')
        expiration_date = user_pay_pass.get('expiration_date', 'Неизвестно')
        
        # Получаем локализованные сообщения
        profile_text = (
            f"{MESSAGES['ru']['profile']['is_profile']}\n"
            f"{MESSAGES['ru']['profile']['id_user']} {user_id}\n"
            f"{MESSAGES['ru']['profile']['gpt_model']} {gpt_model}\n"
            f"{MESSAGES['ru']['profile']['user_subscription']} {subscription}\n"
            f"{MESSAGES['ru']['profile']['limit_bot']}\n"
            f"{MESSAGES['ru']['profile']['data_reg']} {created_at}\n\n"
            f"{MESSAGES['ru']['profile']['data_pass']} {updated_pass}\n"
            f"{MESSAGES['ru']['profile']['expiration_date']} {expiration_date}\n"
        )
        
        # Получаем клавиатуру с учетом статуса подписки
        keyboard = await get_profile_keyboard(subscription != "NoBase", subscription == "Base")
        
        # Обновляем сообщение
        await update_message(
            call.message,
            profile_text,
            keyboard
        )
        
    except Exception as e:
        await logs_bot("error", f"Profile error: {str(e)}")
        await call.answer("Ошибка при загрузке профиля")


@router.callback_query(F.data == "Pay")
async def general_main_pay(call: CallbackQuery):
    users_pay_pass = await get_table_data("UsersPayPass")
    user_pay_pass = next((u for u in users_pay_pass if u.get("chatId") == call.from_user.id), None)
    
    # Check if user has a subscription
    if user_pay_pass and user_pay_pass.get("tarif", "NoBase") != "NoBase":
        # Get expiration date
        expiration_date = user_pay_pass.get("expiration_date", "")
        current_time = datetime.now()
        subscription_type = user_pay_pass.get("tarif", "NoBase")
        
        try:
            # Parse expiration date
            if expiration_date:
                expiration_dt = datetime.strptime(expiration_date, "%H:%M %d-%m-%Y")
                
                # Calculate days remaining
                days_remaining = (expiration_dt - current_time).days
                
                if days_remaining <= 0:
                    # Subscription expired
                    await update_message(
                        call.message, 
                        MESSAGES['ru']['subscription_expired'], 
                        await backstep_menu_message_pass()
                    )
                elif days_remaining <= 3:
                    # Subscription about to expire
                    await update_message(
                        call.message, 
                        f"{MESSAGES['ru']['subscription_expiring_soon']}\n"
                        f"Осталось дней: {days_remaining}",
                        await get_pay_keyboard(True, subscription_type == "Base")  # True indicates renewal option, second param for upgrade option
                    )
                else:
                    # Subscription active
                    await update_message(
                        call.message, 
                        f"{MESSAGES['ru']['subscription_active']}\n"
                        f"Тип подписки: {subscription_type}\n"
                        f"Действует до: {expiration_date}\n"
                        f"Осталось дней: {days_remaining}",
                        await get_pay_keyboard(True, subscription_type == "Base")  # True indicates renewal option, second param for upgrade option
                    )
            else:
                # No expiration date set
                await update_message(
                    call.message, 
                    MESSAGES['ru']['pay_end_plus'], 
                    await get_pay_keyboard(True, subscription_type == "Base")
                )
        except ValueError:
            # Date parsing error
            await update_message(
                call.message, 
                MESSAGES['ru']['pay_end_plus'], 
                await get_pay_keyboard(True, user_pay_pass.get("tarif", "NoBase") == "Base")
            )
    else:
        # No subscription
        await update_message(
            call.message, 
            MESSAGES['ru']['pay_info'], 
            await backstep_menu_message_pass()
        )