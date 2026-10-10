import pytest
from core.statistics import EvalStatistics

def test_all_success_cases_statistics():
    """正向：全部成功用例，统计指标正确"""
    result_list = [
        {
            "success_flag": True,
            "total_score": 90.0,
            "relevance_score": 95.0,
            "completeness_score": 85.0,
            "hallucination_level": "无",
            "is_valid": True,
            "is_compliant": True,
            "judge_llm_status": "disabled"
        },
        {
            "success_flag": True,
            "total_score": 80.0,
            "relevance_score": 85.0,
            "completeness_score": 75.0,
            "hallucination_level": "低",
            "is_valid": True,
            "is_compliant": False,
            "judge_llm_status": "disabled"
        }
    ]
    stats = EvalStatistics(result_list, total_time=2.0)
    summary = stats.calc_summary()
    
    assert summary["total"] == 2
    assert summary["success"] == 2
    assert summary["success_rate"] == 100.0
    assert summary["avg_score"]["total"] == 85.0
    assert summary["hallucination_dist"]["none"]["count"] == 1
    assert summary["hallucination_dist"]["low"]["count"] == 1
    assert "100.00%" in summary["validate_pass_rate"]["valid"]

def test_all_failed_cases_fallback():
    """边界：全部调用失败，统计兜底不报错"""
    result_list = [
        {"success_flag": False, "error_msg": "超时", "judge_llm_status": "disabled"},
        {"success_flag": False, "error_msg": "连接失败", "judge_llm_status": "disabled"}
    ]
    stats = EvalStatistics(result_list, total_time=1.0)
    summary = stats.calc_summary()
    
    assert summary["total"] == 2
    assert summary["success"] == 0
    assert summary["avg_score"]["total"] == "N/A(用例全部调用失败)"
    assert summary["hallucination_dist"]["none"]["ratio"] == "N/A(用例全部调用失败)"

def test_empty_case_list():
    """边界：空用例列表，统计兜底"""
    stats = EvalStatistics([], total_time=0)
    summary = stats.calc_summary()
    assert summary["total"] == 0
    assert summary["success"] == 0
    assert summary["success_rate"] == 0.0

def test_judge_llm_status_statistics():
    """正向：Judge-LLM链路状态统计正确"""
    result_list = [
        {"success_flag": True, "hallucination_level": "无", "is_valid": True, "is_compliant": True,
         "judge_llm_status": "success", "total_score": 90, "relevance_score": 90, "completeness_score": 90},
        {"success_flag": True, "hallucination_level": "无", "is_valid": True, "is_compliant": True,
         "judge_llm_status": "api_failed", "total_score": 80, "relevance_score": 80, "completeness_score": 80},
        {"success_flag": True, "hallucination_level": "无", "is_valid": True, "is_compliant": True,
         "judge_llm_status": "parse_failed", "total_score": 85, "relevance_score": 85, "completeness_score": 85},
    ]
    stats = EvalStatistics(result_list, total_time=3.0)
    summary = stats.calc_summary()
    
    assert summary["judge_stats"]["enable"] is True
    assert summary["judge_stats"]["total"] == 3
    assert summary["judge_stats"]["success"] == 1
    assert summary["judge_stats"]["api_failed"] == 1
    assert summary["judge_stats"]["parse_failed"] == 1