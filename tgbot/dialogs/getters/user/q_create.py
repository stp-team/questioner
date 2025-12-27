from aiogram_dialog import DialogManager


async def confirmation_getter(dialog_manager: DialogManager, **_kwargs):
    """Получение данных для подтверждения."""
    user_message = dialog_manager.dialog_data.get("user_message", {})
    regulation_link = dialog_manager.dialog_data.get("regulation_link", "")

    return {
        "user_text": user_message.get("text", "Без текста"),
        "has_attachments": "photo" in user_message or "document" in user_message,
        "regulation_link": regulation_link,
    }
