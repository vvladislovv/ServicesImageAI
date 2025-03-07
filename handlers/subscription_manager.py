from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, LabeledPrice, PreCheckoutQuery, Message
from config.confpaypass import get_paypass, get_default_limits, PayPassConfig
from Messages.localization import MESSAGES
import asyncio
from Messages.inlinebutton import (
    backstep_menu_message,
    get_payment_link_keyboard,
    get_subscription_type_keyboard,
)
from Messages.settingsmsg import new_message, update_message
from database.settingsdata import add_to_table, get_table_data
from datetime import datetime, timedelta
from services.logging import logs_bot

router = Router(name=__name__)


@router.callback_query(F.data == "PayStar")
async def pay_star_menu(call: CallbackQuery, bot: Bot):
    # Show subscription type selection
    await update_message(
        call.message,
        MESSAGES["ru"]["select_subscription_type"],
        await get_subscription_type_keyboard(),
    )


@router.callback_query(F.data.in_({"SubscribeBase", "SubscribePro"}))
async def select_subscription_type(call: CallbackQuery, bot: Bot):
    subscription_type = "Base" if call.data == "SubscribeBase" else "Pro"
    subscription_cost = (
        PayPassConfig.BASE_PRICE
        if subscription_type == "Base"
        else PayPassConfig.PRO_PRICE
    )

    # Send invoice
    prices = [LabeledPrice(label="XTR", amount=subscription_cost)]
    await bot.send_invoice(
        chat_id=call.message.chat.id,
        title=f"Подписка {subscription_type}",
        description=f"{MESSAGES['ru']['subscription_info']} {subscription_type}\n"
        f"Стоимость: {subscription_cost}⭐️",
        prices=prices,
        provider_token="",  # Your payment provider token
        payload=f"{subscription_type}_{subscription_cost}",
        currency="XTR",
    )

    await asyncio.sleep(1)
    await new_message(
        call.message, MESSAGES["ru"]["pay_star_back"], await backstep_menu_message()
    )


# Handle pre-checkout query
@router.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery, bot: Bot):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


# Handle successful payment
@router.message(F.successful_payment)
async def successful_payment(message: Message, bot: Bot):
    payment_info = message.successful_payment
    payload = payment_info.invoice_payload

    # Extract subscription type from payload
    subscription_type = payload.split("_")[0]
    is_renewal = len(payload.split("_")) > 2 and payload.split("_")[2] == "renewal"

    # Get user data
    users_pay_pass = await get_table_data("UsersPayPass")
    user_pay_pass = next(
        (u for u in users_pay_pass if u.get("chatId") == message.from_user.id), None
    )

    # Calculate expiration date
    current_time = datetime.now()

    # If renewal and existing subscription hasn't expired yet, add 30 days to current expiration date
    if is_renewal and user_pay_pass and user_pay_pass.get("expiration_date"):
        try:
            existing_expiration = datetime.strptime(
                user_pay_pass.get("expiration_date"), "%H:%M %d-%m-%Y"
            )
            # Only use existing date if it's in the future
            if existing_expiration > current_time:
                expiration_date = (existing_expiration + timedelta(days=30)).strftime(
                    "%H:%M %d-%m-%Y"
                )
            else:
                # If expired, start fresh from current date
                expiration_date = (current_time + timedelta(days=30)).strftime(
                    "%H:%M %d-%m-%Y"
                )
        except ValueError:
            # If date parsing fails, default to 30 days from now
            expiration_date = (current_time + timedelta(days=30)).strftime(
                "%H:%M %d-%m-%Y"
            )
    else:
        # New subscription or no valid existing date
        expiration_date = (current_time + timedelta(days=30)).strftime("%H:%M %d-%m-%Y")

    # Update user subscription
    await add_to_table(
        "UsersPayPass",
        {
            "chatId": message.from_user.id,
            "tarif": subscription_type,
            "updated_pass": current_time.strftime("%H:%M %d-%m-%Y"),
            "expiration_date": expiration_date,
        },
    )

    # Update user limits based on subscription type
    limits = get_paypass(subscription_type).dict()
    api_limits = {}

    # Convert model names to API names
    model_mapping = {
        "gpt_4o_mini": "gpt-4o-mini",
        "gpt_4o": "gpt-4o",
        "claude_3_5_sonnet": "claude-3-5-sonnet",
        "claude_3_haiku": "claude-3-haiku",
        "gemini_1_5_flash": "gemini-1.5-flash",
        "deepseek_v3": "deepseek-v3",
        "deepseek_r1": "deepseek-r1",
        "o1_mini": "o1-mini",
        "o1": "o1",
        "tts": "tts",
        "tts_hd": "tts-hd",
        "o3_mini": "o3-mini",
    }

    for model_name, api_name in model_mapping.items():
        if model_name in limits:
            api_limits[api_name] = limits[model_name]

    # Update user limits
    await add_to_table(
        "StaticAIUsers", {"chatId": message.from_user.id, "dataGpt": api_limits}
    )

    # Determine if this was a renewal with added days
    renewal_message = ""
    if is_renewal and user_pay_pass and user_pay_pass.get("expiration_date"):
        try:
            old_expiration = datetime.strptime(
                user_pay_pass.get("expiration_date"), "%H:%M %d-%m-%Y"
            )
            if old_expiration > current_time:
                days_added = (
                    datetime.strptime(expiration_date, "%H:%M %d-%m-%Y")
                    - old_expiration
                ).days
                renewal_message = f"\nДобавлено дней: {days_added}"
        except ValueError:
            pass

    # Send confirmation message with proper escaping for Telegram's MarkdownV2
    confirmation_message = (
        f"Спасибо за оплату! Ваша подписка {subscription_type} активирована.\n"
        f"Срок действия: до {expiration_date.replace('-', '-')}\n"
        f"{renewal_message}\n"
        f"Теперь у вас доступны расширенные возможности!"
    )

    await new_message(message, confirmation_message)


