from functools import wraps
import logging
from celery.utils.log import get_task_logger
from .email import send_admin_email

logger = get_task_logger(__name__)

def notification_on_error(func):
    @wraps(func)
    def inner_call(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"{func.__name__}\n\n\n{e}")
            send_admin_email(subject=f"{func.__name__}", content=f"{e}")
    return inner_call

