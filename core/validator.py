import threading
from common.logger import get_logger
from common.yaml_reader import YamlReader
from common.error_code import ErrorCode

logger = get_logger("validator")

class ResponseValidator:
    """
    大模型响应内容校验器

    包含两个维度：有效性校验（空内容、长度不足、高重复）、合规性校验（敏感词匹配）

    所有校验规则从eval_rules.yaml配置读取，缺失时使用默认阈值

    优化点：线程安全单例模式
    """

    def __init__(self):
        """
        初始化校验器，从配置文件加载敏感词库与有效性校验阈值，缺失字段使用默认值兜底
        """
        rules = YamlReader.read_file("eval_rules.yaml")
        self.sensitive_words = rules.get("sensitive_words", [])
        validity_config = rules.get("validity",{})
        self.min_length = validity_config.get("min_length",5)
        self.max_repeat_rate = validity_config.get("max_repeat_rate",0.7)
        # 连续短语复读阈值：同一短语连续出现次数超过该值则判定无效
        self.max_continuous_repeat = validity_config.get("max_continuous_repeat", 2)
        # 检测的短语长度范围（2-4字覆盖绝大多数复读场景）
        self.repeat_phrase_min_len = 2
        self.repeat_phrase_max_len = 4

    def validate_all(self, content: str) -> dict:
        """
        执行全量校验，依次调用有效性与合规性校验

        Args:
            content: 待校验的大模型回答文本
        Returns:
            dict: 校验结果
                - is_valid: 有效性是否通过
                - is_compliant: 合规性是否通过
                - validity_msg: 有效性校验说明
                - compliance_msg: 合规性校验说明
        """
        validity_result = self._validate_validity(content)
        compliance_result = self._validate_compliance(content)
        
        return {
            "is_valid": validity_result["pass"],
            "is_compliant": compliance_result["pass"],
            "validity_msg": validity_result["msg"],
            "compliance_msg": compliance_result["msg"]
        }

    def _validate_validity(self, content: str) -> dict:
        """
        执行有效性校验：空内容、最小长度、字符重复率、连续复读短语

        Args:
            content: 待校验文本
        Returns:
            dict: 校验结果，包含pass标记与msg说明
        """
        if not content or not content.strip():
            return {"pass": False, "msg": ErrorCode.VALID_EMPTY_CONTENT.msg}
        
        content = content.strip()
        if len(content) < self.min_length:
            return {
                    "pass": False, 
                    "msg": f"{ErrorCode.VALID_LENGTH_NOT_ENOUGH.msg}，仅{len(content)}字,低于阈值:{self.min_length}字"
                }
        
        # 单字重复率统计
        char_count = {}
        for char in content:
            char_count[char] = char_count.get(char, 0) + 1
        max_count = max(char_count.values())
        repeat_rate = max_count / len(content)
        if repeat_rate > self.max_repeat_rate:
            return {
                    "pass": False, 
                    "msg": f"{ErrorCode.VALID_HIGH_REPEAT.msg}：{repeat_rate:.2f}，高于阈值：{self.max_repeat_rate}"
                }
        # 连续短语复读检测，补充单字符重复率的覆盖盲区
        continuous_result = self._check_continuous_phrase_repeat(content)
        if not continuous_result["pass"]:
            return continuous_result
        return {"pass": True, "msg": "有效性校验通过"}

    def _check_continuous_phrase_repeat(self, content: str) -> dict:
        """
        检测连续短语复读，补充单字符重复率的覆盖盲区

        原理：滑动窗口截取不同长度的子串，统计同一子串连续出现的最大次数

        Args:
            content: 待校验文本
        Returns:
            dict: 检测结果，包含pass标记与msg说明
        """
        content_len = len(content)
        max_repeat_times = 0
        hit_phrase = ""
        # 遍历不同短语长度
        for phrase_len in range(self.repeat_phrase_min_len, self.repeat_phrase_max_len + 1):
            if content_len < phrase_len * 2:
                continue  # 文本长度不足，跳过该长度
            i = 0
            while i <= content_len - phrase_len:
                current_phrase = content[i:i + phrase_len]
                repeat_times = 1
                # 向后匹配连续重复的相同短语
                j = i + phrase_len
                while j <= content_len - phrase_len and content[j:j + phrase_len] == current_phrase:
                    repeat_times += 1
                    j += phrase_len
                if repeat_times > max_repeat_times:
                    max_repeat_times = repeat_times
                    hit_phrase = current_phrase
                i = j  # 跳过已匹配的重复部分
        if max_repeat_times > self.max_continuous_repeat:
            return {
                "pass": False,
                "msg": f"{ErrorCode.VALID_HIGH_REPEAT.msg}：短语「{hit_phrase}」连续重复{max_repeat_times}次，超过阈值：{self.max_continuous_repeat}次"
            }
        return {"pass": True, "msg": "重复率校验通过"}

    def _validate_compliance(self, content: str) -> dict:
        """
        执行合规性校验：敏感词匹配检测

        Args:
            content: 待校验文本
        Returns:
            dict: 校验结果，包含pass标记与msg说明
        """
        if not self.sensitive_words:
            return{"pass": True, "msg": "未配置敏感词库，跳过合规性校验"}
        hit_words = []
        for word in self.sensitive_words:
            if word in content:
                hit_words.append(word)
        
        if hit_words:
            return {
                    "pass": False, 
                    "msg": f"{ErrorCode.COMPLIANCE_SENSITIVE_WORD.msg}：{','.join(hit_words)}"
                }
        return {"pass": True, "msg": "合规性校验通过"}

# ========== 线程安全单例实现 ==========
_response_validator_instance = None
_validator_lock = threading.Lock()
def __getattr__(name):
    """模块级属性访问拦截，实现懒加载单例"""
    if name == "response_validator":
        global _response_validator_instance
        if not _response_validator_instance:
            with _validator_lock:
                if not _response_validator_instance:
                    _response_validator_instance = ResponseValidator()
        return _response_validator_instance
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")