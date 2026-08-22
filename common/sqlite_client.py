import sqlite3
import uuid
import time
from typing import List, Dict, Any,Optional
from common.logger import get_logger

logger = get_logger("sqlite_client")

class EvalDbClient:
    """
    SQLite 评测结果持久化客户端

    封装数据库初始化、批次结果落库、历史查询、批次删除能力，屏蔽底层SQL细节

    全链路异常兜底，写入失败不阻断主业务流程
    """

    def __init__(self, db_path: str = "./output/eval_result.db"):
        """
        初始化数据库客户端，自动完成表结构创建

        Args:
            db_path: SQLite 数据库文件路径，文件不存在时自动创建
        """
        self.db_path = db_path
        self._init_tables()

    def _get_connection(self) -> sqlite3.Connection:
        """
        获取数据库连接，内部工具方法

        Returns:
            sqlite3.Connection: 数据库连接对象
        """
        return sqlite3.connect(self.db_path)

    def _init_tables(self) -> None:
        """
        初始化数据表，表不存在时自动创建

        仅首次创建输出INFO日志，表已存在时静默，避免语义冗余

        包含两张表：批次主表 eval_batch、用例明细表 eval_case_detail
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
            # 前置查询：判断主表是否已存在，精准控制日志输出
            # 两张表绑定创建，主表存在则明细表必然存在，无需二次查询
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='eval_batch'")
                table_exists = cursor.fetchone() is not None
                if not table_exists:
                    # 批次主表：记录每次批量执行的整体信息
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS eval_batch (
                            batch_id TEXT PRIMARY KEY,
                            execute_time TEXT NOT NULL,
                            model_name TEXT,
                            total_cases INTEGER,
                            success_count INTEGER,
                            total_time REAL,
                            success_rate REAL,
                            avg_total_score REAL
                        )
                    """)

                    # 用例明细表：记录单条用例完整评测结果
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS eval_case_detail (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            batch_id TEXT NOT NULL,
                            case_id TEXT,
                            case_desc TEXT,
                            prompt TEXT,
                            execute_timestamp TEXT,
                            thread_id TEXT,
                            api_cost_ms REAL,
                            compute_cost_ms REAL,
                            request_cost_ms REAL,
                            answer_content TEXT,
                            success_flag INTEGER,
                            error_msg TEXT,
                            is_valid INTEGER,
                            is_compliant INTEGER,
                            validity_msg TEXT,
                            compliance_msg TEXT,
                            total_score REAL,
                            relevance_score REAL,
                            completeness_score REAL,
                            hallucination_level TEXT,
                            hallucination_msg TEXT,
                            FOREIGN KEY (batch_id) REFERENCES eval_batch(batch_id)
                        )
                    """)

                    conn.commit()
                    logger.info("数据库表结构初始化完成")
                else:
                    # 表已存在，仅输出DEBUG日志，INFO级别下不可见
                    logger.debug("数据库表结构已存在，跳过创建")
        except Exception as e:
            logger.error(f"数据库表初始化失败：{str(e)}", exc_info=True)

    def save_batch_result(self, result_list: List[Dict[str, Any]], summary: Dict[str, Any], model_name: str = "unknown") -> str:
        """
        保存一整批评测结果：写入批次主表 + 批量写入所有用例明细

        Args:
            result_list: 单条评测结果列表
            summary: 统计汇总数据
            model_name: 本次评测使用的模型名称
        Returns:
            str: 生成的批次ID，失败返回空字符串
        """
        # 生成唯一批次ID：时间戳+短随机串，兼顾可读性与唯一性
        batch_id = f"batch_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        execute_time = time.strftime("%Y-%m-%d %H:%M:%S")

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # 1. 写入批次主表
                avg_score_data = summary.get("avg_score", {})
                avg_total = avg_score_data.get("total", 0) if isinstance(avg_score_data, dict) else 0
                cursor.execute("""
                    INSERT INTO eval_batch
                    (batch_id, execute_time, model_name, total_cases, success_count, total_time, success_rate, avg_total_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    batch_id,
                    execute_time,
                    model_name,
                    summary.get("total", 0),
                    summary.get("success", 0),
                    summary.get("total_time", 0),
                    summary.get("success_rate", 0),
                    avg_total
                ))

                # 2. 组装明细数据，批量写入
                detail_rows = []
                for item in result_list:
                    detail_rows.append((
                        batch_id,
                        item.get("case_id", ""),
                        item.get("case_desc", ""),
                        item.get("prompt", ""),
                        item.get("execute_timestamp", ""),
                        item.get("thread_id", ""),
                        item.get("api_cost_ms", 0),
                        item.get("compute_cost_ms", 0),
                        item.get("request_cost_ms", 0),
                        item.get("answer_content", ""),
                        1 if item.get("success_flag") else 0,
                        item.get("error_msg", ""),
                        1 if item.get("is_valid") else 0,
                        1 if item.get("is_compliant") else 0,
                        item.get("validity_msg", ""),
                        item.get("compliance_msg", ""),
                        item.get("total_score", 0),
                        item.get("relevance_score", 0),
                        item.get("completeness_score", 0),
                        item.get("hallucination_level", ""),
                        item.get("hallucination_msg", "")
                    ))

                cursor.executemany("""
                    INSERT INTO eval_case_detail
                    (batch_id, case_id, case_desc, prompt, execute_timestamp, thread_id,
                    api_cost_ms, compute_cost_ms, request_cost_ms, answer_content,
                    success_flag, error_msg, is_valid, is_compliant, validity_msg, compliance_msg,
                    total_score, relevance_score, completeness_score, hallucination_level, hallucination_msg)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, detail_rows)

                conn.commit()
                logger.info(f"批次 {batch_id} 结果已持久化，共 {len(result_list)} 条用例")
                return batch_id

        except Exception as e:
            logger.error(f"批次结果写入数据库失败：{str(e)}", exc_info=True)
            return ""

    def query_batch_list(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        查询历史批次列表，按执行时间倒序
        
        Args:
            limit: 返回条数，默认最近10条
        Returns:
            list: 批次信息字典列表
        """
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row  # 支持按字段名访问结果
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM eval_batch
                    ORDER BY execute_time DESC
                    LIMIT ?
                """, (limit,))
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"查询批次列表失败：{str(e)}", exc_info=True)
            return []

    def query_batch_by_id(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """
        根据批次ID查询单条批次汇总信息
        
        Args:
            batch_id: 批次唯一ID
        Returns:
            dict: 批次汇总信息字典；批次不存在或查询失败返回None
        """
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM eval_batch
                    WHERE batch_id = ?
                    LIMIT 1
                """, (batch_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"查询批次详情失败，batch_id={batch_id}：{str(e)}", exc_info=True)
            return None
    def query_case_details_by_batch_id(self, batch_id: str) -> List[Dict[str, Any]]:
        """
        查询指定批次下的所有用例明细
    
        Args:
            batch_id: 批次唯一ID
        Returns:
            list: 用例明细字典列表，空批次或查询失败返回空列表
        """
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM eval_case_detail
                    WHERE batch_id = ?
                    ORDER BY id ASC
                """, (batch_id,))
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"查询批次明细失败，batch_id={batch_id}：{str(e)}", exc_info=True)
            return []
    def delete_batch_by_id(self, batch_id: str) -> bool:
        """
        级联删除指定批次：先删除明细表记录，再删除主表记录，事务保证原子性
    
        Args:
            batch_id: 批次唯一ID
        Returns:
            bool: 删除成功返回True，失败返回False
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # 先删明细表，再删主表，保证数据一致性
                cursor.execute("DELETE FROM eval_case_detail WHERE batch_id = ?", (batch_id,))
                cursor.execute("DELETE FROM eval_batch WHERE batch_id = ?", (batch_id,))
                conn.commit()
                affected_rows = cursor.rowcount
                if affected_rows > 0:
                    logger.info(f"批次 {batch_id} 已成功删除")
                    return True
                else:
                    logger.warning(f"批次 {batch_id} 不存在，无数据被删除")
                    return False
        except Exception as e:
            logger.error(f"删除批次失败，batch_id={batch_id}：{str(e)}", exc_info=True)
            return False
