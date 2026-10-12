import sys
from unittest.mock import patch

# ==============================================
# pytest 全局前置配置
# 所有测试模块导入前执行，全局Mock配置读取接口
# 彻底解除单元测试对真实配置文件的依赖
# ==============================================
patch(
    "common.yaml_reader.YamlReader.read_file",
    return_value={
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
        # ========== 合规敏感词配置 ==========
        "sensitive_words": []
    }
).start()

# 清除可能已缓存的 config_loader 模块，强制后续导入重新走 Mock 链路
if "common.config_loader" in sys.modules:
    del sys.modules["common.config_loader"]
