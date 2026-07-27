from common.logger import get_logger
from common.yaml_reader import YamlReader

logger = get_logger("scorer")

class AnswerScorer:
    """
    大模型回答评分与幻觉检测模块
    评分维度：相关性（关键词命中）、完整度（长度+字符重合度）、合规性
    幻觉检测：基于标准答案的差集比对，标记新增事实点风险
    权重从配置文件读取，可灵活调整
    """
    def __init__(self):
        """
        初始化评分器，从配置加载各维度权重
        """
        rules = YamlReader.read_file("eval_rules.yaml")
        self.weight = rules["score_weight"]

    def score_answer(self, content: str, expect_keywords: list, standard_answer: str) -> dict:
        """
        执行多维评分与幻觉检测

        Args:
            content: 大模型回答文本
            expect_keywords: 预期关键词列表
            standard_answer: 标准答案文本
        Returns:
            dict: 评分结果
                - total_score: 加权总分
                - relevance_score: 相关性得分
                - completeness_score: 完整度得分
                - hallucination_level: 幻觉风险等级
                - hallucination_msg: 幻觉检测说明
        """
        # 第一步：分别计算三个维度的结果
        relevance_score = self._calc_relevance_score(content, expect_keywords)  # 相关性得分
        completeness_score = self._calc_completeness_score(content, standard_answer)  # 完整度得分
        hallucination_risk = self._check_hallucination(content, standard_answer)  # 幻觉检测结果

        # 第二步：加权计算总分
        total_score = round(
            # 相关性得分 × 相关性权重
            relevance_score * self.weight["relevance"] +
            # 完整度得分 × 完整度权重
            completeness_score * self.weight["completeness"] +
            # 幻觉等级对应分数 × 合规权重
            (100 if hallucination_risk["level"] == "无" else 60 if hallucination_risk["level"] == "低" else 20) * self.weight["compliance"],
            2  # 保留2位小数
        )

        # 第三步：统一返回所有结果
        return {
            "total_score": total_score,
            "relevance_score": relevance_score,
            "completeness_score": completeness_score,
            "hallucination_level": hallucination_risk["level"],
            "hallucination_msg": hallucination_risk["msg"]
        }

    def _calc_relevance_score(self, content: str, keywords: list) -> float:
        """
        计算相关性得分：命中关键词占总关键词的比例，满分100
        Args:
            content: 回答文本
            keywords: 预期关键词列表
        Returns:
            float: 相关性得分，0-100
        """
        # 边界处理：如果没传关键词，直接给满分（无评判标准）
        if not keywords:
            return 100.0
        
        hit_count = 0
        # 遍历所有预期关键词，统计命中数量
        for kw in keywords:
            if kw in content:
                hit_count += 1
        
        return round(hit_count / len(keywords) * 100, 2)

    def _calc_completeness_score(self, content: str, standard: str) -> float:
        """
        计算完整度得分：长度占比40% + 字符重合度60%，满分100
        Args:
            content: 回答文本
            standard: 标准答案文本
        Returns:
            float: 完整度得分，0-100
        """
        # 边界处理：没有标准答案，默认给80分
        if not standard:
            return 80.0
        
        # 维度1：长度占比 = 回答长度 / 标准答案长度，最高1.0（超过标准答案长度也按1算）
        len_ratio = min(len(content) / len(standard), 1.0)
        
        # 维度2：字符重合度
        # set(content)：把回答拆成单个字符的集合（去重）
        # set(standard)：把标准答案拆成单个字符的集合
        # & ：取交集，也就是两边都有的字符
        # 重合度 = 共同字符数 / 标准答案总字符数
        common_chars = len(set(content) & set(standard)) / len(set(standard)) if len(set(standard)) > 0 else 0
        
        return round((len_ratio * 0.4 + common_chars * 0.6) * 100, 2)

    def _check_hallucination(self, content: str, standard: str) -> dict:
        """
        规则版幻觉检测：比对回答与标准答案的分词差集，统计新增词汇
        Args:
            content: 回答文本
            standard: 标准答案文本
        Returns:
            dict: 检测结果
                - level: 风险等级：无/低/高/未知
                - msg: 检测说明
        """
        # 边界处理：无标准答案，无法检测，标记未知
        if not standard:
            return {"level": "未知", "msg": "无标准答案，无法检测"}
        
        # 按空格分词，转成集合（去重）
        std_words = set(standard.split())   # 标准答案的词集合
        ans_words = set(content.split())    # 模型回答的词集合
        
        # 差集运算：回答里有、但标准答案里没有的词 → 疑似新增事实
        extra_words = ans_words - std_words
        # 过滤掉单字（减少语气词、标点的误判）
        extra_words = {w for w in extra_words if len(w) >= 2}
        # 按新增词数量划分风险等级
        if not extra_words:
            return {"level": "无", "msg": "未检测到疑似幻觉内容"}
        elif len(extra_words) <= 3:
            return {"level": "低", "msg": f"疑似新增事实点：{','.join(list(extra_words)[:3])}"}
        else:
            return {"level": "高", "msg": f"存在大量未核实内容，疑似幻觉点较多"}
