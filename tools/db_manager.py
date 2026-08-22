"""
数据库管理命令行工具

提供历史批次查询、详情查看、批次删除等能力，无需编写业务代码

使用示例：
    python tools/db_manager.py list --limit 10
    python tools/db_manager.py detail --batch_id batch_xxx
    python tools/db_manager.py cases --batch_id batch_xxx
    python tools/db_manager.py delete --batch_id batch_xxx
"""
import os
import sys
import argparse

# 兼容命令行执行，将项目根目录加入Python路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from common.sqlite_client import EvalDbClient
from common.yaml_reader import YamlReader

# 命令行交互场景优化：控制台仅输出WARNING及以上级别日志
# 避免底层INFO日志干扰业务表格展示，文件日志保持INFO级别不变
import logging
_root_logger = logging.getLogger()
for _handler in _root_logger.handlers:
    # 匹配控制台处理器，排除文件处理器
    if isinstance(_handler, logging.StreamHandler) and not isinstance(_handler, logging.FileHandler):
        _handler.setLevel(logging.WARNING)

def init_client() -> EvalDbClient:
    """初始化数据库客户端，读取配置中的db路径"""
    db_path = YamlReader.get("config.yaml", "eval.db_path", "./output/eval_result.db")
    return EvalDbClient(db_path=db_path)


def cmd_list(args):
    """查看历史批次列表"""
    client = init_client()
    batch_list = client.query_batch_list(limit=args.limit)
    if not batch_list:
        print("暂无历史批次数据")
        return

    print(f"\n===== 最近 {len(batch_list)} 条评测批次 =====")
    print(f"{'批次ID':<28} {'执行时间':<20} {'模型':<20} {'用例数':<6} {'成功率':<8} {'平均分':<8}")
    print("-" * 100)
    for item in batch_list:
        print(
            f"{item['batch_id']:<28} "
            f"{item['execute_time']:<20} "
            f"{item['model_name']:<20} "
            f"{item['total_cases']:<6} "
            f"{item['success_rate']:<8} "
            f"{item['avg_total_score']:<8}"
        )
    print()


def cmd_detail(args):
    """查看单批次汇总详情"""
    client = init_client()
    info = client.query_batch_by_id(args.batch_id)
    if not info:
        print(f"未找到批次：{args.batch_id}")
        return

    print(f"\n===== 批次详情：{args.batch_id} =====")
    for key, value in info.items():
        print(f"{key}: {value}")
    print()


def cmd_cases(args):
    """查看批次下所有用例明细概览"""
    client = init_client()
    case_list = client.query_case_details_by_batch_id(args.batch_id)
    if not case_list:
        print(f"批次 {args.batch_id} 无用例明细或不存在")
        return

    print(f"\n===== 批次 {args.batch_id} 用例明细（共 {len(case_list)} 条）=====")
    print(f"{'用例ID':<12} {'状态':<6} {'总分':<8} {'幻觉等级':<8} {'用例描述'}")
    print("-" * 80)
    for item in case_list:
        status = "成功" if item["success_flag"] else "失败"
        print(
            f"{item['case_id']:<12} "
            f"{status:<6} "
            f"{item['total_score']:<8} "
            f"{item['hallucination_level']:<8} "
            f"{item['case_desc']}"
        )
    print()


def cmd_delete(args):
    """删除指定批次（带二次确认）"""
    client = init_client()
    # 二次确认
    confirm = input(f"确认删除批次 {args.batch_id} 吗？此操作不可撤销，输入 yes 确认：")
    if confirm.strip().lower() != "yes":
        print("已取消删除操作")
        return

    result = client.delete_batch_by_id(args.batch_id)
    if result:
        print(f"批次 {args.batch_id} 删除成功")
    else:
        print(f"批次 {args.batch_id} 删除失败或不存在")


def main():
    parser = argparse.ArgumentParser(description="评测数据库管理工具")
    subparsers = parser.add_subparsers(dest="command", required=True, help="支持的子命令")

    # list 子命令
    parser_list = subparsers.add_parser("list", help="查看历史批次列表")
    parser_list.add_argument("--limit", type=int, default=10, help="返回条数，默认10条")
    parser_list.set_defaults(func=cmd_list)

    # detail 子命令
    parser_detail = subparsers.add_parser("detail", help="查看单批次汇总详情")
    parser_detail.add_argument("--batch_id", type=str, required=True, help="批次ID")
    parser_detail.set_defaults(func=cmd_detail)

    # cases 子命令
    parser_cases = subparsers.add_parser("cases", help="查看批次用例明细概览")
    parser_cases.add_argument("--batch_id", type=str, required=True, help="批次ID")
    parser_cases.set_defaults(func=cmd_cases)

    # delete 子命令
    parser_delete = subparsers.add_parser("delete", help="删除指定批次（级联删除明细）")
    parser_delete.add_argument("--batch_id", type=str, required=True, help="批次ID")
    parser_delete.set_defaults(func=cmd_delete)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()