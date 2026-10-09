import sys
import pytest
from unittest.mock import patch
from common.config_loader import ConfigLoader
@pytest.fixture(autouse=True)
def reset_config_singleton():
    """前置清理：移除已加载的全局配置单例，保证每个用例独立初始化"""
    if "common.config_loader" in sys.modules:
        del sys.modules["common.config_loader"]
    yield
    if "common.config_loader" in sys.modules:
        del sys.modules["common.config_loader"]

def test_normal_config_load_default_values():
    """正向：正常配置加载，缺失字段使用默认值兜底"""
    mock_config = {
        "llm": {
            "base_url": "https://test.api.com",
            "timeout": 30,
            "max_retry": 1
        },
        "eval": {
            "concurrent_num": 2
        },
        "log": {
            "file_level": "info",
            "console_level": "info"
        }
    }
    with patch("common.config_loader.YamlReader.read_file", return_value=mock_config):
        config = ConfigLoader()
        assert config.llm_base_url == "https://test.api.com"
        assert config.llm_model == "deepseek-v4-flash"  # 默认值兜底
        assert config.eval_concurrent_num == 2
        assert config.eval_thread_pool_size is None
        assert config.judge_llm_enable is False  # 默认关闭

def test_judge_llm_config_validate_when_enabled():
    """正向：Judge-LLM开启时，关联配置强制校验"""
    mock_config = {
        "llm": {"base_url": "https://test.api.com"},
        "judge_llm": {
            "enable": True,
            "base_url": "https://judge.api.com",
            "timeout": 60,
            "max_retry": 2
        },
        "eval": {},
        "log": {}
    }
    with patch("common.config_loader.YamlReader.read_file", return_value=mock_config):
        config = ConfigLoader()
        assert config.judge_llm_enable is True
        assert config.judge_llm_base_url == "https://judge.api.com"

def test_invalid_concurrent_num():
    """反向：并发数为非法值，校验失败终止程序"""
    mock_config = {
        "llm": {"base_url": "https://test.api.com"},
        "eval": {"concurrent_num": 0},
        "log": {}
    }
    with patch("common.config_loader.YamlReader.read_file", return_value=mock_config):
        with pytest.raises(SystemExit):
            ConfigLoader()

def test_plaintext_key_security_check():
    """反向：配置文件存在明文密钥，安全校验不通过"""
    mock_config = {
        "llm": {
            "base_url": "https://test.api.com",
            "api_key": "sk-123456"  # 明文密钥
        },
        "eval": {},
        "log": {}
    }
    with patch("common.config_loader.YamlReader.read_file", return_value=mock_config):
        with pytest.raises(SystemExit):
            ConfigLoader()

def test_invalid_log_level():
    """反向：日志级别非法，校验失败"""
    mock_config = {
        "llm": {"base_url": "https://test.api.com"},
        "eval": {},
        "log": {"file_level": "invalid_level"}
    }
    with patch("common.config_loader.YamlReader.read_file", return_value=mock_config):
        with pytest.raises(SystemExit):
            ConfigLoader()