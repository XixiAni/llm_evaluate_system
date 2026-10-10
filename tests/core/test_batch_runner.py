import pytest
from unittest.mock import patch, Mock
from core.batch_runner import BatchEvalRunner
from common.error_code import ErrorCode

@pytest.fixture
def mock_llm_client():
    """模拟主LLM客户端，返回固定成功结果"""
    client = Mock()
    # 给模拟的 chat 方法设置固定返回值
    client.chat.return_value = {
        "code": 0,
        "data": "测试回答内容",
        "msg": "执行成功",
        "cost_ms": 100
    }
    return client

@pytest.fixture
def mock_judge_client():
    """模拟Judge-LLM客户端，返回成功结果"""
    client = Mock()
    client.chat.return_value = {
        "code": 0,
        "data": '{"level": 0, "reason": "无幻觉"}',
        "msg": "执行成功",
        "cost_ms": 150
    }
    return client

def test_batch_run_normal_order(mock_llm_client):
    """正向：批量执行正常，结果顺序与输入一致"""
    runner = BatchEvalRunner(llm_client=mock_llm_client, concurrent_num=1)
    case_list = [
        {"case_id": "case01", "prompt": "问题1", "expect_keywords": [], "standard_answer": ""},
        {"case_id": "case02", "prompt": "问题2", "expect_keywords": [], "standard_answer": ""},
        {"case_id": "case03", "prompt": "问题3", "expect_keywords": [], "standard_answer": ""}
    ]

    result = runner.run_batch_cases(case_list)

    assert len(result) == 3
    # 验证顺序严格一致
    assert result[0]["case_id"] == "case01"
    assert result[1]["case_id"] == "case02"
    assert result[2]["case_id"] == "case03"
    # 验证全部执行成功
    assert all(item["success_flag"] for item in result)


def test_single_case_exception_isolated(mock_llm_client):
    """正向：单条用例异常，不影响其他用例（异常隔离）"""
    # 第一条正常，第二条抛异常，第三条正常
    def side_effect(prompt):
        if prompt == "异常问题":
            raise Exception("模拟调用异常")
        return {
            "code": 0,
            "data": "正常回答",
            "msg": "执行成功",
            "cost_ms": 100
        }
    mock_llm_client.chat.side_effect = side_effect
    
    runner = BatchEvalRunner(llm_client=mock_llm_client, concurrent_num=1)
    case_list = [
        {"case_id": "case01", "prompt": "正常问题1", "expect_keywords": [], "standard_answer": ""},
        {"case_id": "case02", "prompt": "异常问题", "expect_keywords": [], "standard_answer": ""},
        {"case_id": "case03", "prompt": "正常问题2", "expect_keywords": [], "standard_answer": ""}
    ]
    
    result = runner.run_batch_cases(case_list)
    
    assert len(result) == 3
    assert result[0]["success_flag"] is True
    assert result[1]["success_flag"] is False  # 异常用例标记失败
    assert "执行异常" in result[1]["error_msg"]
    assert result[2]["success_flag"] is True  # 后续用例不受影响
    assert [item["case_id"] for item in result] == ["case01", "case02", "case03"]

def test_judge_llm_enable_call(mock_llm_client, mock_judge_client):
    """正向：Judge-LLM开启时，调用评判链路"""
    runner = BatchEvalRunner(
        llm_client=mock_llm_client,
        concurrent_num=1,
        judge_llm_client=mock_judge_client
    )
    case_list = [
        {"case_id": "case01", "prompt": "问题", "expect_keywords": [], "standard_answer": "标准答案"}
    ]
    
    result = runner.run_batch_cases(case_list)
    
    assert mock_judge_client.chat.called
    assert result[0]["judge_llm_status"] == "success"
    assert result[0]["hallucination_level"] == "无"


def test_judge_llm_disable_no_call(mock_llm_client):
    """正向：Judge-LLM关闭时，不调用评判链路"""
    runner = BatchEvalRunner(llm_client=mock_llm_client, concurrent_num=1)
    case_list = [
        {"case_id": "case01", "prompt": "问题", "expect_keywords": [], "standard_answer": "标准答案"}
    ]
    
    result = runner.run_batch_cases(case_list)
    
    assert result[0]["judge_llm_status"] == "disabled"


def test_empty_case_list(mock_llm_client):
    """边界：空用例列表，返回空结果"""
    runner = BatchEvalRunner(llm_client=mock_llm_client, concurrent_num=1)
    result = runner.run_batch_cases([])
    assert len(result) == 0
