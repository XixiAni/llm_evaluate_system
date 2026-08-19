import os
import logging
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, "logs")
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 【注意】模块导入时获取本次程序启动的日期；适合脚本短生命周期场景
today_str = datetime.now().strftime("%Y-%m-%d")
LOG_FILE_PATH = os.path.join(LOG_DIR, f"{today_str}.log")

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# 守卫：避免模块重复导入重复添加handler，防止日志重复输出
if not root_logger.handlers:
    # 文件处理器：普通FileHandler，按启动日期命名，追加写入
    file_handler = logging.FileHandler(
        filename=LOG_FILE_PATH,
        mode="a",
        encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    file_handler.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    console_handler.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)


def get_logger(name: str = "llm_evaluator") -> logging.Logger:
    """
    获取指定名称的日志记录器实例，复用根日志器的处理器与格式配置
    
    Args:
        name: 日志记录器名称，通常传入模块名用于日志溯源，默认值'llm_evaluator'
    Returns:
        logging.Logger: 配置完成的日志记录器对象，支持控制台+文件双输出
    """
    logger = logging.getLogger(name)
    logger.propagate = True
    return logger
