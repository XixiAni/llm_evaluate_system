# AI大模型自动化评测系统
> 最后更新时间：2026年8月 | 版本：v0.1.19
![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)

基于 Python 开发的轻量级大模型自动化评测工具，面向AI测试开发场景，采用YAML数据驱动设计，支持批量Prompt评测、响应有效性校验、内容合规检测、规则版幻觉检测与多维度量化打分，自动生成评测报告，可用于大模型版本效果回归、基线对比、内容质量专项测试场景。

## ✨ 核心亮点
- 🧪 **分层评测体系**：有效性校验 → 合规性检测 → 智能打分 → 幻觉识别，全链路自动化
- 🎯 **多维量化打分**：相关性、完整度、合规性加权计算，评分规则全量可配置
- 🧠 **双重幻觉检测**：规则算法 + 大模型自校验双链路，可插拔配置，失败自动降级兜底，兼顾效率与准确率；支持调用状态全链路追踪，区分未开启/成功/解析失败/接口失败四档状态，便于数据分析与问题排查  
- 🔍 **规则幻觉检测**：兜底自校验链路，双维度判定（新增词数量 + 占比）+ 白名单豁免 + 精细化停用词，大幅降低长文本误判率
- ✅ **全场景有效性校验**：覆盖空内容、长度不足、单字符复读、连续短语复读四类低质量回答
- ⚡ **并发批量调度**：线程池+信号量双机制职责分离，精准限制API并发，计算环节并行提速，评测效率提升数倍
- 📊 **Judge 链路可观测**：评判模型调用成功率、接口失败率、解析失败率自动统计，原始响应落库留存，问题定位高效
- ⏱️ **细粒度耗时统计**：拆分主模型接口耗时、评判模型接口耗时、业务计算耗时、全链路耗时，支持慢请求阈值告警，性能瓶颈定位更精准
- 📊 **数据驱动设计**：评测用例、打分权重、校验阈值、幻觉等级、输出路径全量 YAML 可配置，无需修改代码
- 🛡️ **高并发安全设计**：核心工具类采用DCL双重检查锁线程安全单例，信号量精准限流，多线程场景稳定可靠
- 🛑 **优雅中断保护**：支持 Ctrl+C 安全停止，不再提交新任务，等待已提交任务完成后落库退出，不损坏数据库、不泄漏资源
- 📈 **丰富统计维度**：自动输出成功率、分项平均分、幻觉风险分布、校验通过率、耗时统计多维度汇总
- 🛡️ **高容错执行**：单用例异常隔离，网络波动自动重试，异常分类统一出口，批量任务不中断
- 🔧 **统一配置中心**：集中式配置加载与合法性校验，启动自动巡检配置完整性，fail-fast 快速暴露问题
- 💾 **轻量持久化存储**：基于Python标准库SQLite零依赖实现评测结果持久化，批次+明细一对多设计，支持外键约束、WAL高性能写入模式、高频字段索引；支持历史数据回溯与多版本模型效果横向对比；支持表结构自动平滑迁移，历史数据库文件无缝兼容新版本
- 🛡️ **数据安全兜底**：SQLite自动热备份+留存策略+完整性校验，支持一键恢复
- 🔒 **配置安全校验**：启动自动扫描明文密钥，从机制上避免敏感信息提交代码库
- 📝 **生产级日志体系**：控制台文本+文件JSON双格式，全链路trace_id追踪，异常自动携带完整堆栈
- 🛠️ **配套命令行工具**：内置数据库管理脚本，无需编写代码即可查询历史批次、查看用例详情、清理测试数据，运维管理成本低
- ⚙️ **完整命令行参数**：所有运行参数可通过命令行覆盖，原生支持CI/CD流水线集成
- 📝 **企业级规范**：密钥脱敏、日志埋点、环境变量管理、全局统一错误码，符合安全开发标准
- ♻️ **成熟基底复用**：核心组件复用双项目验证的成熟代码，稳定性有保障

## 🏗️ 架构设计
```mermaid
flowchart TD
    A[入口层 main.py] --> B[核心业务层 core]
    B --> C[公共工具层 common]
    C --> D[配置数据层 config/data]
    B --> E[报告输出层 report]
```

## 📦 环境依赖
 
- Python 3.8+
- 可用的大模型API密钥（兼容OpenAI协议标准）
- 完整依赖清单见 [requirements.txt](requirements.txt)
 
