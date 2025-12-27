import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, StartMode
from aiogram_dialog.api.exceptions import NoContextError
from stp_database.models.Questions import Question
from stp_database.models.STP import Employee
from stp_database.repo.Questions.requests import QuestionsRequestsRepo

from tgbot.dialogs.states.user.main import UserSG
from tgbot.keyboards.user.main import (
    CancelQuestion,
)
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
    except NoContextError:
        pass

    await dialog_manager.start(UserSG.menu, mode=StartMode.RESET_STACK)


@user_router.callback_query(CancelQuestion.filter(F.action == "cancel"))
async def cancel_question(
    callback: CallbackQuery,
    callback_data: CancelQuestion,
    state: FSMContext,
    questions_repo: QuestionsRequestsRepo,
    user: Employee,
):
    question: Question = await questions_repo.questions.get_question(
        token=callback_data.token
    )

    if (
        question
        and question.status == "open"
        and not question.duty_userid
        and not question.end_time
    ):
        group_settings = await questions_repo.settings.get_settings_by_group_id(
            group_id=question.group_id
        )

        await callback.bot.edit_forum_topic(
            chat_id=question.group_id,
            message_thread_id=question.topic_id,
            icon_custom_emoji_id=group_settings.get_setting("emoji_fired"),
        )
        await callback.bot.close_forum_topic(
            chat_id=question.group_id,
            message_thread_id=question.topic_id,
        )
        await questions_repo.questions.delete_question(token=question.token)
        await remove_question_timer(question=question)
        await callback.bot.send_message(
            chat_id=question.group_id,
            message_thread_id=question.topic_id,
            text="""<b>🔥 Отмена вопроса</b>
        
Специалист отменил вопрос

<i>Вопрос будет удален через 30 секунд</i>""",
        )
        await callback.answer("Вопрос успешно удален")
    elif not question:
        await callback.answer("Не удалось найти отменяемый вопрос")
    else:
        await callback.answer("Вопрос не может быть отменен. Он уже в работе")
    await callback.answer()
