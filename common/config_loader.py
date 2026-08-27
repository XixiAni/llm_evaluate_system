import sys
from common.logger import get_logger, setup_log_level
from common.yaml_reader import YamlReader

logger = get_logger("config_loader")

class ConfigLoader:
    """
    统一配置加载与校验器

    集中管理所有框架配置的读取、默认值填充、合法性校验，遵循fail-fast原则

    配置错误直接终止程序，聚合所有问题一次性输出

    优化点：新增日志级别配置、线程池大小配置
    """

    def __init__(self):
        """初始化并加载全量配置，执行合法性校验"""
        self._load_all_config()
        self._validate_config()
        # 配置校验通过后，设置日志级别
        setup_log_level(self.log_file_level, self.log_console_level)
        logger.info("全量配置加载与校验完成")

    def _load_all_config(self) -> None:
        """一次性读取所有配置文件，填充到实例属性"""
        # 主框架配置
        config = YamlReader.read_file("config.yaml")

        # or，防御yaml中节点为null的场景
        llm_config = config.get("llm") or {}
        judge_config = config.get("judge_llm") or {}
        eval_config = config.get("eval") or {}
        log_config = config.get("log") or {}

        # 主模型配置
        self.llm_base_url = llm_config.get("base_url", "")
        self.llm_timeout = llm_config.get("timeout", 30)
        self.llm_max_retry = llm_config.get("max_retry", 1)
        self.llm_model = llm_config.get("model", "deepseek-v4-flash")
        self.llm_slow_threshold_ms = llm_config.get("slow_threshold_ms", 1500)

        # Judge-LLM配置
        self.judge_llm_enable = judge_config.get("enable", False)
        self.judge_llm_base_url = judge_config.get("base_url", self.llm_base_url)
        self.judge_llm_timeout = judge_config.get("timeout", 60)
        self.judge_llm_max_retry = judge_config.get("max_retry", 2)

        # 评测执行配置
        self.eval_concurrent_num = eval_config.get("concurrent_num", 1)
        self.eval_db_path = eval_config.get("db_path", "./output/eval_result.db")
        self.eval_output_dir = eval_config.get("output_dir", "./output")
        self.eval_thread_pool_size = eval_config.get("thread_pool_size", None)

        # 日志配置
        self.log_file_level = log_config.get("file_level", "info")
        self.log_console_level = log_config.get("console_level", "info")

    def _validate_config(self) -> None:
        """集中校验所有配置合法性，聚合错误后统一输出"""
        errors = []

        # ========== 通用基础配置校验 ==========
        if not self.llm_base_url or not self.llm_base_url.strip():
            errors.append("配置项 llm.base_url 不能为空，请填写正确的模型接口地址")

        if not isinstance(self.llm_timeout, (int, float)) or self.llm_timeout <= 0:
            errors.append(f"配置项 llm.timeout 必须为大于0的数字，当前值：{self.llm_timeout}")

        if not isinstance(self.llm_max_retry, int) or self.llm_max_retry < 0:
            errors.append(f"配置项 llm.max_retry 必须为非负整数，当前值：{self.llm_max_retry}")

        if not isinstance(self.eval_concurrent_num, int) or self.eval_concurrent_num <= 0:
            errors.append(f"配置项 eval.concurrent_num 必须为正整数，当前值：{self.eval_concurrent_num}")

        if self.eval_thread_pool_size is not None and (not isinstance(self.eval_thread_pool_size, int) or self.eval_thread_pool_size <= 0):
            errors.append(f"配置项 eval.thread_pool_size 必须为正整数，当前值：{self.eval_thread_pool_size}")

        # 日志级别校验
        valid_levels = {"debug", "info", "warning", "error", "critical"}

        if self.log_file_level.lower() not in valid_levels:
            errors.append(f"配置项 log.file_level 取值无效，可选：{','.join(valid_levels)}，当前值：{self.log_file_level}")

        if self.log_console_level.lower() not in valid_levels:
             errors.append(f"配置项 log.console_level 取值无效，可选：{','.join(valid_levels)}，当前值：{self.log_console_level}")

        # ========== Judge-LLM 关联配置校验（仅开启时校验） ==========
        if self.judge_llm_enable:
            if not self.judge_llm_base_url or not self.judge_llm_base_url.strip():
                errors.append("配置项 judge_llm.base_url 不能为空（Judge-LLM已开启）")

            if not isinstance(self.judge_llm_timeout, (int, float)) or self.judge_llm_timeout <= 0:
                errors.append(f"配置项 judge_llm.timeout 必须为大于0的数字（Judge-LLM已开启），当前值：{self.judge_llm_timeout}")

            if not isinstance(self.judge_llm_max_retry, int) or self.judge_llm_max_retry < 0:
                errors.append(f"配置项 judge_llm.max_retry 必须为非负整数（Judge-LLM已开启），当前值：{self.judge_llm_max_retry}")

        # 错误汇总输出
        if errors:
            print("\n❌ 配置校验失败，共发现 {} 处问题：".format(len(errors)))
            for idx, err in enumerate(errors, 1):
                print("  {}. {}".format(idx, err))
            print("\n请修正 config.yaml 后重新运行程序")
            logger.error(f"配置校验失败，共{len(errors)}处错误，程序终止")
            sys.exit(1)

# 全局单例，外部直接导入使用
app_config = ConfigLoader()
