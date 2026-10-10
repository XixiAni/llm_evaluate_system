import os
import csv
from report.reporter import EvalReporter

def test_export_csv_success(tmp_path):
    """正向：导出CSV文件成功，文件存在且字段完整"""
    result_list = [
        {
            "case_id": "case01",
            "case_desc": "测试用例1",
            "execute_timestamp": "2026-10-09 10:00:00",
            "api_cost_ms": 100,
            "judge_api_cost_ms": 0,
            "compute_cost_ms": 50,
            "request_cost_ms": 150,
            "success_flag": True,
            "error_msg": "",
            "is_valid": True,
            "is_compliant": True,
            "validity_msg": "通过",
            "compliance_msg": "通过",
            "total_score": 90.0,
            "relevance_score": 95.0,
            "completeness_score": 85.0,
            "hallucination_level": "无",
            "hallucination_msg": "无风险",
            "judge_llm_status": "disabled",
            "judge_llm_err": "",
            "judge_raw_resp": "",
            "answer_content": "测试回答"
        }
    ]

    # 临时目录导出
    output_path = str(tmp_path)
    reporter = EvalReporter(result_list)
    reporter.export_dir = output_path  # 直接修改实例属性，指定输出到临时目录
    file_path = reporter.export_csv(filename="test_report.csv")

    # 验证文件存在
    assert os.path.exists(file_path)

    # 验证CSV内容
    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["case_id"] == "case01"
        assert rows[0]["total_score"] == "90.0"

        expected_headers = [
            "case_id", "case_desc", "execute_timestamp",
            "api_cost_ms", "judge_api_cost_ms", "compute_cost_ms", "request_cost_ms",
            "success_flag", "error_msg",
            "is_valid", "is_compliant", "validity_msg", "compliance_msg",
            "total_score", "relevance_score", "completeness_score",
            "hallucination_level", "hallucination_msg",
            "judge_llm_status", "judge_llm_err", "judge_raw_resp",
            "answer_content"
        ]
        assert list(rows[0].keys()) == expected_headers

def test_export_custom_filename(tmp_path):
    """正向：自定义文件名导出正常"""
    result_list = []
    output_path = str(tmp_path)
    reporter = EvalReporter(result_list)
    reporter.export_dir = output_path
    file_path = reporter.export_csv(filename="custom_name.csv")

    assert os.path.exists(file_path)
    assert "custom_name.csv" in file_path

def test_empty_result_export(tmp_path):
    """边界：空结果列表也能正常导出，不报错"""
    result_list = []
    output_path = str(tmp_path)
    reporter = EvalReporter(result_list)
    reporter.export_dir = output_path
    file_path = reporter.export_csv()

    assert os.path.exists(file_path)
