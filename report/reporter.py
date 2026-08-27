import csv
import os
from datetime import datetime
from typing import List, Dict, Any
from common.logger import get_logger
from common.yaml_reader import YamlReader

logger = get_logger("reporter")

class EvalReporter:
    """
    评测报告导出工具

    支持CSV格式导出，自动创建输出目录，编码兼容Excel，字段可灵活扩展

    默认文件名自动追加时间戳，多次执行不覆盖历史报告

    优化点：新增judge_api_cost_ms字段导出
    """
    def __init__(self, result_list: List[Dict[str, Any]]):
        """
        初始化报告生成器，接收评测结果列表

        Args:
            result_list: 评测结果字典列表
        """
        self.result_list = result_list
        # 从配置读取输出目录，缺失则使用默认值兜底
        self.export_dir = YamlReader.get("config.yaml", "eval.output_dir", "./output")
        os.makedirs(self.export_dir, exist_ok=True)

    def export_csv(self, filename: str = None) -> str:
        """
        将评测结果导出为CSV文件

        Args:
            filename: 导出文件名，不传则自动生成带时间戳的默认文件名：eval_report_{时间戳}.csv
        Returns:
            str: 导出文件的完整路径
        """
        # 未指定文件名时，自动追加时间戳，避免多次执行覆盖
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"eval_report_{timestamp}.csv"
        file_path = os.path.join(self.export_dir, filename)
        headers = [
            "case_id", "case_desc", "execute_timestamp",
            "api_cost_ms", "judge_api_cost_ms", "compute_cost_ms", "request_cost_ms",
            "success_flag", "error_msg",
            "is_valid", "is_compliant", "validity_msg", "compliance_msg",
            "total_score", "relevance_score", "completeness_score",
            "hallucination_level", "hallucination_msg",
            "judge_llm_status", "judge_llm_err",
            "answer_content"
        ]
        # 打开文件，w=覆盖写入模式；newline="" 消除CSV多余空行（Windows系统特有bug修复）
        # encoding="utf-8-sig" 核心：兼容Excel打开中文不乱码
        with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
            # 构建DictWriter对象：字典写入CSV，fieldnames绑定表头
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for res in self.result_list:
                # res.get(key, "")：容错，若结果字典缺失某个字段，填充空字符串，防止CSV列错位
                row = {key: res.get(key, "") for key in headers}
                writer.writerow(row)
        
        print(f"√ 评测报告已导出至：{file_path}")
        logger.info(f"评测报告导出完成，路径：{file_path}")
        return file_path
