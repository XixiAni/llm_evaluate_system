from typing import List, Dict, Any
from common.logger import get_logger

logger = get_logger("statistics")


class EvalStatistics:
    """
    评测结果统计与报告输出工具

    接收评测结果列表，计算成功率、得分均值、幻觉分布、校验通过率等核心指标，

    并提供格式化控制台输出能力

    优化点：新增Judge-LLM链路成功率统计
    """

    def __init__(self, result_list: List[Dict[str, Any]], total_time: float):
        """
        初始化统计器，绑定评测结果与总耗时

        Args:
            result_list: 评测结果字典列表
            total_time: 批量评测总耗时，单位秒
        """
        self.result_list = result_list
        self.total_time = total_time
        self.total = len(result_list)
        self.success_list = [item for item in result_list if item["success_flag"]]
        self.success_count = len(self.success_list)
        self.failed_count = self.total - self.success_count

    def calc_summary(self) -> Dict[str, Any]:
        """
        计算全量统计指标，返回结构化汇总数据

        Returns:
            dict: 包含成功率、得分、幻觉分布、校验通过率、Judge链路统计，五类指标
        """
        summary = {
            "total": self.total,
            "success": self.success_count,
            "failed": self.failed_count,
            "success_rate": self._calc_success_rate(),
            "avg_score": self._calc_avg_scores(),
            "hallucination_dist": self._calc_hallucination_dist(),
            "validate_pass_rate": self._calc_validate_pass_rate(),
            "judge_stats": self._calc_judge_stats(),
            "total_time": self.total_time,
            "avg_time_per_case": round(self.total_time / self.total, 2) if self.total > 0 else 0
        }
        return summary

    def print_summary(self) -> None:
        """
        格式化打印汇总报告到控制台

        所有边界场景（全失败、无用例）均做兜底处理
        """
        print("\n" + "=" * 60)
        print("【批量评测汇总结果】")
        print("=" * 60)

        # 基础执行数据
        print(f"总用例数：{self.total} | 成功：{self.success_count}条 | 失败：{self.failed_count}条")
        if self.total > 0:
            success_rate = self.success_count / self.total * 100
            print(f"调用成功率：{success_rate:.2f}%")
            print(f"总耗时：{self.total_time}s | 单条平均耗时：{round(self.total_time / self.total, 2)}s/条")
        else:
            print("调用成功率：0%")
            print("未传入用例，请检查yaml配置文件")

        print("-" * 60)
        self._print_score_section()
        print("-" * 60)
        self._print_hallucination_section()
        print("-" * 60)
        self._print_validate_section()
        print("-" * 60)
        self._print_judge_section()
        print("=" * 60)

    def _calc_success_rate(self) -> float:
        """计算调用成功率，无用例时返回0"""
        if self.total == 0:
            return 0.0
        return round(self.success_count / self.total * 100, 2)

    def _calc_avg_scores(self) -> Dict[str, Any]:
        """计算各维度平均得分，全失败时返回N/A描述"""
        if self.success_count == 0:
            return {
                "total": "N/A(用例全部调用失败)",
                "relevance": "N/A(用例全部调用失败)",
                "completeness": "N/A(用例全部调用失败)"
            }
        return {
            "total": round(sum(item["total_score"] for item in self.success_list) / self.success_count, 2),
            "relevance": round(sum(item["relevance_score"] for item in self.success_list) / self.success_count, 2),
            "completeness": round(sum(item["completeness_score"] for item in self.success_list) / self.success_count, 2)
        }

    def _calc_hallucination_dist(self) -> Dict[str, Any]:
        """统计幻觉风险等级分布，全失败时返回N/A描述"""
        if self.success_count == 0:
            return {
                "none": {"count": 0, "ratio": "N/A(用例全部调用失败)"},
                "low": {"count": 0, "ratio": "N/A(用例全部调用失败)"},
                "medium": {"count": 0, "ratio": "N/A(用例全部调用失败)"},
                "high": {"count": 0, "ratio": "N/A(用例全部调用失败)"},
                "unknown": {"count": 0, "ratio": "N/A(用例全部调用失败)"}
            }
        levels = [item["hallucination_level"] for item in self.success_list]
        dist = {
            "none": levels.count("无"),
            "low": levels.count("低"),
            "medium": levels.count("中"),
            "high": levels.count("高"),
            "unknown": levels.count("未知")
        }
        return {
            level: {"count": cnt, "ratio": f"{cnt / self.success_count * 100:.2f}%"}
            for level, cnt in dist.items()
        }

    def _calc_validate_pass_rate(self) -> Dict[str, Any]:
        """计算有效性、合规性校验通过率，全失败时返回N/A描述"""
        if self.success_count == 0:
            return {
                "valid": "N/A(用例全部调用失败)",
                "compliant": "N/A(用例全部调用失败)"
            }
        valid_pass = sum(1 for item in self.success_list if item["is_valid"])
        compliant_pass = sum(1 for item in self.success_list if item["is_compliant"])
        return {
            "valid": f"{valid_pass / self.success_count * 100:.2f}%",
            "compliant": f"{compliant_pass / self.success_count * 100:.2f}%"
        }

    def _calc_judge_stats(self) -> Dict[str, Any]:
        """计算Judge-LLM链路统计，未开启时返回禁用标记"""
        judge_cases = [item for item in self.result_list if item["judge_llm_status"] != "disabled"]
        total = len(judge_cases)
        if total == 0:
            return {"enable": False, "total": 0, "msg": "Judge-LLM未开启"}
        
        success = sum(1 for item in judge_cases if item["judge_llm_status"] == "success")
        api_failed = sum(1 for item in judge_cases if item["judge_llm_status"] == "api_failed")
        parse_failed = sum(1 for item in judge_cases if item["judge_llm_status"] == "parse_failed")
        success_rate = round(success / total * 100, 2)
        return {
            "enable": True,
            "total": total,
            "success": success,
            "api_failed": api_failed,
            "parse_failed": parse_failed,
            "success_rate": f"{success_rate}%"
        }

    def _print_score_section(self) -> None:
        """打印得分统计区块"""
        score_data = self._calc_avg_scores()
        print("【得分统计】")
        print(f"平均总分：{score_data['total']} | 平均相关性得分：{score_data['relevance']} | 平均完整度得分：{score_data['completeness']}")

    def _print_hallucination_section(self) -> None:
        """打印幻觉风险分布区块"""
        hall_data = self._calc_hallucination_dist()
        print("【幻觉风险分布】")
        print(f"无风险：{hall_data['none']['count']} 条 {hall_data['none']['ratio']}")
        print(f"低风险：{hall_data['low']['count']} 条 {hall_data['low']['ratio']}")
        print(f"中风险：{hall_data['medium']['count']} 条 {hall_data['medium']['ratio']}")
        print(f"高风险：{hall_data['high']['count']} 条 {hall_data['high']['ratio']}")
        print(f"未知风险：{hall_data['unknown']['count']} 条 {hall_data['unknown']['ratio']}")

    def _print_validate_section(self) -> None:
        """打印校验通过率区块"""
        valid_data = self._calc_validate_pass_rate()
        print("【校验通过率】")
        print(f"有效性通过率：{valid_data['valid']}")
        print(f"合规性通过率：{valid_data['compliant']}")

    def _print_judge_section(self) -> None:
        """打印Judge-LLM链路统计区块"""
        judge_data = self._calc_judge_stats()
        print("【Judge-LLM 链路统计】")
        if not judge_data["enable"]:
            print("未开启")
            return
        print(f"调用总数：{judge_data['total']} | 成功：{judge_data['success']} | 成功率：{judge_data['success_rate']}")
        print(f"接口失败：{judge_data['api_failed']} | 解析失败：{judge_data['parse_failed']}")