import pytest
from common.compliance import ComplianceChecker

@pytest.fixture
def checker():
    """复用校验器实例"""
    return ComplianceChecker()

def test_compliance_pass(checker):
    """正向：正常内容通过校验"""
    result = checker.check("这是一段正常的回答内容")
    assert result["pass"] is True
    assert "通过" in result["msg"]

def test_compliance_hit_sensitive(checker):
    """正向：命中敏感词返回不通过"""
    # 假设敏感词库包含示例敏感词，可根据实际配置调整
    checker.sensitive_words = ["违禁词测试"]
    result = checker.check("这句话包含违禁词测试内容")
    assert result["pass"] is False
    assert "违禁词测试" in result["msg"]

def test_compliance_empty_word_list(checker):
    """边界：未配置敏感词库时自动跳过校验"""
    checker.sensitive_words = []
    result = checker.check("任意内容")
    assert result["pass"] is True
    assert "跳过" in result["msg"]

def test_compliance_empty_content(checker):
    """反向：空内容校验"""
    result = checker.check("")
    assert result["pass"] is True  # 空内容合规性校验不拦截，由有效性模块负责
