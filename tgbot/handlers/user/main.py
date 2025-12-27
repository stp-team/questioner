import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, StartMode
from aiogram_dialog.api.exceptions import NoContextError
from stp_database.models.Questions import Question
from stp_database.models.STP import Employee
from stp_database.repo.Questions.requests import QuestionsRequestsRepo

from tgbot.dialogs.states.user.main import QuestionSG, UserSG
from tgbot.keyboards.user.main import (
    CancelQuestion,
    MainMenu,
)
from tgbot.misc.helpers import format_fullname
from tgbot.services.scheduler import (
    remove_question_timer,
)

user_router = Router()
user_router.message.filter(F.chat.type == "private")
user_router.callback_query.filter(F.message.chat.type == "private")


logger = logging.getLogger(__name__)


@user_router.message(CommandStart())
async def start_user(_message: Message, dialog_manager: DialogManager):
    try:
        await dialog_manager.done()
    except NoContextError as exc:
        logger.debug("No active dialog to finish on /start: %s", exc)

    await dialog_manager.start(UserSG.menu, mode=StartMode.RESET_STACK)


@user_router.callback_query(MainMenu.filter(F.menu == "main"))
async def home(
    _event: CallbackQuery,
    dialog_manager: DialogManager,
):
    await dialog_manager.start(UserSG.menu, mode=StartMode.RESET_STACK)


@user_router.callback_query(CancelQuestion.filter(F.action == "cancel"))
async def cancel_question(
    callback: CallbackQuery,
    callback_data: CancelQuestion,
    questions_repo: QuestionsRequestsRepo,
    user: Employee,
    dialog_manager: DialogManager,
):
    question: Question = await questions_repo.questions.get_question(
        token=callback_data.token
    )

    if not question:
        await callback.answer("Не удалось найти отменяемый вопрос")
        return

    if question.status != "open" or question.duty_userid:
        await callback.answer("Вопрос уже невозможно отменить")
        return

    await callback.answer("Вопрос успешно удален")
    await dialog_manager.start(UserSG.menu, mode=StartMode.RESET_STACK)

    group_settings = await questions_repo.settings.get_settings_by_group_id(
        group_id=question.group_id
    )

    # Редактируем эмодзи и название темы
    await callback.bot.edit_forum_topic(
        chat_id=question.group_id,
        message_thread_id=question.topic_id,
        icon_custom_emoji_id=group_settings.get_setting("emoji_fired"),
    )

    # Закрываем тему
    await callback.bot.close_forum_topic(
        chat_id=question.group_id,
        message_thread_id=question.topic_id,
    )

    # Удаляем вопрос из БД
    await questions_repo.questions.delete_question(token=question.token)

    # Запускаем таймер удаления топика
    await remove_question_timer(question=question)

    # Уведомляем в топике об отмене вопроса
    await callback.bot.send_message(
        chat_id=question.group_id,
        message_thread_id=question.topic_id,
        text=f"""<b>🔥 Отмена вопроса</b>
        
<b>{format_fullname(user, True, True)}</b> отменил вопрос

<i>Топик будет удален через 30 секунд</i>""",
    )


@user_router.callback_query(MainMenu.filter(F.menu == "ask"))
async def ask_question(
    _event: CallbackQuery,
    dialog_manager: DialogManager,
):
    await dialog_manager.start(QuestionSG.question_text, mode=StartMode.RESET_STACK)
