import logging
from .models import ParsingInfo
from django.db import IntegrityError

logger = logging.getLogger(__name__)

def save_parsing_info(full_name: str, position: str, company_name: str, email: str = None) -> ParsingInfo:
    """
    Creates and saves a ParsingInfo instance.
    Returns the created instance or None if failed.
    """
    try:
        instance = ParsingInfo.objects.create(
            full_name=full_name.strip(),
            position=position.strip(),
            company_name=company_name.strip(),
            email=email.strip() if email else None
        )
        logger.info(f"Saved ParsingInfo: {instance}")
        return instance
    except IntegrityError as e:
        logger.error(f"Failed to save ParsingInfo for {full_name} @ {company_name}: {e}")
        return None
