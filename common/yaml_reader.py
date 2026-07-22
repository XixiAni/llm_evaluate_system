import yaml
import os
import re
from typing import Any
from common.logger import get_logger

logger = get_logger("yaml_reader")

class YamlReader:
    _cache: dict[str, dict] = {}
    _current_env: str = "dev"

    @classmethod
    def set_current_env(cls, env_name: str) -> None:
        cls._current_env = env_name
        logger.info(f"全局运行环境已设置为：{env_name}")

    @classmethod
    def _replace_env_var(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        pattern = r"\$\{([\w-]+)\}"
        def _replace(match):
            var_name = match.group(1)
            return os.environ.get(var_name, match.group(0))
        return re.sub(pattern, _replace, value)

    @classmethod
    def _get_config_path(cls, filename: str) -> str:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        full_path = os.path.join(base_dir, "config", filename)
        logger.debug(f"拼接配置文件完整路径：{full_path}")
        return full_path

    @classmethod
    def _get_by_dot_path(cls, data: dict, key_path: str, error_prefix: str = "") -> Any:
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
        logger.info(f"读取配置节点，文件：{filename}，路径：{key_path}")
        data = cls.read_file(filename)
        return cls._get_by_dot_path(data, key_path, error_prefix="配置读取失败：")

    @classmethod
    def get_test_data(cls, filename: str, key_path: str = None) -> Any:
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
