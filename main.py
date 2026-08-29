import os
import time
import signal
import argparse
from dotenv import load_dotenv

# 定位根目录加载.env，不受终端工作目录影响
current_script_abs_path = os.path.abspath(__file__)
current_dir = os.path.dirname(current_script_abs_path)
env_path = os.path.join(current_dir, ".env")
load_dotenv(dotenv_path=env_path)

# 置顶加载配置，fail-fast校验不通过直接终止
from common.config_loader import app_config
from common.logger import set_trace_id
from common.yaml_reader import YamlReader
from core.llm_client import LLMClient
from core.batch_runner import BatchEvalRunner, request_stop
from core.statistics import EvalStatistics
from report.reporter import EvalReporter
from common.sqlite_client import EvalDbClient

def _signal_handler(signum, frame):
    """SIGINT信号处理器：请求优雅停止批量任务"""
    print("\n📢 收到中断信号，正在安全收尾，请勿重复按Ctrl+C...")
    request_stop()
# 注册中断信号
signal.signal(signal.SIGINT, _signal_handler)

def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="AI大模型自动化评测系统")
    parser.add_argument(
        "--case-file", "-f",
        type=str,
        default="eval_cases.yaml",
        help="评测用例文件名，默认eval_cases.yaml（data目录下）"
    )
    parser.add_argument(
        "--concurrent", "-c",
        type=int,
        default=None,
        help="API并发数，覆盖config.yaml中的eval.concurrent_num配置"
    )
    parser.add_argument(
        "--judge-llm",
        action="store_true",
        default=None,
        help="强制开启Judge-LLM大模型自校验"
    )
    parser.add_argument(
        "--no-judge-llm",
        action="store_true",
        default=None,
        help="强制关闭Judge-LLM大模型自校验"
    )
    parser.add_argument(
        "--batch-tag",
        type=str,
        default="",
        help="批次标签，用于备份文件名、报告名自定义标识"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="CSV报告输出文件名，默认自动生成时间戳文件名"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default=None,
        help="控制台日志级别：debug/info/warning/error，默认info"
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        default=False,
        help="关闭执行后自动数据库备份"
    )
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()

    # 生成全局trace_id
    trace_id = f"run_{int(time.time())}"
    if args.batch_tag:
        trace_id += f"_{args.batch_tag}"
    set_trace_id(trace_id)
    
    # 动态调整日志级别
    if args.log_level:
        from common.logger import setup_log_level
        setup_log_level(console_level=args.log_level)

    db_client = None
    try:
        # 1. 初始化主LLM客户端
        llm_client = LLMClient(
            base_url=app_config.llm_base_url,
            timeout=app_config.llm_timeout,
            max_retry=app_config.llm_max_retry
        )
        model_name = app_config.llm_model

        # 2. 初始化Judge-LLM评判客户端（命令行优先级 > 配置文件；执行配置仍由yaml文件控制）
        judge_llm_client = None
        judge_enable = app_config.judge_llm_enable
        if args.judge_llm:
            judge_enable = True
        if args.no_judge_llm:
            judge_enable = False

        if judge_enable:
            judge_llm_client = LLMClient(
                base_url=app_config.judge_llm_base_url,
                timeout=app_config.judge_llm_timeout,
                max_retry=app_config.judge_llm_max_retry
            )
        
        # 3. 加载评测用例集
        case_list = YamlReader.get_test_data(args.case_file, "eval_case_list")
        if not case_list:
            print("无可用评测用例，程序退出")
            exit(0)

        # 4. 初始化批量执行器，传入并发数、自定义线程池大小；并发数命令行优先
        concurrent_num = args.concurrent if args.concurrent else app_config.eval_concurrent_num

        eval_runner = BatchEvalRunner(
            llm_client=llm_client,
            concurrent_num=concurrent_num,
            judge_llm_client=judge_llm_client,
            thread_pool_size=app_config.eval_thread_pool_size
        )

        # 5. 执行批量评测
        start_time = time.time()
        result_list = eval_runner.run_batch_cases(case_list=case_list)
        total_time = round(time.time() - start_time, 2)

        # 6. 统计汇总 + 控制台输出
        statistics = EvalStatistics(result_list, total_time)
        summary = statistics.calc_summary()
        statistics.print_summary()

        # 7. 评测结果持久化
        db_client = EvalDbClient(db_path=app_config.eval_db_path)
        if result_list:
            db_client.save_batch_result(
                result_list,
                summary,
                model_name=model_name,
                auto_backup=not args.no_backup
                )

        # 8. 导出CSV报告
        if result_list:
            reporter = EvalReporter(result_list)
            reporter.export_csv(filename=args.output)

    except KeyboardInterrupt:
        print("\n⚠️ 程序已中断，已安全释放资源")

    except Exception as e:
        print(f"\n❌ 程序运行异常：{str(e)}")
        logger = __import__("common.logger").get_logger("main")
        logger.error(f"主程序运行异常：{str(e)}", exc_info=True)

    finally:
        # 安全关闭数据库连接
        if db_client:
            del db_client
        print("\n程序结束")