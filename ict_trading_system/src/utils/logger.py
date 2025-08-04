
import logging
from logging.handlers import TimedRotatingFileHandler
import os

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
LOG_FILE = os.path.join(LOG_DIR, 'app.log')

os.makedirs(LOG_DIR, exist_ok=True)

def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s %(name)s: %(message)s')
    # Daily rotation, keep 14 days
    file_handler = TimedRotatingFileHandler(LOG_FILE, when="midnight", interval=1, backupCount=14)
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.handlers = [file_handler, stream_handler]
    # For log shipping, add a handler here (e.g., HTTP, S3, Loki, etc.)
