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
root_logger.setLevel(logging.DEBUG)  # 总开关开最低，由handler分别控制级别

# 全局handler引用，用于后续动态调整级别
_file_handler = None
_console_handler = None

# 守卫：避免模块重复导入重复添加handler，防止日志重复输出
if not root_logger.handlers:
    # 文件处理器：普通FileHandler，按启动日期命名，追加写入
    _file_handler = logging.FileHandler(
        filename=LOG_FILE_PATH,
        mode="a",
        encoding="utf-8"
    )
    _file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    _file_handler.setLevel(logging.INFO)
    root_logger.addHandler(_file_handler)

    # 控制台处理器
    _console_handler = logging.StreamHandler()
    _console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    _console_handler.setLevel(logging.INFO)
    root_logger.addHandler(_console_handler)

# 级别字符串映射
_LEVEL_MAP = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL
}

def setup_log_level(file_level: str = "info", console_level: str = "info") -> None:
    """
    动态设置文件日志与控制台日志的级别

    用于配置加载完成后，覆盖默认级别

    Args:
        file_level: 文件日志级别，debug/info/warning/error/critical
        console_level: 控制台日志级别，debug/info/warning/error/critical
    """
    file_lv = _LEVEL_MAP.get(file_level.lower(), logging.INFO)
    console_lv = _LEVEL_MAP.get(console_level.lower(), logging.INFO)

    if _file_handler:
        _file_handler.setLevel(file_lv)
    if _console_handler:
        _console_handler.setLevel(console_lv)

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