## 🚀 快速上手
 
### 1. 安装依赖

```bash
pip install -r requirements.txt
```
 
### 2. 配置密钥
项目根目录创建  `.env`  文件（复制  `.env.example`  模板修改即可）：
 
```ini
AI_API_KEY=sk-你的大模型密钥
LLM_MODEL=deepseek-v4-flash
```

#### 2.1 可选：开启大模型自校验
修改 `config.yaml` 中 `judge_llm.enable` 为 `true`，即可启用规则+LLM双重幻觉检测；关闭时完全走规则版链路，无额外Token消耗。

### 3. 运行评测

```bash  
python main.py

# 指定用例文件+并发数运行
python main.py --case-file my_cases.yaml -c 5

# 强制开启Judge-LLM+自定义批次标签
python main.py --judge-llm --batch-tag v2.3.1_regression

# 关闭自动备份+指定输出文件名
python main.py --no-backup -o model_v2_compare.csv
```
 
### 4. 查看结果

- 控制台输出：实时执行日志 + 评测指标汇总报告
- CSV报告： `./output/eval_report_时间戳.csv`（默认自动追加时间戳，支持自定义文件名，Excel直接打开）
- 全链路日志： `./logs/` 目录按日期独立存储，同一天多次运行自动追加
- SQLite数据库：  `./output/eval_result.db` （支持历史数据查询、多版本对比）
  - 命令行查询：通过 `tools/db_manager.py` 快速检索历史批次与用例明细，无需打开数据库文件

### 5. 管理历史评测数据
```bash
# 查看最近10条评测批次
python tools/db_manager.py list --limit 10

# 查看单批次汇总详情
python tools/db_manager.py detail --batch_id batch_xxx

# 查看批次下所有用例明细
python tools/db_manager.py cases --batch_id batch_xxx

# 删除指定批次（级联删除所有用例明细）
python tools/db_manager.py delete --batch_id batch_xxx
```
 
## 📁 项目目录结构
 
```text
├── common/             # 公共工具层：全项目复用基础组件
│   ├── config_loader.py  # 统一配置加载与校验器，集中管理全量框架配置
│   ├── logger.py       # 标准化日志工具，控制台+文件双输出
│   ├── yaml_reader.py  # YAML配置读取工具，支持缓存、点式路径、环境变量占位
│   ├── error_code.py   # 全局统一错误码枚举，按业务领域分层管理
│   └── sqlite_client.py # SQLite评测结果持久化客户端，零依赖轻量存储
├── config/             # 配置文件层：所有可变参数
│   ├── config.yaml     # 全局框架配置
│   └── eval_rules.yaml # 评测规则配置（敏感词、权重、校验阈值）
├── prompts/            # 提示词模板层：存放LLM评判类提示词模板
│   └── judge_hallucination.yaml
├── core/               # 核心业务层：评测核心逻辑
│   ├── llm_client.py   # 大模型请求客户端，统一封装接口调用
│   ├── batch_runner.py # 批量评测执行器，负责任务调度与结果收集
│   ├── validator.py    # 响应校验模块：有效性+合规性双校验
│   ├── scorer.py       # 智能评分模块：多维打分 + 幻觉检测
│   └── statistics.py   # 评测结果统计与汇总输出工具
├── data/               # 评测数据层：YAML格式存储评测用例
│   └── eval_cases.yaml # 评测用例集
├── report/             # 报告输出层
│   └── reporter.py     # CSV评测报告导出工具
├── logs/               # 运行日志输出目录（自动生成）
├── output/             # 评测报告输出目录（自动生成）
├── docs/               # 文档与示例目录
│   └── examples/       # 扩展实现参考示例，不参与业务运行
├── tools/              # 配套工具层：辅助管理脚本
│   └── db_manager.py   # 数据库管理命令行工具
├── main.py             # 项目唯一入口
├── requirements.txt    # 项目依赖清单
└── README.md           # 项目说明文档
```

## 📖 更多文档
 
- 详细使用与原理说明：见[DETAILED_USAGE.md](DETAILED_USAGE.md)，包含完整调用链路、代码详解、选型考量
- 版本变更记录：见 [CHANGELOG.md](CHANGELOG.md)
 
## 📄 License

本项目采用 MIT 协议开源，详见 [LICENSE](LICENSE) 文件。