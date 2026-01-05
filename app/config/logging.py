import logging
import sys
from multiprocessing import Queue

from app.config.settings import get_settings


def setup_logging() -> None:
    settings = get_settings()
    
    logger = logging.getLogger("meeting-stt")
    logger.setLevel(logging.INFO)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    if settings.loki_url:
        try:
            import logging_loki
            
            tags = {
                "app": settings.app_name,
                "environment": settings.environment,
            }
            
            auth = None
            if settings.loki_auth_username and settings.loki_auth_password:
                auth = (settings.loki_auth_username, settings.loki_auth_password)
            
            loki_handler = logging_loki.LokiQueueHandler(
                Queue(-1),
                url=settings.loki_url,
                tags=tags,
                auth=auth,
                version="1",
            )
            logger.addHandler(loki_handler)
            logger.info("Loki logging handler initialized")
        except ImportError:
            logger.warning("python-logging-loki not installed, skipping Loki handler")
        except Exception as e:
            logger.warning(f"Failed to initialize Loki handler: {e}")
