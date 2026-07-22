import time
from typing import List, Dict, Any
from common.logger import get_logger
from core.llm_client import LLMClient
from core.validator import ResponseValidator
from core.scorer import AnswerScorer

logger = get_logger("batch_runner")

class BatchEvalRunner:
    def __init__(self, llm_client: LLMClient):
        # 依赖注入模式，和项目一完全一致
        self.llm_client = llm_client
        self.validator = ResponseValidator()
        self.scorer = AnswerScorer()
        self.eval_result_list: List[Dict[str, Any]] = []

    def run_single_case(self, case_info: Dict[str, Any]) -> Dict[str, Any]:
        """单条用例执行，自带异常容错，单条失败不影响整体"""
        start_time = time.time()
        # 默认结果初始化，和项目一逻辑完全一致
        single_result = {
            "case_id": case_info.get("case_id", "unknown_id"),
            "case_desc": case_info.get("case_desc", "unknown_desc"),
            "prompt": case_info.get("prompt", ""),
            "execute_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
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
            print(f"【评测执行】正在运行用例 {single_result['case_id']}: {single_result['case_desc']}")
            
            # 1. 调用大模型
            resp = self.llm_client.chat(prompt)
            cost_ms = round((time.time() - start_time) * 1000, 2)
            single_result["request_cost_ms"] = cost_ms

            if resp["code"] == 0:
                single_result["success_flag"] = True
                answer = resp["data"]
                single_result["answer_content"] = answer

                # 2. 执行校验
                validate_result = self.validator.validate_all(answer)
                single_result.update(validate_result)

                # 3. 执行打分与幻觉检测
                expect_kw = case_info.get("expect_keywords", [])
                std_ans = case_info.get("standard_answer", "")
                score_result = self.scorer.score_answer(answer, expect_kw, std_ans)
                single_result.update(score_result)

            else:
                single_result["error_msg"] = resp["msg"]

        except Exception as e:
            single_result["error_msg"] = f"执行异常：{str(e)}"
            logger.error(f"用例 {single_result['case_id']} 运行出错：{str(e)}")

        self.eval_result_list.append(single_result)
        return single_result

    def run_batch_cases(self, case_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量执行所有评测用例"""
        self.eval_result_list.clear()
        print(f"===== 开始批量评测，共加载 {len(case_list)} 条评测用例 =====")
        for case in case_list:
            self.run_single_case(case)
        print(f"===== 批量评测全部完成，总计 {len(self.eval_result_list)} 条执行记录 =====")
        return self.eval_result_list

    def get_all_results(self) -> List[Dict[str, Any]]:
        return self.eval_result_list
