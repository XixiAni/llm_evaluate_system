import os
import json
import logging
import traceback
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, "logs")

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# 文本日志格式（控制台用）
TEXT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 全局trace_id，用于链路追踪
_trace_id = "default"

def set_trace_id(trace_id: str) -> None:
    """设置全局链路追踪ID，贯穿本次运行所有日志"""
    global _trace_id
    _trace_id = trace_id

# 【注意】模块导入时获取本次程序启动的日期；适合脚本短生命周期场景
today_str = datetime.now().strftime("%Y-%m-%d")
LOG_FILE_PATH = os.path.join(LOG_DIR, f"{today_str}.log")

root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)  # 总开关开最低，由handler分别控制级别

# 全局handler引用，用于后续动态调整级别
_file_handler = None
_console_handler = None

class JsonFormatter(logging.Formatter):
    """结构化JSON日志格式化器，生产环境日志采集专用"""
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record, DATE_FORMAT),
            "level": record.levelname,
            "module": record.name,
            "trace_id": _trace_id,
            "process_id": record.process,
            "thread_name": record.threadName,
            "message": record.getMessage(),
            "file": record.filename,
            "line": record.lineno
        }

        # 异常级别自动携带完整堆栈
        if record.exc_info:
            log_entry["exception"] = traceback.format_exc()

        return json.dumps(log_entry, ensure_ascii=False)

class TraceIdFilter(logging.Filter):
    """注入trace_id到日志记录"""
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = _trace_id
        return True

# 守卫：避免模块重复导入重复添加handler，防止日志重复输出
if not root_logger.handlers:
    # 文件处理器：普通FileHandler，按启动日期命名，追加写入;
    # JSON格式，生产采集用
    _file_handler = logging.FileHandler(
        filename=LOG_FILE_PATH,
        mode="a",
        encoding="utf-8"
    )
    _file_handler.setFormatter(JsonFormatter())
    _file_handler.setLevel(logging.INFO)
    _file_handler.addFilter(TraceIdFilter())
    root_logger.addHandler(_file_handler)

    # 控制台处理器：文本格式，本地调试用
    _console_handler = logging.StreamHandler()
    _console_handler.setFormatter(logging.Formatter(TEXT_LOG_FORMAT, DATE_FORMAT))
    _console_handler.setLevel(logging.INFO)
    _console_handler.addFilter(TraceIdFilter())

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
        name: 日志记录器名称，通常传入模块名用于日志溯源
    Returns:
        logging.Logger: 配置完成的日志记录器对象，支持控制台+文件双输出
    """
    logger = logging.getLogger(name)
    logger.propagate = True
    return logger
