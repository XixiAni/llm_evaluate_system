from common.logger import get_logger
from common.yaml_reader import YamlReader

logger = get_logger("scorer")

class AnswerScorer:
    def __init__(self):
        rules = YamlReader.read_file("eval_rules.yaml")
        self.weight = rules["score_weight"]

    def score_answer(self, content: str, expect_keywords: list, standard_answer: str) -> dict:
        """多维打分 + 幻觉风险检测"""
        relevance_score = self._calc_relevance_score(content, expect_keywords)
        completeness_score = self._calc_completeness_score(content, standard_answer)
        hallucination_risk = self._check_hallucination(content, standard_answer)

        # 加权计算总分，纯算术运算
        total_score = round(
            relevance_score * self.weight["relevance"] +
            completeness_score * self.weight["completeness"] +
            (100 if hallucination_risk["level"] == "无" else 60 if hallucination_risk["level"] == "低" else 20) * self.weight["compliance"],
            2
        )

        return {
            "total_score": total_score,
            "relevance_score": relevance_score,
            "completeness_score": completeness_score,
            "hallucination_level": hallucination_risk["level"],
            "hallucination_msg": hallucination_risk["msg"]
        }

    def _calc_relevance_score(self, content: str, keywords: list) -> float:
        """相关性得分：关键词匹配率，逻辑同断言包含"""
        if not keywords:
            return 100.0
        hit_count = 0
        for kw in keywords:
            if kw in content:
                hit_count += 1
        return round(hit_count / len(keywords) * 100, 2)

    def _calc_completeness_score(self, content: str, standard: str) -> float:
        """完整度得分：长度占比 + 字符重合度"""
        if not standard:
            return 80.0
        len_ratio = min(len(content) / len(standard), 1.0)
        common_chars = len(set(content) & set(standard)) / len(set(standard)) if len(set(standard)) > 0 else 0
        return round((len_ratio * 0.4 + common_chars * 0.6) * 100, 2)

    def _check_hallucination(self, content: str, standard: str) -> dict:
        """规则版幻觉检测：反向比对回答超出标准答案的内容"""
        if not standard:
            return {"level": "未知", "msg": "无标准答案，无法检测"}
        
        std_words = set(standard.split())
        ans_words = set(content.split())
        extra_words = ans_words - std_words
        extra_words = {w for w in extra_words if len(w) >= 2}

        if not extra_words:
            return {"level": "无", "msg": "未检测到疑似幻觉内容"}
        elif len(extra_words) <= 3:
            return {"level": "低", "msg": f"疑似新增事实点：{','.join(list(extra_words)[:3])}"}
        else:
            return {"level": "高", "msg": f"存在大量未核实内容，疑似幻觉点较多"}
