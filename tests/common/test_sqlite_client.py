import os
import time
import sqlite3
import pytest
from common.sqlite_client import EvalDbClient

@pytest.fixture
def db_client(tmp_path):
    """在临时目录创建数据库客户端，每个用例独立"""
    db_path = os.path.join(tmp_path, "test_eval.db")
    client = EvalDbClient(db_path=db_path, backup_retention=2)
    return client

def test_init_table_auto_create(db_client):
    """正向：初始化自动创建表结构"""
    batch_list = db_client.query_batch_list()
    assert isinstance(batch_list, list)
    assert len(batch_list) == 0

def test_save_and_query_batch(db_client):
    """正向：保存批次结果后可查询到对应记录"""
    result_list = [
        {
            "case_id": "case001",
            "case_desc": "测试用例1",
            "prompt": "测试问题",
            "execute_timestamp": "2026-10-09 10:00:00",
            "thread_id": "MainThread",
            "api_cost_ms": 100.0,
            "compute_cost_ms": 50.0,
            "request_cost_ms": 150.0,
            "answer_content": "测试回答",
            "success_flag": True,
            "error_msg": "",
            "is_valid": True,
            "is_compliant": True,
            "validity_msg": "通过",
            "compliance_msg": "通过",
            "total_score": 90.0,
            "relevance_score": 95.0,
            "completeness_score": 85.0,
            "hallucination_level": "无",
            "hallucination_msg": "无风险",
            "judge_llm_status": "disabled",
            "judge_llm_err": None,
            "judge_raw_resp": ""
        }
    ]
    summary = {
        "total": 1,
        "success": 1,
        "total_time": 0.15,
        "success_rate": 100.0,
        "avg_score": {"total": 90.0}
    }
    
    batch_id = db_client.save_batch_result(result_list, summary, model_name="test-model", auto_backup=False)
    assert batch_id.startswith("batch_")
    
    # 查询批次列表
    batch_list = db_client.query_batch_list()
    assert len(batch_list) == 1
    assert batch_list[0]["model_name"] == "test-model"
    
    # 查询明细
    details = db_client.query_case_details_by_batch_id(batch_id)
    assert len(details) == 1
    assert details[0]["case_id"] == "case001"

def test_delete_batch_cascade(db_client):
    """正向：删除批次级联删除明细"""
    result_list = [{"case_id": "case001", "case_desc": "", "prompt": "", "execute_timestamp": "",
                  "thread_id": "", "api_cost_ms": 0, "compute_cost_ms": 0, "request_cost_ms": 0,
                  "answer_content": "", "success_flag": True, "error_msg": "", "is_valid": True,
                  "is_compliant": True, "validity_msg": "", "compliance_msg": "",
                  "total_score": 0, "relevance_score": 0, "completeness_score": 0,
                  "hallucination_level": "", "hallucination_msg": "",
                  "judge_llm_status": "disabled", "judge_llm_err": "", "judge_raw_resp": ""}]
    summary = {"total": 1, "success": 1, "total_time": 0, "success_rate": 100, "avg_score": {"total": 0}}
    
    batch_id = db_client.save_batch_result(result_list, summary, auto_backup=False)
    assert db_client.query_batch_by_id(batch_id) is not None
    
    # 删除批次
    result = db_client.delete_batch_by_id(batch_id)
    assert result is True
    assert db_client.query_batch_by_id(batch_id) is None
    assert len(db_client.query_case_details_by_batch_id(batch_id)) == 0

def test_backup_and_restore(db_client):
    """正向：数据库备份与恢复功能正常"""
    # 1. 写入测试数据
    result_list = []
    summary = {"total": 0, "success": 0, "total_time": 0, "success_rate": 0, "avg_score": {"total": 0}}
    batch_id = db_client.save_batch_result(result_list, summary, auto_backup=False)
    
    # 2. 执行备份
    backup_path = db_client.backup()
    assert os.path.exists(backup_path)
    
    # 3. 删除原批次数据
    db_client.delete_batch_by_id(batch_id)

    # 4. 执行 CHECKPOINT 合并 WAL 到主库，清空日志文件，解除文件锁定
    conn = sqlite3.connect(db_client.db_path)
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
    conn.close()

    # 5. 清理 WAL/SHM 残留文件，避免旧日志覆盖恢复数据（重试兼容 Windows 句柄延迟）
    db_path = db_client.db_path
    wal_path = db_path + "-wal"
    shm_path = db_path + "-shm"

    for f in [wal_path, shm_path]:
         for _ in range(3):
             if os.path.exists(f):
                 try:
                     os.remove(f)
                     break
                 except PermissionError:
                     time.sleep(0.1)
    
    # 6. 执行恢复
    restore_result = db_client.restore_from_backup(backup_path)
    assert restore_result is True
    
    # 再次清理 WAL 保证读取最新主文件
    for f in [wal_path, shm_path]:
        if os.path.exists(f):
            os.remove(f)

    # 7. 验证数据已恢复
    assert db_client.query_batch_by_id(batch_id) is not None

def test_integrity_check(db_client):
    """正向：数据库完整性检查通过"""
    assert db_client.check_integrity() is True