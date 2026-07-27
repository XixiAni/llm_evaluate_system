from common.logger import get_logger
from common.yaml_reader import YamlReader

logger = get_logger("validator")

class ResponseValidator:
    """
    大模型响应内容校验器
    包含两个维度：有效性校验（空内容、长度不足、高重复）、合规性校验（敏感词匹配）
    所有校验规则从eval_rules.yaml配置读取，无需修改代码
    """
    def __init__(self):
        """
        初始化校验器，从配置文件加载敏感词库与有效性校验阈值
        """
        rules = YamlReader.read_file("eval_rules.yaml")
        self.sensitive_words = rules.get("sensitive_words", [])
        self.min_length = rules["validity"]["min_length"]
        self.max_repeat_rate = rules["validity"]["max_repeat_rate"]

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
        执行有效性校验：空内容、最小长度、字符重复率
        Args:
            content: 待校验文本
        Returns:
            dict: 校验结果，包含pass标记与msg说明
        """
        if not content or not content.strip():
            return {"pass": False, "msg": "回答为空"}
        
        content = content.strip()
        if len(content) < self.min_length:
            return {"pass": False, "msg": f"回答长度不足，仅{len(content)}字"}
        
        # 重复率统计
        char_count = {}
        for char in content:
            char_count[char] = char_count.get(char, 0) + 1
        max_count = max(char_count.values())
        repeat_rate = max_count / len(content)
        if repeat_rate > self.max_repeat_rate:
            return {"pass": False, "msg": f"回答重复度过高，重复率{repeat_rate:.2f}"}
        
        return {"pass": True, "msg": "有效性校验通过"}

    def _validate_compliance(self, content: str) -> dict:
        """
        执行合规性校验：敏感词匹配检测
        Args:
            content: 待校验文本
        Returns:
            dict: 校验结果，包含pass标记与msg说明
        """
        hit_words = []
        for word in self.sensitive_words:
            if word in content:
                hit_words.append(word)
        
        if hit_words:
            return {"pass": False, "msg": f"检测到敏感词：{','.join(hit_words)}"}
        
        return {"pass": True, "msg": "合规性校验通过"}
