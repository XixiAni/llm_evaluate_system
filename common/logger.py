import os
import logging
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, "logs")
LOG_FILE_NAME = f"{datetime.now().strftime('%Y-%m-%d')}.log"
LOG_FILE_PATH = os.path.join(LOG_DIR, LOG_FILE_NAME)

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

logging.basicConfig(
    filename=LOG_FILE_PATH,
    format=LOG_FORMAT,
    datefmt=DATE_FORMAT,
    level=logging.INFO,
    filemode="a",
    encoding="utf-8"
)

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
console_handler.setLevel(logging.INFO)
logging.getLogger().addHandler(console_handler)

def get_logger(name: str = "llm_evaluator") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.propagate = True
    return logger
