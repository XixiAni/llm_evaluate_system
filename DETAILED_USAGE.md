# AI大模型自动化评测系统 详细使用手册
> 最后更新时间：2026年7月 | 版本：v0.1.0

## 1 工具简介
本系统是面向AI测试开发的大模型质量专项评测工具，聚焦大模型输出内容的质量评估，覆盖批量问答、有效性校验、合规检测、幻觉识别、量化打分全流程，采用数据驱动设计，评测用例与代码完全解耦，可用于大模型版本回归测试、效果基线对比、内容安全专项评测等场景。

框架核心组件全部复用两个成熟自动化项目代码[AI接口自动化框架](https://github.com/XixiAni/ai_model_eval_framework)与[Playwright UI自动化框架](https://github.com/XixiAni/playwright_ui_po_autotest_framework)的成熟代码，保证基底稳定性；在此基础上扩展评测专项业务逻辑，所有新增逻辑均基于Python基础语法实现，无额外第三方依赖。
> `AI接口自动化框架` 与 `Playwright UI自动化框架` 后续简称 `项目一` 与 `项目二`

## 2 项目依赖
```bash
pip install -r requirements.txt
``` 
 
>  补充说明：日志模块使用Python内置logging标准库，YAML解析依赖pyyaml，网络请求依赖requests,版本详情见[requirements.txt](requirements.txt)
 
## 3 整体架构设计
 
### 3.1 四层分层架构
 
严格遵循分层解耦设计原则，自上而下单向依赖，下层不感知上层：

| 层级       | 代表文件                       | 核心职责                                   |
| ---------- | ------------------------------ | ------------------------------------------ |
| 入口层     | `main.py`                      | 环境初始化、模块调度、结果输出             |
| 核心业务层 | `core/*.py`                    | 评测核心逻辑：请求、执行、校验、打分       |
| 公共工具层 | `common/*.py`                  | 通用能力：日志、配置读取、通用工具         |
| 配置数据层 | `config/*.yaml`、`data/*.yaml` | 所有可变参数、评测规则、用例数据           |
| 报告输出层 | `report/*.py`                  | 评测结果汇总、导出报告                     |

### 3.2 核心设计原则
 
1. 依赖注入：执行器不直接实例化客户端，外部注入实例，方便替换不同模型实现
2. 异常隔离：单条评测用例异常被限制在单任务内部，不会影响其他用例执行
3. 数据驱动：所有评测用例、规则配置写在YAML文件，与代码完全分离
4. 纯工具类设计：校验、打分、导出模块均为无状态类，仅接收输入返回结果，易扩展
5. 安全规范：密钥通过环境变量读取，日志自动脱敏，无硬编码敏感信息
 
## 4 各模块详细代码讲解
 
### 4.1 公共工具层
 
#### 4.1.1 logger.py 日志工具
 
- 核心能力：
1. 双输出通道：控制台实时打印 + 本地日志文件持久化
2. 按日期拆分：每天自动生成独立日志文件，命名格式  年-月-日.log 
3. 防重复机制：子logger通过传播复用根logger处理器，杜绝日志重复打印
4. 自动建目录：首次运行自动创建 logs/ 文件夹
- 调用方式：各模块通过  get_logger("模块名")  获取独立日志实例
> 复用来源：项目二 100% 完整复用 

#### 4.1.2 yaml_reader.py YAML读取工具
 
- 核心能力：
1. 类方法调用：无需实例化，直接通过类名调用
2. 文件缓存机制：同一份文件全程仅读取一次磁盘，减少IO开销
3. 点式路径取值：支持  llm.base_url  格式嵌套路径读取，无需多层字典索引
4. 环境变量占位符：支持  ${VAR_NAME}  格式，读取时自动替换为系统环境变量值
5. 多环境支持：全局环境标识管理、环境配置读取、配置自动合并（当前版本未主动调用，能力保留）
6. 三类读取入口：
-  get() ：读取全局公共配置
-  get_test_data() ：读取评测数据集文件
-  get_env() ：读取环境差异化配置（预留扩展）
> 复用来源：[项目二](https://github.com/XixiAni/playwright_ui_po_autotest_framework) 100% 完整复用，所有能力完整保留  
 
### 4.2 核心业务层
 
#### 4.2.1 llm_client.py 大模型请求客户端
 
- 核心职责：统一封装大模型接口请求，处理鉴权、超时、重试、异常、响应解析
- 核心方法说明：
1.  __init__  初始化
- 密钥读取优先级：实例化传入 > 系统环境变量 > .env文件
- 初始化Session会话，复用连接池；自动生成脱敏后的鉴权头用于日志打印
- 配置全局超时、重试次数、SSL校验开关
2.  send_post()  通用POST请求
- 底层核心请求方法，完整保留[项目一](https://github.com/XixiAni/ai_model_eval_framework)的三重异常分层、自动重试逻辑
- 仅捕获超时/连接错误进行重试，其他异常直接返回，避免无效重试
- 统一返回  code/data/msg  三层结构，上层代码无需处理异构响应
3.  chat()  快捷对话方法（新增业务封装）
- 基于  send_post  封装的业务快捷方法，无新增底层API
- 自动构造标准对话请求体，自动提取回答内容
- 新增  code=-3  状态码，标记「请求成功但回答提取失败」场景
- 状态码说明：
code值 含义 
0 全流程成功 
-1 网络/HTTP链路故障 
-2 响应内容非JSON格式 
-3 请求成功但提取回答内容失败 
> 复用来源：90% 复用[项目一](https://github.com/XixiAni/ai_model_eval_framework)  AiApiRequest ，仅新增业务快捷方法

#### 4.2.2 validator.py 响应校验模块
 
- 核心职责：对大模型返回的回答内容做基础质量校验，分为有效性与合规性两个维度
- 核心方法说明：
1.  validate_all()  全量校验入口
- 顺序调用有效性校验与合规性校验，返回统一结果字典
2.  _validate_validity()  有效性校验
- 空内容校验：判断回答是否为空或仅空白字符
- 长度校验：回答长度小于阈值标记为无效
- 重复率校验：统计字符出现频率，高重复内容标记为无效
3.  _validate_compliance()  合规性校验
- 敏感词匹配：遍历配置的敏感词列表，检测是否命中
- 核心逻辑与[项目一](https://github.com/XixiAni/ai_model_eval_framework)「关键词包含断言」完全一致，仅将断言改为结果返回
- 设计思想：规则前置，快速过滤低质量回答，减少后续打分模块的无效计算；所有校验规则均可通过YAML配置调整，无需改代码。
> 复用来源：核心匹配逻辑复用[项目一](https://github.com/XixiAni/ai_model_eval_framework)断言工具，改造为返回结果模式

#### 4.2.3 scorer.py 智能评分与幻觉检测模块
 
- 核心职责：对有效回答进行多维度量化打分，并执行规则版幻觉检测
- 核心方法说明：
1.  score_answer()  总评分入口
- 分别计算相关性得分、完整度得分、合规得分
- 按照配置的权重加权计算总分
- 同步输出幻觉检测风险等级与说明
2.  _calc_relevance_score()  相关性得分
- 计算预期关键词的命中比例，命中越多得分越高
- 核心逻辑：关键词命中数 / 总关键词数 × 100
3.  _calc_completeness_score()  完整度得分
- 综合长度占比与字符重合度两个维度
- 避免单纯以长度判断完整度的偏差
4.  _check_hallucination()  规则版幻觉检测
- 核心原理：反向比对，找出回答中存在、但标准答案中不存在的词汇，标记为疑似幻觉
- 使用Python内置 set 集合做差集运算，自动去重提升效率
- 风险等级划分：无新增词汇=无风险；≤3个新增=低风险；>3个=高风险
- 配套原理说明： set  是Python内置基础数据类型，核心特性是元素唯一、支持集合运算（交集、差集、并集），是文本去重、比对场景的通用方案，不属于新技术，和列表、字典同属基础语法范畴。
> 复用来源：关键词匹配逻辑复用断言工具，打分逻辑为基础算术运算
 
#### 4.2.4 batch_runner.py 批量评测执行器
 
- 核心职责：批量加载评测用例，逐条执行全链路评测，收集所有结果
- 核心设计：
1. 依赖注入：接收外部初始化好的LLM客户端实例，不自行创建，实现解耦
2. 异常隔离：单条用例所有异常全部捕获，记录错误信息，不中断批量任务
3. 标准化结果结构：无论成功失败，均生成统一格式的结果字典，方便后续统计导出
4. 执行流程：调用模型 → 有效性校验 → 合规性校验 → 打分与幻觉检测 → 存入结果列表
- 单条用例执行时序：
1. 初始化默认结果字典，异常场景也能正常存入
2. 调用LLM客户端获取回答
3. 请求成功则执行校验与打分，填充对应字段
4. 请求失败则记录错误信息
5. 结果存入总列表，返回单条结果
> 复用来源：80% 复用[项目一](https://github.com/XixiAni/ai_model_eval_framework)  ModelEvalRunner  结构，新增校验打分步骤

### 4.3 报告输出层
 
#### 4.3.1 reporter.py 评测报告导出工具

- 核心职责：将评测结果列表导出为CSV文件，支持Excel直接打开
- 核心特性：
1. 自动创建输出目录，不存在则递归生成
2. 使用  utf-8-sig  编码，Excel打开无中文乱码
3. 输出字段可灵活扩展，新增字段仅需修改表头列表
> 复用来源：90% 复用[项目一](https://github.com/XixiAni/ai_model_eval_framework)  CsvResultExporter ，仅扩展输出字段

### 4.4 入口层
 
#### 4.4.1 main.py 项目主入口
 
- 执行顺序：
1. 加载.env环境变量，定位项目根目录，不受终端工作目录影响
2. 读取全局配置，初始化LLM客户端
3. 加载YAML评测用例集，空用例则直接退出
4. 初始化批量执行器，执行全部评测任务
5. 计算汇总指标：总用例数、成功率、平均分、高幻觉风险数
6. 控制台输出汇总报告，导出CSV结果文件
> 复用来源：执行链路完全复用[项目一](https://github.com/XixiAni/ai_model_eval_framework)  main.py  设计

## 5 完整调用链路与数据流向
 
### 5.1 全链路执行流程
  
1. main.py 加载.env → 读取config.yaml → 初始化 LLMClient
2. main.py → YamlReader.get_test_data() → 加载 eval_cases.yaml 评测用例
3. main.py → 实例化 BatchEvalRunner，注入 LLMClient 实例
4. BatchEvalRunner.run_batch_cases() 循环执行每条用例：
   → LLMClient.chat() 发起请求，返回标准化回答
   → ResponseValidator.validate_all() 执行双维度校验
   → AnswerScorer.score_answer() 执行打分与幻觉检测
   → 生成单条结果字典，加入总结果列表
5. BatchEvalRunner 返回完整结果列表给 main.py
6. main.py 计算汇总统计指标，控制台输出
7. main.py → EvalReporter.export_csv() → 生成CSV评测报告
 
### 5.2 参数传递链路
 
config.yaml / eval_rules.yaml → YamlReader读取 → 各模块初始化时加载参数
                                 ↓
data/eval_cases.yaml → YamlReader读取 → BatchEvalRunner逐条传入执行
                                 ↓
LLMClient → 返回回答内容 → Validator → Scorer → 结果字典 → Reporter导出
 
 
## 6 核心数据结构说明
 
### 6.1 接口统一返回格式
 
```python
  
{
    "code": int,       # 0=成功, -1=网络错误, -2=JSON解析错误, -3=回答提取失败
    "data": Any,       # 成功=回答文本, 失败=原始内容/None
    "msg": str         # 结果描述
}
```
 
### 6.2 单条评测结果格式
 
```python
  
{
    "case_id": str,                # 用例唯一标识
    "case_desc": str,              # 用例业务描述
    "prompt": str,                 # 评测提问
    "execute_timestamp": str,      # 执行时间
    "request_cost_ms": float,      # 请求耗时
    "answer_content": str,         # 模型回答内容
    "success_flag": bool,          # 接口调用是否成功
    "error_msg": str,              # 错误信息
    "is_valid": bool,              # 有效性校验结果
    "is_compliant": bool,          # 合规性校验结果
    "validity_msg": str,           # 有效性校验说明
    "compliance_msg": str,         # 合规性校验说明
    "total_score": float,          # 总分
    "relevance_score": float,      # 相关性得分
    "completeness_score": float,   # 完整度得分
    "hallucination_level": str,    # 幻觉风险等级
    "hallucination_msg": str       # 幻觉检测说明
}
```
 
## 7 快速运行命令
 
```bash
  
# 安装依赖
pip install -r requirements.txt
# 执行全量评测
python main.py
``` 
 
## 8 常见问题排查
 
### 8.1 提示找不到API密钥
 
- 确认根目录存在  .env  文件，且配置了  AI_API_KEY 
- 检查密钥拼写是否正确，前后无多余空格
- 可尝试配置系统环境变量验证
 
### 8.2 YAML文件读取报错
 
-  KeyError ：检查YAML文件中对应层级的字段名是否拼写正确
- 文件找不到：确认config、data目录在项目根目录，文件名与代码中一致
- 格式错误：检查YAML缩进是否规范，必须使用空格不能用Tab
 
### 8.3 CSV报告打开乱码
 
- 确认使用Excel打开，本框架采用utf-8-sig编码，Excel原生兼容
- 若使用其他编辑器打开，手动选择UTF-8编码即可
 
### 8.4 日志重复打印两行
 
- 本框架已复用项目二的日志防重方案，不会出现该问题
- 若自行修改代码后出现，检查是否重复添加了控制台处理器