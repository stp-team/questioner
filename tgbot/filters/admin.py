from aiogram.filters import BaseFilter
from aiogram.types import Message
from stp_database.models.STP import Employee

from tgbot.misc.dicts import executed_codes

ADMIN_ROLE = 10


class AdminFilter(BaseFilter):
    async def __call__(self, obj: Message, user: Employee, **kwargs) -> bool:
        if user is None:
            return False

        return user.role == executed_codes["root"]