# card plus pay
@router.callback_query(F.data == "PayCard")
async def pay_card_button(call: CallbackQuery):
    await update_message(
        call.message, MESSAGES["ru"]["pay_card"], await get_payment_link_keyboard()
    )


@router.callback_query(F.data == "RenewSubscription")
async def renew_subscription(call: CallbackQuery, bot: Bot):
    # Get user data
    users_pay_pass = await get_table_data("UsersPayPass")
    user_pay_pass = next(
        (u for u in users_pay_pass if u.get("chatId") == call.from_user.id), None
    )

    if not user_pay_pass:
        await call.answer("Ошибка: данные подписки не найдены")
        return

    current_subscription = user_pay_pass.get("tarif", "NoBase")

    if current_subscription == "NoBase":
        # If no subscription, redirect to subscription selection
        await pay_star_menu(call, bot)
    else:
        # Renew existing subscription
        subscription_cost = (
            PayPassConfig.BASE_PRICE
            if current_subscription == "Base"
            else PayPassConfig.PRO_PRICE
        )

        # Send invoice for renewal
        prices = [LabeledPrice(label="XTR", amount=subscription_cost)]
        await bot.send_invoice(
            chat_id=call.message.chat.id,
            title=f"Продление подписки {current_subscription}",
            description=f"Продление подписки {current_subscription} на 30 дней\n"
            f"Стоимость: {subscription_cost}⭐️",
            prices=prices,
            provider_token="",  # Your payment provider token
            payload=f"{current_subscription}_{subscription_cost}_renewal",
            currency="XTR",
        )

        await asyncio.sleep(1)
        await new_message(
            call.message,
            MESSAGES["ru"]["renewal_initiated"],
            await backstep_menu_message(),
        )


async def update_pass_date(chat_id: int, user_pay_pass: dict):
    """
    Updates subscription status and limits based on expiration date

    Args:
        chat_id: User's chat ID
        user_pay_pass: User's payment/subscription data
    """
    if not user_pay_pass:
        await logs_bot("warning", f"No subscription data found for user {chat_id}")
        return

    current_time = datetime.now()
    created_at = current_time.strftime("%H:%M %d-%m-%Y")

    # Get expiration date
    expiration_date = user_pay_pass.get("expiration_date", "")
    tarif = user_pay_pass.get("tarif", "NoBase")

    # If no expiration date set but has a tarif, set one for 30 days
    if not expiration_date and tarif != "NoBase":
        expiration_date = (current_time + timedelta(days=30)).strftime("%H:%M %d-%m-%Y")
        await add_to_table(
            "UsersPayPass", {"chatId": chat_id, "expiration_date": expiration_date}
        )

    # Check if subscription has expired
    try:
        if expiration_date:
            expiration_dt = datetime.strptime(expiration_date, "%H:%M %d-%m-%Y")

            if current_time >= expiration_dt:
                # Subscription expired, reset to NoBase
                await logs_bot("info", f"Subscription expired for user {chat_id}")

                await add_to_table(
                    "UsersPayPass",
                    {"chatId": chat_id, "tarif": "NoBase", "updated_pass": created_at},
                )

                # Reset limits to default
                await add_to_table(
                    "StaticAIUsers",
                    {"chatId": int(chat_id), "dataGpt": get_default_limits()},
                )

                # Notify user about expiration
                # This would require a bot instance, which we don't have in this function
                # Consider implementing a notification system elsewhere
            else:
                # Subscription still valid
                await logs_bot(
                    "debug",
                    f"Subscription for user {chat_id} is valid until {expiration_date}",
                )
    except ValueError as e:
        await logs_bot("error", f"Date parsing error for user {chat_id}: {str(e)}")
        return


@router.callback_query(F.data == "UpgradeToPro")
async def upgrade_to_pro(call: CallbackQuery, bot: Bot):
    # Get user data
    users_pay_pass = await get_table_data("UsersPayPass")
    user_pay_pass = next(
        (u for u in users_pay_pass if u.get("chatId") == call.from_user.id), None
    )

    if not user_pay_pass or user_pay_pass.get("tarif", "NoBase") != "Base":
        await call.answer("Ошибка: вы не можете повысить подписку")
        return
    print("test")
    # Send invoice for upgrade (price difference between Pro and Base)
    price_difference = PayPassConfig.PRO_PRICE - PayPassConfig.BASE_PRICE
    print(price_difference)
    # Send invoice for upgrade
    prices = [LabeledPrice(label="XTR", amount=price_difference)]
    await bot.send_invoice(
        chat_id=call.message.chat.id,
        title="Повышение до Pro",
        description=f"Повышение подписки с Base до Pro\n"
        f"Доплата: {price_difference}⭐️",
        prices=prices,
        provider_token="",  # Your payment provider token
        payload=f"Pro_{price_difference}_upgrade",
        currency="XTR",
    )

    await asyncio.sleep(1)
    await new_message(
        call.message,
        "Запрос на повышение подписки отправлен. Оплатите счет для завершения процесса.",
        await backstep_menu_message(),
    )
