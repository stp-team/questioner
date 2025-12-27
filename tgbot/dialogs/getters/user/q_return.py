from aiogram_dialog import DialogManager
from stp_database.models.Questions import Question
from stp_database.models.STP import Employee
from stp_database.repo.Questions import QuestionsRequestsRepo
from stp_database.repo.STP import MainRequestsRepo

from tgbot.misc.helpers import format_fullname


async def return_getter(
    user: Employee,
    questions_repo: QuestionsRequestsRepo,
    **_kwargs,
):
    questions = await questions_repo.questions.get_last_questions_by_chat_id(
        employee_chat_id=user.user_id, limit=5
    )

    for q in questions:
        q.start_time = q.start_time.strftime("%d.%m.%Y %H:%M")

    return {
        "user_questions": questions,
        "questions_length": len(questions),
        "have_questions": True if questions else False,
    }


async def confirmation_getter(
    user: Employee,
    stp_repo: MainRequestsRepo,
    questions_repo: QuestionsRequestsRepo,
    dialog_manager: DialogManager,
    **_kwargs,
):
    """Получение данных для окна подтверждения возврата вопроса."""
    question_token = dialog_manager.dialog_data.get("question_token")

    # Получаем все доступные вопросы для возврата
    return_questions = (
        await questions_repo.questions.get_available_to_return_questions()
    )

    # Находим выбранный вопрос
    selected_question = None
    for question in return_questions:
        if (
            str(question.token) == str(question_token)
            and question.employee_userid == user.user_id
        ):
            selected_question: Question = question
            break

    duty = await stp_repo.employee.get_users(user_id=selected_question.duty_userid)

    return {
        "question": selected_question,
        "text": selected_question.question_text if selected_question else "",
        "duty": format_fullname(duty, True, True),
        "start_time": selected_question.start_time.strftime("%d.%m.%Y %H:%M"),
        "end_time": selected_question.end_time.strftime("%d.%m.%Y %H:%M"),
        "token": selected_question.token if selected_question else "",
    }
