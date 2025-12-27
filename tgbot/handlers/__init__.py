"""Import all routers and add them to routers_list."""

from tgbot.handlers.user.main import user_router

from .admin.main import admin_router
from .admin.stats_extract import stats_router
from .group.main import topic_router
from .group.main_cmds import main_topic_cmds_router
from .group.topic_cmds import topic_cmds_router
from .user.q_active import user_q
from .user.q_return import user_q_return

routers_list = [
    admin_router,
    stats_router,
    main_topic_cmds_router,
    topic_cmds_router,
    topic_router,
    user_q,
    user_q_return,
    user_router,
]

__all__ = [
    "routers_list",
]
