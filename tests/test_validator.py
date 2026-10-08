import pytest
from core.validator import ResponseValidator

@pytest.fixture
def validator():
    return ResponseValidator()

def test_valid_empty_content(validator):
    """反向：空内容校验不通过"""
    result = validator._validate_validity("")
    assert result["pass"] is False

def test_valid_length_not_enough(validator):
    """反向：内容长度不足"""
    validator.min_length = 10
    result = validator._validate_validity("短文本")
    assert result["pass"] is False
    assert "长度不足" in result["msg"]

def test_valid_high_repeat_char(validator):
    """反向：单字符高重复"""
    result = validator._validate_validity("aaaaaaaaaaaaaaa")
    assert result["pass"] is False
    assert "重复率过高" in result["msg"]

def test_valid_continuous_phrase_repeat(validator):
    """反向：连续短语复读"""
    result = validator._validate_validity("我知道我知道我知道我知道")
    assert result["pass"] is False
    assert "连续重复" in result["msg"]

def test_valid_normal_content(validator):
    """正向：正常内容校验通过"""
    result = validator._validate_validity("这是一段正常的回答内容，信息完整逻辑通顺。")
    assert result["pass"] is True
