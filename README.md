# AI大模型自动化评测系统
> 最后更新时间：2026年8月 | 版本：v0.1.12
![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)

基于 Python 开发的轻量级大模型自动化评测工具，面向AI测试开发场景，采用YAML数据驱动设计，支持批量Prompt评测、响应有效性校验、内容合规检测、规则版幻觉检测与多维度量化打分，自动生成评测报告，可用于大模型版本效果回归、基线对比、内容质量专项测试场景。

## ✨ 核心亮点
- 🧪 **分层评测体系**：有效性校验 → 合规性检测 → 智能打分 → 幻觉识别，全链路自动化
- 🎯 **多维量化打分**：相关性、完整度、合规性加权计算，评分规则全量可配置
- 🔍 **高精度幻觉检测**：双维度判定（新增词数量 + 占比）+ 白名单豁免 + 精细化停用词，大幅降低长文本误判率
- ✅ **全场景有效性校验**：覆盖空内容、长度不足、单字符复读、连续短语复读四类低质量回答
- ⚡ **并发批量调度**：线程池+信号量双机制职责分离，精准限制API并发，计算环节并行提速，评测效率提升数倍
- ⏱️ **细粒度耗时统计**：拆分纯接口耗时、业务计算耗时、全链路耗时，支持慢请求阈值告警
- 📊 **数据驱动设计**：评测用例、打分权重、校验阈值、幻觉等级、输出路径全量 YAML 可配置，无需修改代码
- 📈 **丰富统计维度**：自动输出成功率、分项平均分、幻觉风险分布、校验通过率、耗时统计多维度汇总
- 🛡️ **高容错执行**：单用例异常隔离，网络波动自动重试，异常分类统一出口，批量任务不中断
- 💾 **轻量持久化存储**：基于Python标准库SQLite零依赖实现评测结果持久化，批次+明细一对多设计，支持历史数据回溯与多版本模型效果横向对比
- 🛠️ **配套命令行工具**：内置数据库管理脚本，无需编写代码即可查询历史批次、查看用例详情、清理测试数据，运维管理成本低
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
 
### 3. 运行评测

```bash  
python main.py
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
│   ├── logger.py       # 标准化日志工具，控制台+文件双输出
│   ├── yaml_reader.py  # YAML配置读取工具，支持缓存、点式路径、环境变量占位
│   ├── error_code.py   # 全局统一错误码枚举，按业务领域分层管理
│   └── sqlite_client.py # SQLite评测结果持久化客户端，零依赖轻量存储
├── config/             # 配置文件层：所有可变参数
│   ├── config.yaml     # 全局框架配置
│   └── eval_rules.yaml # 评测规则配置（敏感词、权重、校验阈值）
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