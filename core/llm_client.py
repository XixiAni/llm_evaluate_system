import requests
import json
import warnings
import time
import os
from urllib.parse import urljoin
from requests.exceptions import RequestException, HTTPError, Timeout, ConnectionError
from common.logger import get_logger

logger = get_logger("llm_client")
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

class LLMClient:
    def __init__(self, api_key: str = None, base_url: str = "", timeout: int = 30, max_retry: int = 1):
        ENV_API_KEY_NAME = "AI_API_KEY"
        if api_key is not None and api_key.strip() != "":
            self.api_key = api_key.strip()
        else:
            env_key = os.getenv(ENV_API_KEY_NAME, "")
            self.api_key = env_key.strip()

        if not self.api_key:
            err_msg = f"未获取有效API密钥！请实例化时传入api_key参数/配置系统环境变量 {ENV_API_KEY_NAME}/在项目根目录创建 .env 文件"
            logger.error(err_msg)
            raise ValueError(err_msg)

        self.base_url = base_url
        self.base_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        self.auth_header = self.base_headers["Authorization"]
        self.masked_auth = self.auth_header[:15] + "***MASKED***" + self.auth_header[-5:]
        self.timeout = timeout
        self.max_retry = max_retry
        self.verify = False
        self.session = requests.Session()
        self.session.headers.update(self.base_headers)

    def _parse_response_json(self, resp) -> dict:
        try:
            result = resp.json()
            return {"code": 0, "data": result, "msg": "请求成功"}
        except json.JSONDecodeError:
            return {"code": -2, "data": resp.text, "msg": "响应内容不是合法JSON格式"}

    def send_post(self, api_path: str, request_data: dict) -> dict:
        full_url = urljoin(self.base_url, api_path)
        start_time = time.time()
        retry_count = 0
        retry_interval = 1

        logger.info(f"【POST请求发起】接口地址：{full_url}，请求入参：{request_data}")
        while retry_count <= self.max_retry:
            try:
                resp = self.session.post(
                    url=full_url,
                    json=request_data,
                    timeout=self.timeout,
                    verify=self.verify
                )
                resp.raise_for_status()
                parse_result = self._parse_response_json(resp)
                cost = round((time.time() - start_time) * 1000, 2)
                logger.info(f"【POST请求完成】耗时{cost}ms，返回状态码：{resp.status_code}，统一返回码：{parse_result['code']}")
                return parse_result
            except (Timeout, ConnectionError) as e:
                retry_count += 1
                if retry_count > self.max_retry:
                    break
                logger.warning(f"网络波动，{retry_interval}秒后重试第 {retry_count} 次...")
                time.sleep(retry_interval)

        cost = round((time.time() - start_time) * 1000, 2)
        try:
            resp.raise_for_status()
        except Timeout:
            err_msg = f"请求超时，超时限制{self.timeout}秒"
            logger.error(f"【POST请求失败】接口：{full_url}，耗时{cost}ms，错误原因：{err_msg}")
            return {"code": -1, "data": None, "msg": err_msg}
        except ConnectionError:
            err_msg = "网络连接失败，无法访问接口地址"
            logger.error(f"【POST请求失败】接口：{full_url}，耗时{cost}ms，错误原因：{err_msg}")
            return {"code": -1, "data": None, "msg": err_msg}
        except HTTPError as e:
            err_msg = f"接口返回错误状态码：{str(e)}"
            logger.error(f"【POST请求失败】接口：{full_url}，耗时{cost}ms，错误原因：{err_msg}，原始响应：{resp.text}")
            return {"code": -1, "data": resp.text, "msg": err_msg}
        except RequestException as e:
            err_msg = f"未知网络异常：{str(e)}"
            logger.error(f"【POST请求失败】接口：{full_url}，耗时{cost}ms，错误原因：{err_msg}")
            return {"code": -1, "data": None, "msg": err_msg}

    def chat(self, prompt: str, model: str = None) -> dict:
        """
        快捷对话方法：封装标准对话接口调用，直接返回回答文本
        :param prompt: 用户提问
        :param model: 模型名，不传则使用环境变量默认值
        :return: 统一格式返回，data字段为回答文本
        """
        api_path = "/v1/chat/completions"
        use_model = model if model else os.getenv("LLM_MODEL", "deepseek-v4-flash")
        request_body = {
            "model": use_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7
        }
        resp = self.send_post(api_path, request_body)
        if resp["code"] == 0:
            try:
                content = resp["data"]["choices"][0]["message"]["content"]
                return {"code": 0, "data": content, "msg": "调用成功"}
            except Exception as e:
                return {"code": -3, "data": resp["data"], "msg": f"提取回答失败：{str(e)}"}
        else:
            return resp
