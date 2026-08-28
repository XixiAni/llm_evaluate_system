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

# 全局停止事件：用于接收中断信号，优雅停止批量任务
_stop_event = threading.Event()
def request_stop() -> None:
    """请求停止批量任务，线程安全"""
    _stop_event.set()

def is_stop_requested() -> bool:
    """检查是否已请求停止"""
    return _stop_event.is_set()

class BatchEvalRunner:
    """
    批量评测执行器

    采用依赖注入模式接收LLM客户端，支持串行/并发两种执行模式

    单条异常隔离，统一收集结果，内置API请求限流保护

    支持拆分统计接口耗时与业务计算耗时，便于性能分析与瓶颈定位

    可选接入Judge-LLM大模型自校验，实现规则+LLM双重幻觉检测

    校验器、评分器复用模块级单例，避免重复初始化开销

    优化点：支持自定义线程池大小、Judge-LLM独立耗时统计、优雅中断
    """

    def __init__(self, llm_client: LLMClient, concurrent_num: int = 1, judge_llm_client: Optional[LLMClient] = None, thread_pool_size: int = None):
        """
        初始化批量执行器，注入LLM客户端，复用全局单例校验器与评分器

        并发架构分工：信号量严格限制API请求并发数，线程池管理总线程资源，计算环节不受限流

        Args:
            llm_client: 已初始化的主评测大模型客户端实例
            concurrent_num: 最大API请求并发数，默认1（串行）；大于1时启用线程池并发执行
            judge_llm_client: 可选，已初始化的评判大模型客户端实例，传入则启用LLM自校验幻觉检测
            thread_pool_size: 可选，自定义线程池总大小；不传则自动计算（并发数×2，4~10区间）
        """
        self.llm_client = llm_client
        self.judge_llm_client = judge_llm_client
        self.api_concurrent_num = concurrent_num
        # API请求限流信号量，精准控制同时发起的请求数量
        self._api_semaphore = threading.Semaphore(concurrent_num)  # 控制API请求并发数

        # 线程池大小：优先使用传入配置，否则自动计算
        if thread_pool_size and thread_pool_size > 0:
            self._thread_pool_size = thread_pool_size
        else:
            # 自动计算：API并发数 × 2，保证计算环节可与IO并行，默认不低于4，不高于10
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

        可选执行Judge-LLM语义级幻觉校验，解析或接口失败自动降级为规则版结果

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
            "judge_api_cost_ms": 0,
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
            "hallucination_msg": "",
            "judge_llm_status": "disabled",
            "judge_llm_err": None,
            "judge_raw_resp": ""
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
                # 预设默认值，兜底所有异常路径
                resp = None
                try:
                    resp = self.llm_client.chat(prompt)
                finally:
                    # 无论调用成功/抛出异常，都保证字段有值
                    single_result["api_cost_ms"] = resp.get("cost_ms", 0) if resp else 0

                # 2. 调用评判大模型：仅当主模型调用成功、且配置开启、且有标准答案时才执行（同享限流保护）
                # 主模型失败时无有效回答，跳过评判避免无效Token消耗
                if resp["code"] == 0 and self.judge_llm_client and std_ans.strip():
                    judge_user_prompt = self._judge_user_template.format(
                        standard_answer=std_ans,
                        answer_content=resp.get("data", "")
                    )

                    judge_start = time.time()
                    judge_resp = None

                    try:
                        judge_resp = self.judge_llm_client.chat(
                                prompt=judge_user_prompt,
                                system_prompt=self._judge_system_prompt
                            )
                    except Exception as e:
                        # 接口层异常：api_failed标记，网络超时、连接失败等；降级规则结果
                        single_result["judge_llm_status"] = "api_failed"
                        single_result["judge_llm_err"] = str(e)
                        single_result["judge_raw_resp"] = judge_resp.get("data", "") if judge_resp else str(e)
                        logger.warning(f"用例 {single_result['case_id']} Judge-LLM接口调用失败，降级使用规则版：{str(e)}")
                    else:
                        # 调用无异常，但返回业务错误码，也标记为api_failed
                        if judge_resp["code"] != 0:
                            single_result["judge_llm_status"] = "api_failed"
                            single_result["judge_llm_err"] = judge_resp["msg"]
                            single_result["judge_raw_resp"] = judge_resp.get("data", "")
                            logger.warning(f"用例 {single_result['case_id']} Judge-LLM接口返回错误，降级使用规则版：{judge_resp['msg']}")
                        else:
                            # 接口+业务双成功，标记为success
                            single_result["judge_llm_status"] = "success"
                    finally:
                        # 无论调用成功/异常/业务错误，都保证耗时统计必写入
                        single_result["judge_api_cost_ms"] = round((time.time() - judge_start) * 1000, 2)
            finally:
                # 无论请求是否成功，都释放信号量，避免死锁
                self._api_semaphore.release()

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

                # 3.3 Judge-LLM 语义级幻觉校验（接口成功时 解析，成功则覆盖规则版结果，失败自动降级）
                if judge_resp and judge_resp["code"] == 0:
                    # 接口返回成功，尝试解析JSON
                    try:
                        judge_data = json.loads(judge_resp["data"])
                        level_num = judge_data.get("level", -1)
                        if level_num in self._level_map:
                            single_result["hallucination_level"] = self._level_map[level_num]
                            single_result["hallucination_msg"] = judge_data.get("reason", "LLM评判完成")
                            logger.debug(f"用例 {single_result['case_id']} Judge-LLM评判完成，等级：{self._level_map[level_num]}")
                    except Exception as e:
                        # 解析失败：parse_failed标记，JSON解析失败；保留规则版结果
                        single_result["judge_llm_status"] = "parse_failed"
                        single_result["judge_llm_err"] = f"JSON解析失败：{str(e)}"
                        single_result["judge_raw_resp"] = judge_resp.get("data", "")
                        logger.warning(f"用例 {single_result['case_id']} Judge-LLM结果解析失败，保留规则版结果：{str(e)}")

                single_result["compute_cost_ms"] = round((time.time() - compute_start) * 1000, 2)

            else:
                # 主模型失败不修改Judge-LLM状态，保持disabled或原有状态
                single_result["error_msg"] = resp["msg"]

        except Exception as e:
            single_result["error_msg"] = f"执行异常：{str(e)}"
            logger.error(f"【线程:{thread_id}】 用例:{single_result['case_id']} 运行出错：{str(e)}")

        single_result["request_cost_ms"] = round((time.time() - start_time) * 1000, 2)
        return single_result

    def run_batch_cases(self, case_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        批量执行所有评测用例，清空历史结果后，按并发配置执行

        支持优雅中断：收到停止信号后不再提交新任务，等待已提交任务完成后返回

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
            for case in case_list:
                if is_stop_requested():
                    print("\n⚠️ 检测到中断请求，停止提交新用例")
                    break

                self.eval_result_list.append(self.run_single_case(case))
        else:
            # 线程池执行，按提交顺序收集结果，保证顺序与输入一致
            with ThreadPoolExecutor(max_workers = self._thread_pool_size) as executor:
                futures = []
                for case in case_list:
                    if is_stop_requested():
                        print("\n⚠️ 检测到中断请求，停止提交新用例")
                        break

                    futures.append(executor.submit(self.run_single_case, case))

                # 按提交顺序逐个取结果，保证结果列表顺序与输入用例完全一致
                self.eval_result_list = [future.result() for future in futures]
        print(f"===== 批量评测完成，已执行 {len(self.eval_result_list)} 条记录 =====")
        return self.eval_result_list

    def get_all_results(self) -> List[Dict[str, Any]]:
        """
        获取已执行的所有评测结果

        Returns:
            list: 评测结果列表
        """
        return self.eval_result_list
