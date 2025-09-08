
import logging
from logging.handlers import TimedRotatingFileHandler
import os

LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'logs'))
LOG_FILE = os.path.join(LOG_DIR, 'app.log')

os.makedirs(LOG_DIR, exist_ok=True)

file_handler = None

def setup_logging():
    global file_handler
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.propagate = True
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s %(name)s: %(message)s')
    # Close previous file handler if it exists
    if file_handler:
        file_handler.close()
        file_handler = None
    # Daily rotation, keep 14 days
    file_handler = TimedRotatingFileHandler(LOG_FILE, when="midnight", interval=1, backupCount=14)
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root_logger.handlers = [file_handler, stream_handler]
    root_logger.info("[BOOT] Logging system initialized and writing to %s", LOG_FILE)

def close_logging():
    global file_handler
    if file_handler:
        file_handler.close()
        file_handler = None
