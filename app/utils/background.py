# Preserve correlation context for background tasks
import functools
from contextvars import copy_context
from typing import Callable, Any


def run_in_background_with_context(func: Callable, *args: Any, **kwargs: Any):
    """Preserve contextvars (e.g., correlation_id) in FastAPI BackgroundTasks."""
    ctx = copy_context()

    async def _async_task():
        ctx.run(functools.partial(func, *args, **kwargs))

    return _async_task
