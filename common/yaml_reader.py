import yaml
import os
import re
from typing import Any
from common.logger import get_logger

logger = get_logger("yaml_reader")

class YamlReader:
    """
    YAML配置与测试数据统一读取工具类
    核心能力：文件级缓存、点式路径嵌套取值、环境变量占位符替换、多环境配置支持
    所有方法均为类方法，无需实例化即可调用
    """
    _cache: dict[str, dict] = {}
    _current_env: str = "dev"

    @classmethod
    def set_current_env(cls, env_name: str) -> None:
        """
        设置全局运行环境标识，可适配多环境配置切换
        Args:
            env_name: 环境名称，如 dev / test / prod
        """
        cls._current_env = env_name
        logger.info(f"全局运行环境已设置为：{env_name}")

    @classmethod
    def _replace_env_var(cls, value: Any) -> Any:
        """
        替换字符串中的环境变量占位符，格式为 ${变量名}
        非字符串类型直接原样返回
        Args:
            value: 待替换的原始值
        Returns:
            Any: 完成环境变量替换后的值，未匹配到的占位符保持原样
        """
        if not isinstance(value, str):
            return value
        pattern = r"\$\{([\w-]+)\}"
        def _replace(match):
            var_name = match.group(1)
            return os.environ.get(var_name, match.group(0))
        return re.sub(pattern, _replace, value)

    @classmethod
    def _get_config_path(cls, filename: str) -> str:
        """
        拼接config目录下配置文件的绝对路径
        Args:
            filename: 配置文件名称（含后缀）
        Returns:
            str: 配置文件的完整绝对路径
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        full_path = os.path.join(base_dir, "config", filename)
        logger.debug(f"拼接配置文件完整路径：{full_path}")
        return full_path

    @classmethod
    def _get_by_dot_path(cls, data: dict, key_path: str, error_prefix: str = "") -> Any:
        """
        通过点分隔的路径从嵌套字典中取值，如 'llm.base_url'
        Args:
            data: 原始字典数据
            key_path: 点分隔的嵌套键路径
            error_prefix: 错误日志前缀，用于区分配置/测试数据场景
        Returns:
            Any: 路径对应的值，自动完成环境变量占位符替换
        Raises:
            KeyError: 路径中某一层级的键不存在时抛出
        """
        keys = key_path.split(".")
        current_node = data
        for key in keys:
            if key not in current_node:
                err_msg = f"{error_prefix}完整路径 [{key_path}]，当前层级缺失字段 [{key}]"
                logger.error(err_msg)
                raise KeyError(err_msg)
            current_node = current_node[key]
        logger.info(f"配置读取成功：{key_path} = {current_node}")
        current_node = cls._replace_env_var(current_node)
        return current_node

    @classmethod
    def read_file(cls, filename: str) -> dict:
        """
        读取config目录下的YAML配置文件，同文件全程仅读取一次，结果存入缓存
        Args:
            filename: 配置文件名称（含后缀）
        Returns:
            dict: 解析后的YAML配置字典
        Raises:
            FileNotFoundError: 配置文件不存在时抛出
            Exception: YAML格式解析失败时抛出
        """
        file_path = cls._get_config_path(filename)
        if file_path in cls._cache:
            logger.info(f"匹配到配置缓存，直接返回：{file_path}")
            return cls._cache[file_path]
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            cls._cache[file_path] = data
            logger.info(f"配置文件 {filename} 读取完成，存入缓存")
            return data
        except FileNotFoundError as e:
            logger.error(f"配置文件不存在：{file_path}，异常：{str(e)}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"读取YAML文件异常：{file_path}，异常：{str(e)}", exc_info=True)
            raise

    @classmethod
    def get(cls, filename: str, key_path: str) -> Any:
        """
        读取config目录下配置文件的指定节点值，支持点式路径
        Args:
            filename: 配置文件名称
            key_path: 点分隔的嵌套键路径
        Returns:
            Any: 配置节点对应的值
        """
        logger.info(f"读取配置节点，文件：{filename}，路径：{key_path}")
        data = cls.read_file(filename)
        return cls._get_by_dot_path(data, key_path, error_prefix="配置读取失败：")

    @classmethod
    def get_test_data(cls, filename: str, key_path: str = None) -> Any:
        """
        读取data目录下的评测用例数据文件，支持全量读取或指定节点读取
        Args:
            filename: 测试数据文件名称
            key_path: 可选，点分隔的嵌套键路径，不传则返回全量数据
        Returns:
            Any: 测试数据内容，列表或字典
        Raises:
            FileNotFoundError: 测试数据文件不存在时抛出
            Exception: YAML格式解析失败时抛出
        """
        file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", filename)
        logger.info(f"读取测试数据，文件：{filename}，路径：{key_path if key_path else '使用全量数据'}")
        if file_path in cls._cache:
            logger.info(f"匹配到测试数据缓存，直接返回：{file_path}")
            data = cls._cache[file_path]
        else:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                cls._cache[file_path] = data
                logger.info(f"测试数据文件 {filename} 读取完成，存入缓存")
            except FileNotFoundError as e:
                logger.error(f"测试数据文件不存在：{file_path}，异常：{str(e)}", exc_info=True)
                raise
            except Exception as e:
                logger.error(f"读取测试数据文件异常：{file_path}，异常：{str(e)}", exc_info=True)
                raise
        if not key_path:
            return data
        return cls._get_by_dot_path(data, key_path, error_prefix="测试数据读取失败：")
