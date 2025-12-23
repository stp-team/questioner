from stp_database.models.STP import Employee
from stp_database.repo.Questions import QuestionsRequestsRepo


async def menu_getter(
    user: Employee,
    questions_repo: QuestionsRequestsRepo,
    **_kwargs,
):
    questions_count_day = await questions_repo.questions.get_questions_count_today(
        employee_userid=user.user_id
    )
    questions_count_month = (
        await questions_repo.questions.get_questions_count_last_month(
            employee_userid=user.fullname
        )
    )

    return {
        "is_employee": True if user else False,
        "questions_count_day": questions_count_day,
        "questions_count_month": questions_count_month,
    }
