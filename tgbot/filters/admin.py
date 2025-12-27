from aiogram.filters import BaseFilter
from aiogram.types import Message
from stp_database.models.STP import Employee

from tgbot.misc.helpers import get_role

ADMIN_ROLE = 10


class AdminFilter(BaseFilter):
    async def __call__(self, obj: Message, user: Employee, **kwargs) -> bool:
        if user is None:
            return False

        return user.role == get_role(role_name="root", return_id=True)
