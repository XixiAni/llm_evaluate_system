import os
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
        print("无可用评测用例")
        exit(0)

    # 4. 执行批量评测
    eval_runner = BatchEvalRunner(llm_client=llm_client)
    result_list = eval_runner.run_batch_cases(case_list=case_list)

    # 5. 统计汇总指标
    total = len(result_list)
    success = sum(1 for item in result_list if item["success_flag"])
    avg_score = round(sum(item["total_score"] for item in result_list if item["success_flag"]) / success, 2) if success > 0 else 0
    hallucination_high = sum(1 for item in result_list if item["hallucination_level"] == "高")

    print("\n" + "="*60)
    print("【批量评测汇总结果】")
    print(f"总用例数：{total}")
    print(f"成功用例：{success}")
    print(f"失败用例：{total - success}")
    print(f"调用成功率：{success/total*100:.2f}%" if total > 0 else "调用成功率：0%")
    print(f"平均总分：{avg_score}")
    print(f"高幻觉风险用例数：{hallucination_high}")
    print("="*60)

    # 6. 导出CSV报告
    reporter = EvalReporter(result_list)
    reporter.export_csv()
