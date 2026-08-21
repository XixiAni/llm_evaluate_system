"""
SQLite持久化客户端 调用示例

定位：参考示例，不参与业务运行

演示：批次列表查询、单批次汇总查询、批次明细查询、批次删除四个核心接口的代码调用方式
"""
from common.sqlite_client import EvalDbClient

# 初始化客户端
db_client = EvalDbClient(db_path="./output/eval_result.db")

# 1. 查询最近5个批次
batch_list = db_client.query_batch_list(limit=5)
print("最近批次列表：", batch_list)

# 2. 查询单个批次汇总信息
batch_info = db_client.query_batch_by_id("batch_1724234567_abc123")
print("批次详情：", batch_info)

# 3. 查询批次下所有用例明细
case_list = db_client.query_case_details_by_batch_id("batch_1724234567_abc123")
print("用例数量：", len(case_list))

# 4. 删除指定批次
result = db_client.delete_batch_by_id("batch_1724234567_abc123")
print("删除结果：", result)