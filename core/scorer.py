import jieba
from common.logger import get_logger
from common.yaml_reader import YamlReader
from common.error_code import ErrorCode
import re

# 模块级预热：传入非空中文内容，触发词典加载，消除首次调用冷启动开销
jieba.lcut("分词模块预热")

logger = get_logger("scorer")

# 模块级全局单例：仅初始化一次
# 中文停用词集合，用于降低基于规则的幻觉检测误判率
STOP_WORDS = frozenset({
    # 基础助词、语气词
    "的", "地", "得", "了", "着", "过", "啊", "吗", "呢", "吧", "嗯", "哦", "噢",
    # 单字系动词、指代、简单连词
    "是", "系", "在", "这", "那", "有", "和", "与", "也", "等",
    "就", "都", "而", "还", "还要", "还会",
    # 逻辑转折、基础动作虚词
    "但", "可以", "能够", "进行", "通过", "使用", "一个", "一种",
    # 人称、指代短语
    "我们", "你们", "他们", "它们", "这个", "那个", "这些", "那些",
    # 极简因果/假设连词（双字，无歧义）
    "因此", "所以", "因为", "由于", "如果", "假如", "虽然", "尽管", "不仅",
    "并且", "同时", "以及", "等等", "之类", "来说", "而言", "一下", "一点",
    # 程度副词，无专业歧义
    "很", "非常", "十分", "比较", "相当", "稍微", "几乎", "差不多", "大概", "大约"
})

# 预编译正则：匹配纯数字、纯标点
_PUNCT_NUM_PATTERN = re.compile(r'^[\d\W_]+$')

