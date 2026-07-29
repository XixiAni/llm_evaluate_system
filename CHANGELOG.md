# Changelog
所有版本变更记录在此文件中，格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 规范，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/) 规范。

## [v0.1.0] - 2026-07-22
### Added
- 完成 AI大模型自动化评测系统 核心框架搭建，采用四层分层解耦架构
- 全量复用[项目一](https://github.com/XixiAni/ai_model_eval_framework)、[项目二](https://github.com/XixiAni/playwright_ui_po_autotest_framework)成熟底层组件，保证基底稳定性
- 新增 LLMClient 大模型请求客户端，兼容OpenAI协议，支持网络异常自动重试、密钥脱敏、统一返回格式
- 新增 YAML 数据驱动评测体系，评测用例与代码完全分离，支持批量加载与校验
- 新增 BatchEvalRunner 批量评测执行引擎，单用例异常隔离机制，单条失败不阻断整体流程
- 新增 ResponseValidator 响应校验模块，覆盖有效性校验（空答/长度/重复率）与合规性校验（敏感词检测）
- 新增 AnswerScorer 智能评分模块，实现多维加权打分算法与规则版幻觉检测能力
- 新增 EvalReporter 评测报告模块，支持导出CSV格式评测结果，Excel直接打开无乱码
- 集成标准化日志体系，控制台+文件双输出，按日期自动拆分日志文件
- 落地企业级安全规范，密钥通过环境变量/.env文件读取，无硬编码，支持敏感信息脱敏
- 新增项目配套文档：README.md、DETAILED_USAGE.md

## [v0.1.1] - 2026-07-27
### Added
- 全量核心方法统一补充 Google 风格 Docstring 注释规范
- DETAILED_USAGE.md 新增各模块原理解释、工程规范说明章节
- 进度条.md 新增已知问题记录、注释统一化待办条目

### Fixed
- 修正 llm_client.py 中 chat 方法注释格式不统一问题
- 修正 .gitignore 中 report 源码目录误忽略问题

### Known Issues
- 规则版幻觉检测暂未适配中文分词，中文场景准确率有限
- eval_rules.yaml 敏感词库为示例占位，未接入业务级违禁词
- 边界异常场景、单元测试覆盖待完善

## [v0.1.2] - 2026-07-29
### Added
- 新增全局统一错误码枚举类`ErrorCode`，按业务领域分层编码，统一异常描述口径
- 规则版幻觉检测新增中文分词能力，接入jieba分词+通用停用词过滤，大幅提升中文场景准确率
- `YamlReader`新增递归式环境变量占位符替换能力，支持字典/列表嵌套结构全量替换
- 全模块边界异常兜底优化，配置缺失、空入参等场景均提供默认值降级，避免程序中断

### Fixed
- 统一全模块入参校验顺序：优先校验内容空值，再校验基准参数
- 修正`validator.py`中语法格式不规范问题，对齐PEP8编码风格

### Known Issues
- `eval_rules.yaml`敏感词库为示例占位，未接入业务级违禁词
- 单元测试用例未覆盖全量分支
- 中文分词停用词表为基础通用版，垂直领域可按需扩展

