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
from core.statistics import EvalStatistics
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

    # 4. 初始化批量执行器，读取并发配置
    concurrent_num = YamlReader.get("config.yaml", "eval.concurrent_num", 1)
    
    # 5. 执行批量评测
    eval_runner = BatchEvalRunner(llm_client=llm_client, concurrent_num=concurrent_num)
    start_time = time.time()
    result_list = eval_runner.run_batch_cases(case_list=case_list)
    total_time = round(time.time() - start_time, 2)

    # 6. 统计汇总 + 控制台输出
    statistics = EvalStatistics(result_list, total_time)
    statistics.print_summary()

    # 7. 导出CSV报告
    reporter = EvalReporter(result_list)
    reporter.export_csv()
