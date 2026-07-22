from common.logger import get_logger
from common.yaml_reader import YamlReader

logger = get_logger("validator")

class ResponseValidator:
    def __init__(self):
        rules = YamlReader.read_file("eval_rules.yaml")
        self.sensitive_words = rules.get("sensitive_words", [])
        self.min_length = rules["validity"]["min_length"]
        self.max_repeat_rate = rules["validity"]["max_repeat_rate"]

    def validate_all(self, content: str) -> dict:
        """执行全量校验：有效性 + 合规性"""
        validity_result = self._validate_validity(content)
        compliance_result = self._validate_compliance(content)
        
        return {
            "is_valid": validity_result["pass"],
            "is_compliant": compliance_result["pass"],
            "validity_msg": validity_result["msg"],
            "compliance_msg": compliance_result["msg"]
        }

    def _validate_validity(self, content: str) -> dict:
        """有效性校验：空回答、过短、高重复"""
        if not content or not content.strip():
            return {"pass": False, "msg": "回答为空"}
        
        content = content.strip()
        if len(content) < self.min_length:
            return {"pass": False, "msg": f"回答长度不足，仅{len(content)}字"}
        
        # 重复率统计，Python基础字典操作
        char_count = {}
        for char in content:
            char_count[char] = char_count.get(char, 0) + 1
        max_count = max(char_count.values())
        repeat_rate = max_count / len(content)
        if repeat_rate > self.max_repeat_rate:
            return {"pass": False, "msg": f"回答重复度过高，重复率{repeat_rate:.2f}"}
        
        return {"pass": True, "msg": "有效性校验通过"}

    def _validate_compliance(self, content: str) -> dict:
        """合规性校验：敏感词匹配，逻辑同关键词断言"""
        hit_words = []
        for word in self.sensitive_words:
            if word in content:
                hit_words.append(word)
        
        if hit_words:
            return {"pass": False, "msg": f"检测到敏感词：{','.join(hit_words)}"}
        
        return {"pass": True, "msg": "合规性校验通过"}
