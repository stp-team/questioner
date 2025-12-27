from aiogram_dialog import DialogManager
from stp_database.models.STP import Employee
from stp_database.repo.Questions import QuestionsRequestsRepo
from stp_database.repo.STP import MainRequestsRepo

from tgbot.misc.helpers import format_fullname


async def history_getter(
    user: Employee,
    questions_repo: QuestionsRequestsRepo,
    **_kwargs,
):
    questions = await questions_repo.questions.get_questions(
        employee_userid=user.user_id
    )

    for q in questions:
        q.start_time = q.start_time.strftime("%d.%m.%Y %H:%M")

    return {
        "user_questions": questions,
        "questions_length": len(questions),
        "have_questions": True if questions else False,
    }


async def details_getter(
    user: Employee,
    stp_repo: MainRequestsRepo,
    questions_repo: QuestionsRequestsRepo,
    dialog_manager: DialogManager,
    **_kwargs,
):
    """Получение данных для просмотра деталей вопроса."""
    question_token = dialog_manager.dialog_data.get("question_token")
    question = await questions_repo.questions.get_question(token=question_token)

    duty = await stp_repo.employee.get_users(user_id=question.duty_userid)
    regulation = (
        f"<a href='{question.clever_link}'>Clever</a>"
        if question.clever_link
        else "Не указан"
    )

    return {
        "duty": format_fullname(duty, True, True),
        "employee": format_fullname(user, True, True),
        "start_time": question.start_time.strftime("%d.%m.%Y %H:%M"),
        "end_time": question.end_time.strftime("%d.%m.%Y %H:%M"),
        "clever_link": regulation,
        "return": "Да" if question.allow_return else "Нет",
        "question": question,
    }
