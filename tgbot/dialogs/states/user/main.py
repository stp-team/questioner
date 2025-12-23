from aiogram.fsm.state import State, StatesGroup


class UserSG(StatesGroup):
    """Группа состояний специалистов и дежурных."""

    # Меню
    menu = State()


class AskQuestionSG(StatesGroup):
    question_text = State()
    question_link = State()
