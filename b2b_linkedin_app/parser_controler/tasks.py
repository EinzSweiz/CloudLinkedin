from celery import shared_task
from django.core.cache import cache
from django_redis import get_redis_connection
from parser_controler.utils import save_parsing_info
from parser.engine.linkedin.search_profiles import search_linkedin_profiles
from parser_controler.models import ParserRequest
from redis.lock import Lock
import time
from redis.client import Redis
import redis
import logging

logger = logging.getLogger(__name__)

LOCK_EXPIRE = 60 * 60  # 1 hour

# @shared_task(bind=True, name="start_parsing")
# def start_parsing(self):
#     lock_id = "start_parsing_lock"
#     acquire_lock = lambda: cache.add(lock_id, "true", LOCK_EXPIRE)

#     if acquire_lock():
#         logger.info("Start parsing task started.")
#         try:
#             # 🔽 логика парсинга здесь
#             ...
#         finally:
#             cache.delete(lock_id)
#             logger.info("Start parsing task finished.")
#     else:
#         logger.warning("Start parsing already running. Skipping this run.")
#comment
@shared_task(bind=True, name="start_parsing")
def start_parsing(self, keywords, location, limit, start_page, end_page, parser_request_id=None):
    redis_conn = redis.StrictRedis(host="redis", port=6379, db=0)
    lock = redis_conn.lock("start_parsing_lock", timeout=LOCK_EXPIRE)

    logger.info("We are starting parsing")

    try:
        with lock:
            logger.info("Lock acquired — starting parsing task.")

            if parser_request_id:
                ParserRequest.objects.filter(id=parser_request_id).update(status='running')

            profiles = search_linkedin_profiles(
                keywords=keywords,
                location=location,
                limit=limit,
                start_page=start_page,
                end_page=end_page,
            )

            for profile in profiles:
                save_parsing_info(
                    full_name=profile.get("name", ""),
                    position=profile.get("position", ""),
                    company_name=profile.get("company", ""),
                    email=profile.get("email", None)
                )
            logger.info("Parsing completed successfully.")

            if parser_request_id:
                ParserRequest.objects.filter(id=parser_request_id).update(status='completed')

    except redis.exceptions.LockError:
        logger.warning("Lock is already active — skipping this run.")
    except Exception as e:
        logger.exception("An error occurred during parsing.")
        if parser_request_id:
            ParserRequest.objects.filter(id=parser_request_id).update(status='error')