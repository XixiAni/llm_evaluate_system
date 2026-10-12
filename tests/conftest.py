import sys
from unittest.mock import patch
from common.yaml_reader import YamlReader

# ==============================================
# pytest 全局前置配置
# 仅Mock配置类文件读取，不影响yaml_reader自身功能测试
# 解除单元测试对真实配置文件的依赖，同时保留测试文件的真实读取能力
# ==============================================

# Mock配置数据：仅用于config.yaml、eval_rules.yaml等配置文件
_MOCK_CONFIG = {
    # ========== 主模型配置 ==========
    "llm": {
        "base_url": "https://test.api.com",
        "timeout": 30,
        "max_retry": 1,
        "model": "test-model",
        "slow_threshold_ms": 1500
    },
    # ========== Judge-LLM 配置 ==========
    "judge_llm": {
        "enable": False,
        "base_url": "https://test.api.com",
        "timeout": 60,
        "max_retry": 2
    },
    # ========== 评测执行配置 ==========
    "eval": {
        "concurrent_num": 1,
        "db_path": "./test_output/test.db",
        "output_dir": "./test_output",
        "thread_pool_size": None
    },
    # ========== 日志配置 ==========
    "log": {
        "file_level": "info",
        "console_level": "info"
    },
    # ========== 有效性校验规则 ==========
    "validity": {
        "min_length": 5,
        "max_repeat_rate": 0.7,
        "max_continuous_repeat": 2
    },
    # ========== 打分权重配置 ==========
    "score_weight": {
        "relevance": 0.4,
        "completeness": 0.3,
        "compliance": 0.3
    },
    # ========== 幻觉检测配置 ==========
    "hallucination": {
        "low_risk_threshold": 3,
        "high_risk_threshold": 6,
        "extra_ratio_threshold": 0.3,
        "whitelist": []
    },
    # ========== 合规敏感词配置（非空，保证合规测试默认场景断言匹配） ==========
    "sensitive_words": ["示例敏感词"]
}

# 保存原始read_file方法，用于非配置文件的真实读取
_original_read_file = YamlReader.read_file

def _mock_read_file_side_effect(filename: str, sub_dir: str = "config"):
    """
    读取分流：配置类文件返回Mock值，其他文件调用原始方法
    既解除业务模块对真实配置的依赖，又不影响yaml_reader自身的功能测试
    """
    # 配置类文件：返回Mock配置
    if filename in ("config.yaml", "eval_rules.yaml", "judge_hallucination.yaml"):
        return _MOCK_CONFIG
    # 其他文件（测试临时文件等）：走真实读取逻辑
    return _original_read_file(filename, sub_dir)

# 全局打桩
patch(
    "common.yaml_reader.YamlReader.read_file",
    side_effect=_mock_read_file_side_effect
).start()

# 清除可能已缓存的 config_loader 模块，强制后续导入重新走 Mock 链路
if "common.config_loader" in sys.modules:
    del sys.modules["common.config_loader"]
