from enum import Enum
from typing import Tuple


class ErrorCode(Enum):
    """全局统一错误码枚举类，按业务领域分层编码。

    编码规则：
    
        0     : 通用成功
        1xxx  : 配置/参数类错误
        2xxx  : 网络/IO类错误
        3xxx  : 内容校验类错误
        4xxx  : 评测业务类错误
    """
    # 通用成功
    SUCCESS = (0, "执行成功")

    # 配置/参数类 1xxx
    CONFIG_FILE_NOT_FOUND = (1001, "配置文件不存在")
    CONFIG_KEY_NOT_FOUND = (1002, "配置节点不存在")
    PARAM_EMPTY = (1003, "入参为空")
    API_KEY_MISSING = (1004, "API密钥未配置")

    # 网络/IO类 2xxx
    NETWORK_TIMEOUT = (2001, "请求超时")
    NETWORK_CONNECT_ERROR = (2002, "网络连接失败")
    HTTP_ERROR = (2003, "接口返回HTTP错误状态码")
    RESPONSE_PARSE_ERROR = (2004, "响应内容解析失败")

    # 内容校验类 3xxx
    VALID_EMPTY_CONTENT = (3001, "回答内容为空")
    VALID_LENGTH_NOT_ENOUGH = (3002, "回答长度不足")
    VALID_HIGH_REPEAT = (3003, "回答重复率过高")
    COMPLIANCE_SENSITIVE_WORD = (3004, "检测到敏感词")

    # 评测业务类 4xxx
    ANSWER_EXTRACT_FAILED = (4001, "模型回答提取失败")
    NO_STANDARD_ANSWER = (4002, "无标准答案，无法执行检测")

    @property
    def code(self) -> int:
        """获取错误码数值。"""
        return self.value[0]

    @property
    def msg(self) -> str:
        """获取错误码描述。"""
        return self.value[1]
