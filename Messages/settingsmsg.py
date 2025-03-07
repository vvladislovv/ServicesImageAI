from aiogram.types import InlineKeyboardMarkup, Message
from services.logging import logs_bot
from Messages.utils import escape_markdown
from aiogram.enums import ParseMode


async def new_message(message: Message, text: str, keyboard=None) -> Message:
    """
    Отправляет новое сообщение с текстом и опциональной клавиатурой.
    Если текст больше 3997 символов, отправляет его частями.

    Args:
        message: Объект сообщения.
        text: Текст сообщения.
        keyboard: Клавиатура (InlineKeyboardMarkup, список или объект с методом as_markup).

    Returns:
        Объект отправленного сообщения.
    """
    try:
        # Преобразуем клавиатуру
        markup = await prepare_keyboard(keyboard)

        try:
            # Экранируем текст
            escaped_text = await escape_markdown(text)

            # Если текст больше 3997 символов, разбиваем на части
            if len(escaped_text) > 3997:
                # Отправляем первую часть с клавиатурой
                first_part = escaped_text[:3997]
                await message.answer(
                    text=first_part, parse_mode=ParseMode.MARKDOWN, reply_markup=markup
                )
                # Отправляем оставшуюся часть без клавиатуры
                remaining_text = escaped_text[3997:]
                return await message.answer(
                    text=remaining_text, parse_mode=ParseMode.MARKDOWN
                )
            else:
                # Если текст меньше 3997 символов, отправляем как есть
                return await message.answer(
                    text=escaped_text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=markup,
                )

        except Exception as md_error:
            await logs_bot("warning", f"Markdown formatting error: {md_error}")
            # Если не получилось, отправляем с экранированным текстом без форматирования
            if len(text) > 3997:
                await message.answer(text=text[:3997], reply_markup=markup)
                return await message.answer(text=text[3997:])
            else:
                return await message.answer(text=text, reply_markup=markup)

    except Exception as e:
        await message.answer(text=remaining_text, parse_mode=None)
        await logs_bot("error", f"Error in new_message: {e}")
        # Отправляем экранированное сообщение об ошибке
        return await message.answer(
            "⚠️ Произошла ошибка при обработке запроса. Попробуйте позже."
        )


async def update_message(message: Message, text: str, keyboard=None) -> bool:
    """Обновляет существующее сообщение с новым текстом и опциональной клавиатурой.
    Если текст больше 3997 символов, отправляет его частями."""
    try:
        markup = await prepare_keyboard(keyboard)

        try:
            # Экранируем текст
            escaped_text = await escape_markdown(text)

            # Если текст больше 3997 символов, разбиваем на части
            if len(escaped_text) > 3997:
                # Обновляем первую часть с клавиатурой
                first_part = escaped_text[:3997]
                await message.edit_text(
                    text=first_part, parse_mode=ParseMode.MARKDOWN, reply_markup=markup
                )
                # Отправляем оставшуюся часть как новое сообщение
                remaining_text = escaped_text[3997:]
                await message.answer(text=remaining_text, parse_mode=ParseMode.MARKDOWN)
                return True
            else:
                # Если текст меньше 3997 символов, обновляем как есть
                await message.edit_text(
                    text=escaped_text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=markup,
                )
                return True

        except Exception as md_error:
            # Логируем ошибку для отладки
            await logs_bot("warning", f"Markdown formatting error: {md_error}")

            # Если не получилось с форматированием, пробуем с экранированным текстом
            try:
                if len(text) > 3997:
                    await message.edit_text(text=text[:3997], reply_markup=markup)
                    await message.answer(text=text[3997:])
                else:
                    await message.edit_text(text=text, reply_markup=markup)
                return True
            except Exception as plain_error:
                await message.answer(text=remaining_text, parse_mode=None)
                await logs_bot(
                    "error", f"Failed to send message without formatting: {plain_error}"
                )
                return False

    except Exception as e:
        await message.answer(text=remaining_text, parse_mode=None)
        if "message is not modified" not in str(e):
            await logs_bot("error", f"Error in update_message: {e}")
        return False


async def prepare_keyboard(keyboard):
    """Подготовка клавиатуры"""
    if not keyboard:
        return None

    if isinstance(keyboard, InlineKeyboardMarkup):
        return keyboard
    elif isinstance(keyboard, list):
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    elif hasattr(keyboard, "as_markup"):
        return keyboard.as_markup()

    await logs_bot("warning", f"Unsupported keyboard type: {type(keyboard)}")
    return None


async def answer_voice(message, audio, caption):
    """Send voice message with caption"""
    return await message.answer_voice(audio, caption=caption)


async def send_typing_action(message: Message, action_type: str):
    """Отправка действия "печатает"""
    await message.bot.send_chat_action(chat_id=message.chat.id, action=action_type)
    await message.bot.send_chat_action(chat_id=message.chat.id, action=action_type)


async def send_typing_action(message: Message, action_type: str):
    """Отправка действия "печатает"""
    await message.bot.send_chat_action(chat_id=message.chat.id, action=action_type)
    await message.bot.send_chat_action(chat_id=message.chat.id, action=action_type)