class AnswerScorer:
    """
    大模型回答评分与幻觉检测模块

    基于关键词匹配、长度重合度、规则差集实现多维度量化打分与幻觉风险识别。

    支持中文分词停用词过滤、白名单豁免、数量+占比双维度风险判定，阈值与权重可通过配置文件灵活调整。
    """
    
    def __init__(self):
        """
        初始化评分器，从配置加载各维度权重与幻觉检测阈值，缺失则使用默认值
        """
        rules = YamlReader.read_file("eval_rules.yaml")
        weight_config = rules.get("score_weight", {})
        hallucination_config = rules.get("hallucination", {})
        # 打分权重
        self.weight = {
            "relevance": weight_config.get("relevance", 0.4),
            "completeness": weight_config.get("completeness", 0.3),
            "compliance": weight_config.get("compliance", 0.3),
        }

        # 幻觉检测阈值
        self.low_risk_threshold = hallucination_config.get("low_risk_threshold", 3)
        self.high_risk_threshold = hallucination_config.get("high_risk_threshold", 6)
        self.extra_ratio_threshold = hallucination_config.get("extra_ratio_threshold", 0.3)

        # 读取白名单，转为集合，提升查找性能
        self.hallucination_whitelist = frozenset(hallucination_config.get("whitelist", []))

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
        hallucination_result = self._check_hallucination(content, standard_answer)  # 幻觉检测结果

        # 第二步：加权计算总分
        # 合规性得分映射：无风险100分，低风险60分，中风险40分，高风险20分，未知80分
        compliance_score_map = {"无": 100, "低": 60, "中": 40, "高": 20, "未知": 80}
        compliance_score = compliance_score_map.get(hallucination_result["level"],80)
        total_score = round(
            # 相关性得分 × 相关性权重
            relevance_score * self.weight["relevance"] +
            # 完整度得分 × 完整度权重
            completeness_score * self.weight["completeness"] +
            # 幻觉等级对应分数 × 合规权重
            compliance_score * self.weight["compliance"],
            2  # 保留2位小数
        )

        # 第三步：统一返回所有结果
        return {
            "total_score": total_score,
            "relevance_score": relevance_score,
            "completeness_score": completeness_score,
            "hallucination_level": hallucination_result["level"],
            "hallucination_msg": hallucination_result["msg"]
        }

    def _calc_relevance_score(self, content: str, keywords: list) -> float:
        """
        计算相关性得分：基于分词清洗后的实词匹配关键词，命中占比0-100分

        Args:
            content: 回答文本
            keywords: 预期关键词列表
        Returns:
            float: 相关性得分，0-100
        """
        if not content.strip():
            return 0.0
        # 边界处理：如果没传关键词，直接给满分（无评判标准）
        if not keywords:
            return 100.0

    # 分词清洗，得到回答实词
        ans_words = self._tokenize(content)
        hit_count = 0
        for kw in keywords:
            # 关键词分词清洗，避免虚词干扰匹配
            kw_words = self._tokenize(kw)
            if not kw_words:
                # 关键词分词无有效实词，降级原始字符串匹配兜底
                if kw in content:
                    hit_count += 1
                continue
            # 关键词所有核心实词全部存在回答中才算命中
            all_in = all(word in ans_words for word in kw_words)
            if all_in:
                hit_count += 1
        return round(hit_count / len(keywords) * 100, 2)
    def _calc_completeness_score(self, content: str, standard: str) -> float:
        """
        计算完整度得分：实词数量占比40% + 实词集合重合度60%

        统一使用分词过滤停用词，仅对比承载事实的业务实词，规避虚词干扰
        Args:
            content: 回答文本
            standard: 标准答案文本
        Returns:
            float: 完整度得分，0-100
        """
        if not content.strip():
            return 0.0
        # 边界处理：没有标准答案，默认给80分
        if not standard.strip():
            return 80.0

        std_words = self._tokenize(standard)
        ans_words = self._tokenize(content)

        if not std_words:
            return 80.0
        
        # 维度1：实词数量占比，上限1.0
        len_ratio = min(len(ans_words) / len(std_words), 1.0)
        
        # 维度2：实词交集重合度
        common_words = ans_words & std_words
        common_ratio = len(common_words) / len(std_words)
        return round((len_ratio * 0.4 + common_ratio * 0.6) * 100, 2)

    @staticmethod
    def _tokenize(text:str) -> set:
        """
        文本分词并过滤无效词，自动识别中英文并选择对应分词策略。

        过滤规则： 剔除单字词、停用词、空白字符、纯数字、纯标点等无效词
        
        Args:
            text: 待分词的原始文本。
        Returns:
            set: 去重后的词语集合
        """
        # 判断是否包含中文字符
        has_chinese = any("\u4e00" <= char <= "\u9fff" for char in text)
        if has_chinese:
            words = jieba.lcut(text)
        else:
            words = text.split()

        valid_words = set()
        for word in words:
            word = word.strip()
            # 过滤：空值、单字词、停用词、纯数字、纯标点
            if (not word 
                or len(word) < 2 
                or word in STOP_WORDS 
                or _PUNCT_NUM_PATTERN.match(word)):
                continue
            valid_words.add(word)
        return valid_words

    def _check_hallucination(self, content: str, standard: str) -> dict:
        """
        基于规则的幻觉检测：比对回答与标准答案的 实词 差集，统计新增词汇

        Args:
            content: 回答文本
            standard: 标准答案文本
        Returns:
            dict: 检测结果
                - level: 风险等级：无/低/中/高/未知
                - msg: 检测说明
                - code: 异常场景错误码，仅未知等级携带
        """
        if not content or not content.strip():
            return {"level": "无", "msg": "回答内容为空，无幻觉风险"}
        # 边界处理：无标准答案，无法检测，标记未知（业务异常分支，携带错误码）
        if not standard or not standard.strip():
            return {"level": "未知",
                    "code": ErrorCode.NO_STANDARD_ANSWER.code,
                    "msg": ErrorCode.NO_STANDARD_ANSWER.msg
                }
        
        # 按空格分词，转成集合（去重）
        std_words = self._tokenize(standard)   # 标准答案的词集合
        ans_words = self._tokenize(content)    # 模型回答的词集合
        
        # 差集运算：排除回答中的标准答案词和白名单词 → 疑似新增事实
        extra_words = ans_words - std_words - self.hallucination_whitelist
        extra_count = len(extra_words)
        ans_total = len(ans_words)
        extra_ratio = extra_count / ans_total if ans_total > 0 else 0.0

        # 按新增词数量划分风险等级
        if extra_count == 0:
            return {"level": "无", "msg": "未检测到疑似幻觉内容"}

        # 双维度判定：占比未达标时，直接判定为低风险
        if extra_ratio < self.extra_ratio_threshold:
            sample = ",".join(list(extra_words)[:3])
            return {"level": "低", "msg": f"疑似新增事实点{extra_count}个（占比{extra_ratio:.1%}）：{sample}"}
        
        if extra_count <= self.low_risk_threshold:
            sample = ",".join(list(extra_words)[:3])
            return {"level": "低", "msg": f"疑似新增事实点{extra_count}个（占比{extra_ratio:.1%}）：{sample}"}
        
        elif extra_count <= self.high_risk_threshold:
            sample = ",".join(list(extra_words)[:5])
            return {"level": "中", "msg": f"存在较多未核实内容，共{extra_count}个（占比{extra_ratio:.1%}）：{sample}"}
        
        else:  
            sample = ",".join(list(extra_words)[:5])
            return {"level": "高", "msg": f"存在大量未核实内容，共{extra_count}个（占比{extra_ratio:.1%}），高幻觉风险：{sample}"}

# 模块级单例：全局唯一实例，全程仅初始化一次
answer_scorer = AnswerScorer()
