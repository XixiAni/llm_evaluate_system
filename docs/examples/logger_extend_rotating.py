import os
import logging
import time
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime

class DailyStartRotatingFileHandler(TimedRotatingFileHandler):
    """
    扩展 TimedRotatingFileHandler：

    1. 初始化时主动归档历史遗留文件，保证每次启动都写入当天文件

    2. 保留原生 midnight 跨天自动切割能力

    3. 归档文件以日期命名
    """
    def __init__(self, filename: str, when: str = "midnight", interval: int = 1, backupCount: int = 0, encoding: str = None):
        self.base_dir = os.path.dirname(filename)
        self.base_filename = os.path.basename(filename)

        # 初始化前先归档历史遗留文件
        self._archive_existing_file(filename)

        # 调用父类原生初始化
        super().__init__(
            filename=filename,
            when=when,
            interval=interval,
            backupCount=backupCount,
            encoding=encoding,
            delay=False
        )

        # 自定义归档命名：去掉基础文件名前缀，直接用日期做文件名
        self.suffix = "%Y-%m-%d.log"
        self.namer = lambda name: name.replace(f"{self.base_filename}.", "")
    def _archive_existing_file(self, file_path: str) -> None:
        """
        启动时归档已存在的历史日志文件

        规则：根据文件最后修改时间，重命名为对应日期的归档文件

        注意：依赖操作系统文件mtime(修改时间)；Windows文件被占用会归档失败
        """
        if not os.path.exists(file_path):
            return

        try:
            # 取文件最后修改时间对应的日期
            mtime = os.path.getmtime(file_path)
            file_date = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
            archive_path = os.path.join(self.base_dir, f"{file_date}.log")

            # 当天的文件不归档，直接追加
            today = datetime.now().strftime("%Y-%m-%d")
            if file_date == today:
                return
            
            # 避免重名冲突，已存在则追加（分块读写防止大文件占满内存）
            if os.path.exists(archive_path):
                BUF_SIZE = 1024 * 1024
                # 已有同日归档，追加内容
                with open(file_path, "r", encoding="utf-8") as src, open(archive_path, "a", encoding="utf-8") as dst:
                    while chunk := src.read(BUF_SIZE):
                        dst.write(chunk)
                os.remove(file_path)
            else:
                os.rename(file_path, archive_path)
        except OSError as e:
            # 文件锁、权限、IO异常，归档失败只警告，不阻断主程序启动
            logger = logging.getLogger("logger_init")
            logger.warning(f"启动归档历史日志失败，继续运行：{str(e)}", exc_info=True)

# ========== 原有日志配置逻辑 ==========
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, "logs")
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
if not root_logger.handlers:
    # 使用扩展后的处理器
    file_handler = DailyStartRotatingFileHandler(
        filename=os.path.join(LOG_DIR, "eval.log"),
        when="midnight",
        interval=1,
        backupCount=0,
        encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    file_handler.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
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
