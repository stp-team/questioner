import logging

from aiogram.filters import BaseFilter
from aiogram.types import Message
from sqlalchemy import Sequence
from stp_database.models.Questions import Question
from stp_database.repo.Questions import QuestionsRequestsRepo

logger = logging.getLogger(__name__)


class ActiveQuestion(BaseFilter):
    async def __call__(
        self, obj: Message, questions_repo: QuestionsRequestsRepo, **kwargs
    ) -> dict[str, str] | bool:
        """Filter to check if user has an active question
        ONLY works in private chats, not in groups
        :param obj: Message object being filtered
        :param questions_repo: Database repository for questions
        :param kwargs: Additional arguments
        :return: Status whether user has an active question
        """
        if obj.chat.type != "private":
            return False

        active_questions: Sequence[
            Question
        ] = await questions_repo.questions.get_active_questions()

        for question in active_questions:
            if question.employee_userid == obj.from_user.id:
                active_question_token = question.token

                logger.info(
                    f"[Активные вопросы] Найден активный вопрос с токеном {active_question_token} у специалиста {obj.from_user.id}"
                )

                return {"active_question_token": active_question_token}

        logger.info(
            f"[Активные вопросы] Не найдено активных вопросов у специалиста {obj.from_user.id}"
        )
        return False


class ActiveQuestionWithCommand(BaseFilter):
    def __init__(self, command: str = None):
        self.command = command

    async def __call__(
        self, obj: Message, questions_repo: QuestionsRequestsRepo, **kwargs
    ) -> None | bool | dict[str, str]:
        if self.command:
            if obj.chat.type != "private":
                return False

            if not obj.text or not obj.text.startswith(f"/{self.command}"):
                return False

            current_questions: Sequence[
                Question
            ] = await questions_repo.questions.get_active_questions()

            for question in current_questions:
                if question.employee_userid == obj.from_user.id:
                    active_question_token = question.token

                    logger.info(
                        f"[Активные вопросы] Найден активный вопрос с токеном {active_question_token} у специалиста {obj.from_user.id}"
                    )

                    return {"active_question_token": active_question_token}

            return False
        logger.info(
            f"[Активные вопросы] Не найдено активных вопросов у специалиста {obj.from_user.id}"
        )
        return None
