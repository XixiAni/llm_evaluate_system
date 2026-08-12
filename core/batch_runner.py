import time
import threading
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from common.logger import get_logger
from core.llm_client import LLMClient
from core.validator import ResponseValidator
from core.scorer import AnswerScorer

logger = get_logger("batch_runner")

class BatchEvalRunner:
    """
    批量评测执行器
    
    采用依赖注入模式接收LLM客户端，支持串行/并发两种执行模式
    
    单条异常隔离，统一收集结果，内置API请求限流保护
    
    支持拆分统计接口耗时与业务计算耗时，便于性能分析与瓶颈定位
    
    设计思想沿用项目二并发规范：配置化参数、全异常隔离、顺序结果保证
    """

    def __init__(self, llm_client: LLMClient, concurrent_num: int = 1):
        """
        初始化批量执行器，注入LLM客户端，实例化校验器与评分器

        Args:
            llm_client: 已初始化的大模型客户端实例
            concurrent_num: 最大并发数，默认1（串行）；大于1时启用线程池并发执行
        """
        self.llm_client = llm_client
        self.concurrent_num = concurrent_num
        # API请求限流信号量，精准控制同时发起的请求数量（对齐项目二限流思想）
        self._api_semaphore = threading.Semaphore(concurrent_num)  # 控制API请求并发数
        self.validator = ResponseValidator()
        self.scorer = AnswerScorer()
        self.eval_result_list: List[Dict[str, Any]] = []

    def run_single_case(self, case_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行单条评测用例，完整链路：请求模型 → 有效性校验 → 合规性校验 → 评分与幻觉检测

        全链路异常捕获，保证单条用例失败不中断批量任务

        Args:
            case_info: 单条用例字典，包含case_id、case_desc、prompt、expect_keywords、standard_answer等
        Returns:
            dict: 标准化单条用例执行结果，字段完整无缺失
        """
        start_time = time.time()
        thread_id = threading.current_thread().name

        # 初始化默认结果字典，异常场景也能保证字段完整（对齐项目二异常隔离规范）
        single_result = {
            "case_id": case_info.get("case_id", "unknown_id"),
            "case_desc": case_info.get("case_desc", "unknown_desc"),
            "prompt": case_info.get("prompt", ""),
            "execute_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "thread_id": thread_id, # 并发排查字段，对其项目二进程标识设计
            "api_cost_ms": 0,
            "compute_cost_ms": 0,
            "request_cost_ms": 0,
            "answer_content": "",
            "success_flag": False,
            "error_msg": "",
            "is_valid": False,
            "is_compliant": False,
            "validity_msg": "",
            "compliance_msg": "",
            "total_score": 0,
            "relevance_score": 0,
            "completeness_score": 0,
            "hallucination_level": "",
            "hallucination_msg": ""
        }

        try:
            prompt = case_info["prompt"]
            print(f"【评测执行】【{thread_id}】正在运行用例 {single_result['case_id']}: {single_result['case_desc']}")

            # 信号量限流：超出最大并发数则阻塞等待，保证API请求不超限
            self._api_semaphore.acquire()
            try:
                # 1. 调用大模型
                resp = self.llm_client.chat(prompt)
            finally:
                # 无论请求是否成功，都释放信号量，避免死锁（对齐项目二资源释放规范）
                self._api_semaphore.release()
            single_result["api_cost_ms"] = resp.get("cost_ms", 0)

            if resp["code"] == 0:
                single_result["success_flag"] = True
                answer = resp["data"]
                single_result["answer_content"] = answer

                # 2. 执行校验（不受限流，并行执行提升效率）
                compute_start = time.time()
                validate_result = self.validator.validate_all(answer)
                single_result.update(validate_result)

                # 3. 执行打分与幻觉检测（不受限流，并行执行提升效率）
                expect_kw = case_info.get("expect_keywords", [])
                std_ans = case_info.get("standard_answer", "")
                score_result = self.scorer.score_answer(answer, expect_kw, std_ans)
                single_result.update(score_result)
                single_result["compute_cost_ms"] = round((time.time() - compute_start) * 1000, 2)

            else:
                single_result["error_msg"] = resp["msg"]

        except Exception as e:
            single_result["error_msg"] = f"执行异常：{str(e)}"
            logger.error(f"【线程:{thread_id}】 用例:{single_result['case_id']} 运行出错：{str(e)}")

        single_result["request_cost_ms"] = round((time.time() - start_time) * 1000, 2)
        return single_result

    def run_batch_cases(self, case_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        批量执行所有评测用例，清空历史结果后，按并发配置执行
        
        结果顺序与输入用例顺序完全一致，不影响后续统计与导出（对齐项目二结果汇总规范）

        Args:
            case_list: 评测用例列表
        Returns:
            list: 所有用例的执行结果列表
        """
        self.eval_result_list.clear()
        mode_desc = "串行" if self.concurrent_num == 1 else f"并发{self.concurrent_num}线程"
        print(f"===== 开始批量评测，共加载 {len(case_list)} 条评测用例，执行模式：{mode_desc} =====")
        # 并发数为1时等价串行，直接循环执行，避免线程池额外开销
        if self.concurrent_num <= 1:
            self.eval_result_list = [self.run_single_case(case) for case in case_list]
        else:
            # 线程池执行，按提交顺序收集结果，保证顺序与输入一致
            with ThreadPoolExecutor(max_workers = self.concurrent_num) as executor:
                # 按顺序提交任务，得到future列表与输入一一对应
                futures = [executor.submit(self.run_single_case, case) for case in case_list]
                # 按提交顺序逐个取结果，保证结果列表顺序与输入用例完全一致
                self.eval_result_list = [future.result() for future in futures]
        print(f"===== 批量评测全部完成，总计 {len(self.eval_result_list)} 条执行记录 =====")
        return self.eval_result_list

    def get_all_results(self) -> List[Dict[str, Any]]:
        """
        获取已执行的所有评测结果

        Returns:
            list: 评测结果列表
        """
        return self.eval_result_list
