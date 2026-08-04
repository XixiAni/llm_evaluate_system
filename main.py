import os
import time
from typing import List, Dict, Any
from dotenv import load_dotenv

# 定位根目录加载.env，不受终端工作目录影响
current_script_abs_path = os.path.abspath(__file__)
current_dir = os.path.dirname(current_script_abs_path)
env_path = os.path.join(current_dir, ".env")
load_dotenv(dotenv_path=env_path)

from common.yaml_reader import YamlReader
from core.llm_client import LLMClient
from core.batch_runner import BatchEvalRunner
from report.reporter import EvalReporter

if __name__ == "__main__":
    # 1. 读取基础配置，初始化LLM客户端
    base_url = YamlReader.get("config.yaml", "llm.base_url")
    timeout = YamlReader.get("config.yaml", "llm.timeout")
    max_retry = YamlReader.get("config.yaml", "llm.max_retry")

    # 2. 初始化大模型客户端
    llm_client = LLMClient(base_url=base_url, timeout=timeout, max_retry=max_retry)

    # 3. 加载评测用例集
    case_list = YamlReader.get_test_data("eval_cases.yaml", "eval_case_list")
    if not case_list:
        print("无可用评测用例，程序退出")
        exit(0)

    # 4. 执行批量评测
    eval_runner = BatchEvalRunner(llm_client=llm_client)
    start_time = time.time()
    result_list = eval_runner.run_batch_cases(case_list=case_list)
    total_time = round(time.time() - start_time, 2)

    # 5. 统计汇总指标
    total = len(result_list)
    success_list = [item for item in result_list if item["success_flag"]]
    success = len(success_list)
    failed_count = total - success
    # 得分统计
    if success > 0:
        avg_total = round(sum(item["total_score"] for item in success_list) / success, 2)
        avg_relevance = round(sum(item["relevance_score"] for item in success_list) / success, 2)
        avg_completeness = round(sum(item["completeness_score"] for item in success_list) / success, 2)
    else:
        avg_total = avg_relevance = avg_completeness = "N/A(用例全部调用失败)"

    # 幻觉分布统计
    hallucination_levels = [item["hallucination_level"] for item in success_list]
    hallucination_none = hallucination_levels.count("无")
    hallucination_low = hallucination_levels.count("低")
    hallucination_medium = hallucination_levels.count("中")
    hallucination_high = hallucination_levels.count("高")
    hallucination_unknown = hallucination_levels.count("未知")

    # 校验通过率
    valid_pass = sum(1 for item in success_list if item["is_valid"])
    compliant_pass = sum(1 for item in success_list if item["is_compliant"])

    # 6. 控制台格式化输出
    # 预处理百分比
    if success > 0:
        pct_hall_none   = f"{hallucination_none / success * 100:.2f}%"
        pct_hall_low    = f"{hallucination_low / success * 100:.2f}%"
        pct_hall_medium = f"{hallucination_medium / success * 100:.2f}%"
        pct_hall_high   = f"{hallucination_high / success * 100:.2f}%"
        pct_hall_unknown= f"{hallucination_unknown / success * 100:.2f}%"
        pct_valid       = f"{valid_pass / success * 100:.2f}%"
        pct_compliant   = f"{compliant_pass / success * 100:.2f}%"
    else:
        pct_hall_none = pct_hall_low = pct_hall_medium = pct_hall_high = pct_hall_unknown = "N/A(用例全部调用失败)"
        pct_valid = pct_compliant = "N/A(用例全部调用失败)"

    print("\n" + "="*60)
    print("【批量评测汇总结果】")
    print("="*60)

    print(f"总用例数：{total} | 成功：{success}条 | 失败：{failed_count}条")
    print(f"调用成功率：{success / total*100:.2f}%" if total > 0 else "调用成功率：0%")

    print(f"总耗时：{total_time}s | 单条平均耗时：{round(total_time / total, 2)}s/条" if total > 0 else "未传入用例，请检查yaml配置文件")

    print("-"*60)

    print("【得分统计】")
    print(f"平均总分：{avg_total} | 平均相关性得分：{avg_relevance} | 平均完整度得分：{avg_completeness}")

    print("-"*60)

    print(f"【幻觉风险分布】")
    print(f"无风险：{hallucination_none} 条 {pct_hall_none}")
    print(f"低风险：{hallucination_low} 条 {pct_hall_low}")
    print(f"中风险：{hallucination_medium} 条 {pct_hall_medium}")
    print(f"高风险：{hallucination_high} 条 {pct_hall_high}")
    print(f"未知风险：{hallucination_unknown} 条 {pct_hall_unknown}")
    print("-"*60)

    print("【校验通过率】")
    print(f"有效性通过率：{pct_valid}")
    print(f"合规性通过率：{pct_compliant}")

    print("="*60)

    # 6. 导出CSV报告
    reporter = EvalReporter(result_list)
    reporter.export_csv()
