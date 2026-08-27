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

    优化点：新增缓存清理方法，以支持热更新
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
    def _replace_env_var_recursive(cls, value: Any) -> Any:
        """
        递归替换值中的环境变量占位符，支持字符串、字典、列表嵌套结构。

        占位符格式：${变量名}，未匹配到的占位符保持原样返回。

        Args:
            value: 待替换的原始值，支持任意数据类型。
        Returns:
            完成占位符替换后的值，类型与输入一致。
        """
        if isinstance(value, str):
            pattern = r"\$\{([\w-]+)\}"
            def _replace(match: re.Match) -> str:
                var_name = match.group(1)
                return os.environ.get(var_name, match.group(0))
            return re.sub(pattern, _replace, value)
        elif isinstance(value, dict):
            return {k: cls._replace_env_var_recursive(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [cls._replace_env_var_recursive(item) for item in value]
        else:
            return value

    @classmethod
    def _get_abs_path(cls, sub_dir: str, filename: str) -> str:
        """
        通用路径拼接方法：拼接项目根目录下指定子目录的文件绝对路径
        
        仅做底层路径计算，不涉及业务语义，供配置、数据读取方法复用
        
        Args:
            sub_dir: 子目录名称，如 config / data / prompts
            filename: 文件名称（含后缀）
        Returns:
            str: 文件的完整绝对路径
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        full_path = os.path.join(base_dir, sub_dir, filename)
        # 配置类目录打印debug日志，辅助排查
        if sub_dir in ("config","prompts"):
            logger.debug(f"拼接配置文件完整路径：{full_path}")
        return full_path

    @classmethod
    def _get_path(cls, filename: str, sub_dir: str = "config") -> str:
        """
        通用配置文件路径拼接，默认读取config目录

        Args:
            filename: 配置文件名称（含后缀）
            通用配置文件路径拼接，默认读取config目录
        Returns:
            str: 配置文件的完整绝对路径
        """
        return cls._get_abs_path(sub_dir, filename)

    @classmethod
    def _get_config_path(cls, filename: str) -> str:
        """兼容旧调用：拼接config目录下配置文件的绝对路径"""
        return cls._get_path(filename, sub_dir="config")
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
            
        success_prefix = error_prefix.replace("读取失败：", "读取成功：")
        logger.info(f"{success_prefix}{key_path} = {current_node}")
        return current_node

    @classmethod
    def read_file(cls, filename: str, sub_dir: str = "config") -> dict:
        """
        读取指定目录下的YAML配置文件，同文件全程仅读取一次，结果存入缓存

        Args:
            filename: 配置文件名称（含后缀）
            sub_dir: 子目录名称，默认config，支持传入prompts等其他目录
        Returns:
            dict: 解析后的YAML配置字典,已完成全量环境变量占位符替换
        Raises:
            FileNotFoundError: 配置文件不存在时抛出
            Exception: YAML格式解析失败时抛出
        """
        file_path = cls._get_path(filename, sub_dir=sub_dir)
        if file_path in cls._cache:
            logger.info(f"匹配到配置缓存，直接返回：{file_path}")
            return cls._cache[file_path]
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            # 递归替换所有层级的环境变量
            data = cls._replace_env_var_recursive(data)
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
    def get(cls, filename: str, key_path: str, default: Any = None, sub_dir: str = "config") -> Any:
        """
        读取指定目录下配置文件的指定节点值，支持点式路径与默认值兜底

        Args:
            filename: 配置文件名称
            key_path: 点分隔的嵌套键路径
            default: 默认值，当键读取失败时返回
            sub_dir: 子目录名称，默认config
        Returns:
            Any: 配置节点对应的值,读取失败则返回default
        Raises:
            KeyError: 配置节点不存在时抛出
            FileNotFoundError: 配置文件不存在时抛出
        """
        logger.info(f"读取配置节点，文件：{filename}，路径：{key_path}")
        try:
            data = cls.read_file(filename, sub_dir=sub_dir)
            return cls._get_by_dot_path(data, key_path, error_prefix="配置读取失败：")
        except KeyError:
            logger.warning(f"配置节点不存在，返回默认值：{default}")
            return default

    @classmethod
    def get_test_data(cls, filename: str, key_path: str = None, default: Any = None) -> Any:
        """
        读取data目录下的评测用例数据文件，支持全量读取或指定节点读取
        
        Args:
            filename: 测试数据文件名称
            key_path: 可选，点分隔的嵌套键路径，不传则返回全量数据
            default: 默认值，当键读取失败时返回
        Returns:
            Any: 测试数据内容，列表或字典；读取失败则返回default
        Raises:
            FileNotFoundError: 测试数据文件不存在时抛出
            Exception: YAML格式解析失败时抛出
        """
        file_path = cls._get_abs_path("data",filename)
        logger.info(f"读取测试数据，文件：{filename}，路径：{key_path if key_path else '使用全量数据'}")
        if file_path in cls._cache:
            logger.info(f"匹配到测试数据缓存，直接返回：{file_path}")
            data = cls._cache[file_path]
        else:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                # 递归替换所有层级的环境变量
                data = cls._replace_env_var_recursive(data)
                cls._cache[file_path] = data
                logger.info(f"测试数据文件 {filename} 读取完成，存入缓存")
            except FileNotFoundError as e:
                logger.error(f"测试数据文件不存在：{file_path}，异常：{str(e)}", exc_info=True)
                return default
            except Exception as e:
                logger.error(f"读取测试数据文件异常：{file_path}，异常：{str(e)}", exc_info=True)
                return default
        if not key_path:
            return data
        try:
            return cls._get_by_dot_path(data, key_path, error_prefix="测试数据读取失败：")
        except KeyError:
            logger.warning(f"测试数据节点不存在，返回默认值：{default}")
            return default

    @classmethod
    def clear_cache(cls, filename: str = None, sub_dir: str = "config") -> None:
        """
        清理配置缓存
        
        Args:
            filename: 可选，指定文件名；不传则清空全部缓存
            sub_dir: 子目录，默认config；指定文件名时需对应
        """
        if filename:
            file_path = cls._get_path(filename, sub_dir=sub_dir)
            if file_path in cls._cache:
                del cls._cache[file_path]
                logger.info(f"已清理配置缓存：{file_path}")
        else:
            cls._cache.clear()
            logger.info("已清空全部配置缓存")