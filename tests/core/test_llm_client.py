import json
import pytest
from unittest.mock import patch, Mock
from requests.exceptions import Timeout, HTTPError, ConnectionError
from common.error_code import ErrorCode
from core.llm_client import LLMClient

@pytest.fixture
def llm_client():
    """初始化测试客户端，使用测试密钥，不触发真实请求"""
    with patch("core.llm_client.YamlReader.get", return_value=1500):
        client = LLMClient(
            api_key="sk-test-key",
            base_url="https://test.api.com",
            timeout=10,
            max_retry=1
        )
        return client

def test_chat_success_parse(llm_client):
    """正向：请求成功，正确提取回答内容"""
    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "测试回答内容"}}]
    }
    mock_resp.raise_for_status.return_value = None

    with patch.object(llm_client.session, "post", return_value=mock_resp):
        result = llm_client.chat("测试prompt")
        assert result["code"] == 0
        assert result["data"] == "测试回答内容"
        assert result["cost_ms"] > 0

def test_chat_timeout_retry(llm_client):
    """反向：超时异常，触发重试逻辑"""
    with patch.object(llm_client.session, "post", side_effect=Timeout("连接超时")):
        result = llm_client.chat("测试prompt")
        assert result["code"] == ErrorCode.NETWORK_TIMEOUT.code
        assert "超时" in result["msg"]
        # 最大重试1次 + 首次调用 = 总共调用2次
        assert llm_client.session.post.call_count == 2

def test_chat_5xx_error_retry(llm_client):
    """反向：5xx服务端错误，触发重试"""
    mock_resp = Mock()
    mock_resp.status_code = 502
    mock_resp.raise_for_status.side_effect = HTTPError("502 Bad Gateway")
    mock_resp.text = "502 Bad Gateway"

    with patch.object(llm_client.session, "post", return_value=mock_resp):
        result = llm_client.chat("测试prompt")
        assert result["code"] == ErrorCode.HTTP_ERROR.code
        assert llm_client.session.post.call_count == 2

def test_chat_4xx_error_no_retry(llm_client):
    """反向：4xx客户端错误，不重试直接返回"""
    mock_resp = Mock()
    mock_resp.status_code = 401
    mock_resp.raise_for_status.side_effect = HTTPError("401 Unauthorized")
    mock_resp.text = "401 Unauthorized"

    with patch.object(llm_client.session, "post", return_value=mock_resp):
        result = llm_client.chat("测试prompt")
        assert result["code"] == ErrorCode.HTTP_ERROR.code
        assert llm_client.session.post.call_count == 1  # 不重试

def test_response_parse_failed(llm_client):
    """反向：返回非JSON格式，解析失败返回对应错误码"""
    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.json.side_effect = json.JSONDecodeError("无效JSON", "", 0) # 使用标准 JSON 解析异常类型，和真实场景一致
    mock_resp.raise_for_status.return_value = None
    mock_resp.text = "非JSON文本"

    with patch.object(llm_client.session, "post", return_value=mock_resp):
        result = llm_client.chat("测试prompt")
        assert result["code"] == ErrorCode.RESPONSE_PARSE_ERROR.code
        assert "解析失败" in result["msg"]

def test_empty_api_key_raise_error():
    """反向：空密钥初始化抛出异常"""
    with pytest.raises(ValueError) as exc_info:
        LLMClient(api_key="")
    assert "API密钥" in str(exc_info.value)