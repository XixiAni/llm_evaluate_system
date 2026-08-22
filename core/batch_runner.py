import time
import threading
import json
from typing import List, Dict, Any,Optional
from concurrent.futures import ThreadPoolExecutor
from common.logger import get_logger
from core.llm_client import LLMClient
from core.validator import response_validator
from core.scorer import answer_scorer
from common.yaml_reader import YamlReader

logger = get_logger("batch_runner")

class BatchEvalRunner:
    """
    批量评测执行器
    
    采用依赖注入模式接收LLM客户端，支持串行/并发两种执行模式
    
    单条异常隔离，统一收集结果，内置API请求限流保护
    
    支持拆分统计接口耗时与业务计算耗时，便于性能分析与瓶颈定位

    可选接入Judge-LLM大模型自校验，实现规则+LLM双重幻觉检测

    校验器、评分器复用模块级单例，避免重复初始化开销
    """

    def __init__(self, llm_client: LLMClient, concurrent_num: int = 1, judge_llm_client: Optional[LLMClient] = None):
        """
        初始化批量执行器，注入LLM客户端，复用全局单例校验器与评分器

        并发架构分工：信号量严格限制API请求并发数，线程池管理总线程资源，计算环节不受限流

        Args:
            llm_client: 已初始化的主评测大模型客户端实例
            concurrent_num: 最大API请求并发数，默认1（串行）；大于1时启用线程池并发执行
            judge_llm_client: 可选，已初始化的评判大模型客户端实例，传入则启用LLM自校验幻觉检测
        """
        self.llm_client = llm_client
        self.judge_llm_client = judge_llm_client
        self.api_concurrent_num = concurrent_num
        # API请求限流信号量，精准控制同时发起的请求数量
        self._api_semaphore = threading.Semaphore(concurrent_num)  # 控制API请求并发数
        # 线程池总大小：API并发数 × 2，保证计算环节可与IO并行，默认不低于4，不高于10
        self._thread_pool_size = min(max(concurrent_num * 2, 4), 10)

        # 复用全局模块级单例，无状态工具类全程仅初始化一次
        self.validator = response_validator
        self.scorer = answer_scorer
        self.eval_result_list: List[Dict[str, Any]] = []

        # 预加载评判提示词与等级映射，仅开启评判客户端时执行
        if self.judge_llm_client:
            prompt_config = YamlReader.read_file("judge_hallucination.yaml", sub_dir = "prompts")
            self._judge_system_prompt = prompt_config.get("system_prompt", "")
            self._judge_user_template = prompt_config.get("user_prompt_template", "")
            # 等级映射：数字等级 → 项目统一字符串等级，与规则版体系对齐
            self._level_map = {0: "无", 1: "低", 2: "中", 3: "高"}
            logger.info("Judge-LLM 大模型自校验模块已启用")
    def run_single_case(self, case_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行单条评测用例，完整链路：请求模型 → 有效性校验 → 合规性校验 → 评分与幻觉检测

        可选执行Judge-LLM语义级幻觉校验，失败自动降级为规则版结果

        全链路异常捕获，保证单条用例失败不中断批量任务

        Args:
            case_info: 单条用例字典，包含case_id、case_desc、prompt、expect_keywords、standard_answer等
        Returns:
            dict: 标准化单条用例执行结果，字段完整无缺失
        """
        start_time = time.time()
        thread_id = threading.current_thread().name

        # 初始化默认结果字典，异常场景也能保证字段完整
        single_result = {
            "case_id": case_info.get("case_id", "unknown_id"),
            "case_desc": case_info.get("case_desc", "unknown_desc"),
            "prompt": case_info.get("prompt", ""),
            "execute_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "thread_id": thread_id,
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
            # ========== 第一步：本地数据准备，纯内存操作 ==========
            prompt = case_info["prompt"]
            std_ans = case_info.get("standard_answer", "")
            expect_kw = case_info.get("expect_keywords", [])
            judge_resp = None  # 评判结果预初始化
            
            print(f"【评测执行】【{thread_id}】正在运行用例 {single_result['case_id']}: {single_result['case_desc']}")

            # ========== 第二步：受限IO请求，信号量保护 ==========
            # 信号量限流：超出最大并发数则阻塞等待，保证API请求不超限
            self._api_semaphore.acquire()
            try:
                # 1. 调用大模型（仅该环节受限流保护）
                resp = self.llm_client.chat(prompt)

                # 2. 调用评判大模型（配置开启且有标准答案时执行，同享限流保护）
                if self.judge_llm_client and std_ans.strip():
                    judge_prompt = self._judge_user_template.format(
                        standard_answer=std_ans,
                        answer_content=resp.get("data", "")
                    )
                    judge_resp = self.judge_llm_client.chat(judge_prompt)
            finally:
                # 无论请求是否成功，都释放信号量，避免死锁
                self._api_semaphore.release()
            single_result["api_cost_ms"] = resp.get("cost_ms", 0)

            # ========== 第三步：本地计算与校验 ==========
            if resp["code"] == 0:
                single_result["success_flag"] = True
                answer = resp["data"]
                single_result["answer_content"] = answer
                compute_start = time.time()

                ## 3.1 有效性+合规性校验（不受限流，并行执行提升效率）
                validate_result = self.validator.validate_all(answer)
                single_result.update(validate_result)

                # 3.2 执行打分+幻觉检测（不受限流，并行执行提升效率）
                score_result = self.scorer.score_answer(answer, expect_kw, std_ans)
                single_result.update(score_result)

                # 3.3 Judge-LLM 语义级幻觉校验（成功则覆盖规则版结果，失败自动降级）
                if judge_resp and judge_resp["code"] == 0:
                    try:
                        judge_data = json.loads(judge_resp["data"])
                        level_num = judge_data.get("level", -1)
                        if level_num in self._level_map:
                            single_result["hallucination_level"] = self._level_map[level_num]
                            single_result["hallucination_msg"] = judge_data.get("reason", "LLM评判完成")
                            logger.debug(f"用例 {single_result['case_id']} Judge-LLM评判完成，等级：{self._level_map[level_num]}")
                    except Exception as e:
                        logger.warning(f"用例 {single_result['case_id']} Judge-LLM结果解析失败，降级使用规则版：{str(e)}")

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
        
        结果顺序与输入用例顺序完全一致，不影响后续统计与导出

        Args:
            case_list: 评测用例列表
        Returns:
            list: 所有用例的执行结果列表
        """
        self.eval_result_list.clear()
        mode_desc = "串行" if self.api_concurrent_num == 1 else f"API并发{self.api_concurrent_num}，线程池{self._thread_pool_size}线程"
        print(f"===== 开始批量评测，共加载 {len(case_list)} 条评测用例，执行模式：{mode_desc} =====")
        # 并发数为1时等价串行，直接循环执行，避免线程池额外开销
        if self.api_concurrent_num <= 1:
            self.eval_result_list = [self.run_single_case(case) for case in case_list]
        else:
            # 线程池执行，按提交顺序收集结果，保证顺序与输入一致
            with ThreadPoolExecutor(max_workers = self._thread_pool_size) as executor:
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
