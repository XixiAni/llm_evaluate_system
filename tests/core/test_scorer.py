import pytest
from core.scorer import AnswerScorer

@pytest.fixture
def scorer():
    return AnswerScorer()

def test_relevance_score_full_hit(scorer):
    """正向：关键词全部命中，相关性满分"""
    score = scorer._calc_relevance_score("人工智能是计算机科学的分支", ["人工智能", "计算机科学"])
    assert score == 100.0

def test_relevance_score_partial(scorer):
    """正向：关键词部分命中"""
    score = scorer._calc_relevance_score("人工智能技术发展很快", ["人工智能", "计算机科学"])
    assert 0 < score < 100

def test_completeness_score(scorer):
    """正向：完整度得分计算"""
    std = "人工智能是研究计算机模拟人类智能的技术"
    ans = "人工智能是计算机模拟人类智能的技术"
    score = scorer._calc_completeness_score(ans, std)
    assert 0 < score < 100

def test_hallucination_no_risk(scorer):
    """正向：无幻觉场景"""
    std = "Python是一种编程语言"
    ans = "Python是编程语言"
    result = scorer._check_hallucination(ans, std)
    assert result["level"] == "无"

def test_hallucination_extra_content(scorer):
    """正向：存在新增内容，识别为低风险"""
    std = "Python是编程语言"
    ans = "Python是一种简单易学的编程语言"
    result = scorer._check_hallucination(ans, std)
    assert result["level"] in ["低", "中"]

def test_hallucination_empty_standard(scorer):
    """边界：无标准答案时标记未知"""
    result = scorer._check_hallucination("任意回答", "")
    assert result["level"] == "未知"
