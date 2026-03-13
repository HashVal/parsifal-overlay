# Knowledge Base Introduction

这个目录用于承载 `simple-rla` 的本地 Knowledge Base（KB）源数据。

当前设计目标不是做一个泛化百科，而是为以下任务提供高质量、可追溯、可人工维护的知识输入：

- Jira case 分析
- 本地日志 / 附件分析
- grounding bundle 构建
- `DEBUG_STEPS` 生成
- RCA 辅助推理

## 设计原则

### 1. 以人工编写 / 人工审阅为先
KB 的核心需求之一是：

- 人能写
- 人能读
- 人能 review
- 人能持续修订

因此当前建议优先采用 **YAML** 作为 authoring format。
运行时可再转换为 JSON-compatible object 供检索与 MCP tool 使用。

### 2. 按“知识在 RCA 中扮演的角色”分类
当前不建议按文档来源分类（例如 wiki / jira / notes），而是按知识用途分类。

当前建议的类型包括：

1. `issue_pattern`
2. `rca`
3. `platform_note`
4. `code_note`
5. `playbook`
6. `workaround`

### 3. KB 不是原始数据仓库
以下内容不应直接作为 KB 主体：

- Jira 原始全文
- 原始聊天记录
- 大段源码全文
- 巨型 wiki 页面整页导入

KB 更适合保存：

- 抽象出的故障模式
- 具体案例的分析沉淀
- 平台知识
- 组件 / 代码语义说明
- 调试 playbook
- workaround / fix note

---

## 类型说明

### 1) `issue_pattern`
**定位：模式层知识（pattern-level knowledge）**

用于表达一类可复用的故障模式。

典型内容：
- canonical symptoms
- canonical signals
- affected platforms / modes
- likely root cause direction
- typical checks
- related RCAs

一句话：
> `issue_pattern` 关注“这类问题通常长什么样、以后遇到怎么识别”。

---

### 2) `rca`
**定位：案例实例层知识（instance-level knowledge）**

用于表达某个具体 case / incident 的分析沉淀。

典型内容：
- case id
- exact environment
- observed evidence
- conclusion
- workaround / fix
- references

一句话：
> `rca` 关注“这次具体发生了什么、证据是什么、最后怎么判断”。

---

### 3) `platform_note`
**定位：平台 / 产品背景知识**

用于描述平台、模式、拓扑、架构约束、术语等背景事实。

典型内容：
- platform facts
- mode definitions
- topology / tile / GT notes
- architectural constraints
- terminology mapping

一句话：
> `platform_note` 提供系统背景，不直接给根因结论，但会影响问题理解和 triage 优先级。

---

### 4) `code_note`
**定位：代码 / 组件语义知识**

用于描述模块、函数、路径、结构体生命周期、依赖关系等。

典型内容：
- component role
- function semantics
- file path meaning
- object lifecycle
- invariants / expectations

一句话：
> `code_note` 帮助模型把 stack trace / function name / file path 转化为更稳定的语义理解。

---

### 5) `playbook`
**定位：调试步骤 / triage 策略知识**

用于描述遇到某类问题时的建议排查路径。

典型内容：
- trigger conditions
- recommended checks
- stop conditions
- escalation paths
- evidence collection order

一句话：
> `playbook` 关注“接下来怎么查”。

---

### 6) `workaround`
**定位：已知规避方式 / fix note**

用于描述已知 workaround、适用条件、风险与替代方案。

典型内容：
- applicability
- workaround steps
- risks / side effects
- superseded-by / fixed-by

一句话：
> `workaround` 关注“现在怎么绕过去、怎么降低影响、什么时候不该再用”。

---

## `issue_pattern` 与 `rca` 的边界

这是当前最关键的边界之一。

### `issue_pattern`
- 是模式
- 是抽象层知识
- 是可跨 case 复用的 failure model

### `rca`
- 是实例化案例的分析沉淀
- 是具体 case 的结论化知识对象
- 保留更多环境与证据上下文

可以用一句话记：

> `issue_pattern` 是模式，`rca` 是案例实例的分析沉淀。

---

## 当前目录布局

```text
knowledge_base/
  introduction.md
  issue_patterns/
    example.yaml
  rca/
    example.yaml
  platform_notes/
    example.yaml
  code_notes/
    example.yaml
  playbooks/
    example.yaml
  workarounds/
    example.yaml
```

---

## Schema 约束建议（当前阶段）

当前示例文件体现的是**推荐结构**，目标是为后续正式 schema / validation 提供基线。

当前建议：

- 枚举字段尽量固定：
  - `kind`
  - `status`
  - `trust.level`
  - `signal.type`
  - `ref.type`
- 检索关键字段应尽量结构化：
  - `platforms`
  - `subsystems`
  - `modes`
  - `signals`
- 长文本字段允许自然写作：
  - `summary`
  - `content`
  - `notes`
  - `conclusion`

后续若引入 `kb_search` / `kb_get` MCP server，应以这些 YAML 文件为 source of truth，加载后做 schema validation，再建立检索索引。
