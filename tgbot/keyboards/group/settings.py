from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


class SettingsEmoji(CallbackData, prefix="settings_emoji"):
    emoji_key: str
    emoji_id: str


class SettingsEmojiPage(CallbackData, prefix="settings_emoji_page"):
    emoji_key: str
    page: int


def settings_emoji(
    emoji_key: str, custom_emojis: list, page: int = 0
) -> InlineKeyboardMarkup:
    # Configuration
    emojis_per_page = 20  # 5 rows * 4 emojis
    emojis_per_row = 4

    # Calculate pagination
    total_emojis = len(custom_emojis)
    total_pages = (total_emojis + emojis_per_page - 1) // emojis_per_page
    start_index = page * emojis_per_page
    end_index = min(start_index + emojis_per_page, total_emojis)

    buttons = []

    # Add emoji buttons for current page
    current_page_emojis = custom_emojis[start_index:end_index]

    for i in range(0, len(current_page_emojis), emojis_per_row):
        row = []
        for j in range(emojis_per_row):
            if i + j < len(current_page_emojis):
                emoji = current_page_emojis[i + j]
                row.append(
                    InlineKeyboardButton(
                        text=emoji.emoji,
                        callback_data=SettingsEmoji(
                            emoji_key=emoji_key,
                            emoji_id=emoji.custom_emoji_id,
                        ).pack(),
                    )
                )
        if row:  # Only add non-empty rows
            buttons.append(row)

    # Add navigation buttons if there are multiple pages
    if total_pages > 1:
        nav_row = []

        # Предыдущая страница
        if page > 0:
            nav_row.append(
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=SettingsEmojiPage(
                        emoji_key=emoji_key,
                        page=page - 1,
                    ).pack(),
                )
            )

        # Индикатор страницы
        nav_row.append(
            InlineKeyboardButton(
                text=f"{page + 1}/{total_pages}",
                callback_data="noop",
            )
        )

        # Следующая страница
        if page < total_pages - 1:
            nav_row.append(
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=SettingsEmojiPage(
                        emoji_key=emoji_key,
                        page=page + 1,
                    ).pack(),
                )
            )

        buttons.append(nav_row)
        buttons.append([
            InlineKeyboardButton(text="❌ Отмена", callback_data="emoji_cancel")
        ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard
