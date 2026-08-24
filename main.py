import os
import time
from typing import List, Dict, Any
from dotenv import load_dotenv

# 定位根目录加载.env，不受终端工作目录影响
current_script_abs_path = os.path.abspath(__file__)
current_dir = os.path.dirname(current_script_abs_path)
env_path = os.path.join(current_dir, ".env")
load_dotenv(dotenv_path=env_path)

# 置顶加载配置，fail-fast校验不通过直接终止
from common.config_loader import app_config
from common.yaml_reader import YamlReader
from core.llm_client import LLMClient
from core.batch_runner import BatchEvalRunner
from core.statistics import EvalStatistics
from report.reporter import EvalReporter
from common.sqlite_client import EvalDbClient

if __name__ == "__main__":
    # 1. 初始化主LLM客户端
    llm_client = LLMClient(
        base_url=app_config.llm_base_url,
        timeout=app_config.llm_timeout,
        max_retry=app_config.llm_max_retry
    )
    model_name = app_config.llm_model

    # 2. 初始化Judge-LLM评判客户端（配置开启时生效）
    judge_llm_client = None
    if app_config.judge_llm_enable:
        judge_llm_client = LLMClient(
            base_url=app_config.judge_llm_base_url,
            timeout=app_config.judge_llm_timeout,
            max_retry=app_config.judge_llm_max_retry
        )
    
    # 3. 加载评测用例集
    case_list = YamlReader.get_test_data("eval_cases.yaml", "eval_case_list")
    if not case_list:
        print("无可用评测用例，程序退出")
        exit(0)

    # 3. 初始化批量执行器
    eval_runner = BatchEvalRunner(
        llm_client=llm_client,
        concurrent_num=app_config.eval_concurrent_num,
        judge_llm_client=judge_llm_client
    )

    # 4. 执行批量评测
    start_time = time.time()
    result_list = eval_runner.run_batch_cases(case_list=case_list)
    total_time = round(time.time() - start_time, 2)

    # 5. 统计汇总 + 控制台输出
    statistics = EvalStatistics(result_list, total_time)
    summary = statistics.calc_summary()
    statistics.print_summary()

    # 6. 评测结果持久化
    db_client = EvalDbClient(db_path=app_config.eval_db_path)
    db_client.save_batch_result(result_list, summary, model_name=model_name)

    # 7. 导出CSV报告
    reporter = EvalReporter(result_list)
    reporter.export_csv()
