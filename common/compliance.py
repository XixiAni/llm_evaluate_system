import threading
from common.logger import get_logger
from common.yaml_reader import YamlReader
from common.error_code import ErrorCode

logger = get_logger("compliance")


class ComplianceChecker:
    """
    内容合规性校验器
    基于配置的敏感词库执行内容合规检测，支持规则配置化、多场景复用
    设计模式：线程安全单例，全程仅初始化一次
    """

    def __init__(self):
        """
        初始化合规校验器，从配置文件加载敏感词库，缺失时使用默认空列表兜底
        """
        rules = YamlReader.read_file("eval_rules.yaml")
        self.sensitive_words = rules.get("sensitive_words", [])

    def check(self, content: str) -> dict:
        """
        执行内容合规性校验
        Args:
            content: 待校验文本
        Returns:
            dict: 校验结果
                - pass: 是否通过
                - msg: 校验说明
        """
        if not self.sensitive_words:
            return {
                "pass": True,
                "msg": "未配置敏感词库，跳过合规性校验"
            }

        hit_words = []
        for word in self.sensitive_words:
            if word in content:
                hit_words.append(word)

        if hit_words:
            return {
                "pass": False,
                "msg": f"{ErrorCode.COMPLIANCE_SENSITIVE_WORD.msg}：{','.join(hit_words)}"
            }

        return {
            "pass": True,
            "msg": "合规性校验通过"
        }


# ========== 线程安全单例实现 ==========
_compliance_checker_instance = None
_compliance_lock = threading.Lock()


def __getattr__(name):
    """模块级属性访问拦截，实现懒加载单例"""
    if name == "compliance_checker":
        global _compliance_checker_instance
        if not _compliance_checker_instance:
            with _compliance_lock:
                if not _compliance_checker_instance:
                    _compliance_checker_instance = ComplianceChecker()
        return _compliance_checker_instance
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
