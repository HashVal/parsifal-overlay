# 系统对象

## 目的

这份文档定义 `parsifal-overlay` 中的主要概念对象。

它的目的不是定义具体 schema，也不是解释 workflow YAML 语法，而是为设计讨论、实现规划以及后续 spec 工作提供一套共享的对象模型。

更具体地说，这份文档试图澄清：

- 系统在 debug 过程中真正推理的对象是什么
- 哪些对象只是为了组织执行而存在
- 哪些对象只是为了在 step 之间传递状态而存在
- 哪些概念最容易混淆，因此必须明确区分

这份文档应被理解为概念模型，而不是最终接口契约。

---

## 为什么系统对象重要

一个 debug 系统如果没有清晰的对象模型，很快就会变得混乱。

如果内部概念一直是隐式的，就很容易混淆这些关键区别：

- case context 和 workflow state 的区别
- signal 和 observation 的区别
- hypothesis 和 root cause 的区别
- check 和 step 的区别
- evidence 和 knowledge 的区别
- decision 和 conclusion 的区别
- object 和 artifact 的区别

这些区别之所以重要，是因为 `parsifal-overlay` 不只是一个 workflow engine。它同时还是一个推理系统、一个证据收集系统，以及一个受知识约束的 debug 系统。

为了让设计和实现保持一致，系统需要一套统一词汇。

---

## 对象分层

`parsifal-overlay` 里的对象可以分成三层来理解：

### 1. Domain / Reasoning Objects
这些是系统在 debug 过程中真正推理的对象：
- `Case`
- `Signal`
- `Observation`
- `KnowledgeObject`
- `Hypothesis`
- `Check`
- `Evidence`
- `Decision`

### 2. Execution / Orchestration Objects
这些是系统用来组织和执行 workflow 的对象：
- `Workflow`
- `Phase`
- `Step`
- `Run`
- `Iteration`

### 3. Representation / Transport Objects
这些是系统用来存储、传递和暴露状态的对象：
- `Artifact`
- `HandoffBundle`
- `VisibilityBoundary`

第一层描述的是系统试图理解什么。  
第二层描述的是系统如何执行这些工作。  
第三层描述的是状态如何被表示与传递。

---

## Domain / Reasoning Objects

### Case

`Case` 是系统要处理的外部问题实例。

典型来源包括：
- Jira issues
- bug reports
- test failure reports
- 外部给定的 debugging task

一个 case 通常包含或指向：
- issue summary 和 description
- attachments
- platform hints
- reported symptoms
- branch / version context
- environment clues

Case 是系统的入口对象。它是源问题本身，而不是解释。

---

### Signal

`Signal` 是从原始材料中提取出来的局部证据点或异常点。

典型例子包括：
- 一个 error signature
- 一个 call trace anchor
- 一条可疑的 timeout 日志
- 一个 version mismatch 线索
- 一个 platform-specific error marker

Signal 通常具有这些特征：
- 窄
- 局部
- 直接贴近原始输入
- 它之所以重要，是因为它提示“这里值得关注”

Signal 还不是一个完整的结构化 case 判断，它更接近“有意义的证据点”。

---

### Observation

`Observation` 是系统基于一个或多个 signal 以及其他原始输入整理出来的结构化事实陈述。

典型例子包括：
- 故障发生在某个特定初始化阶段
- regression 只出现在某个 branch
- 多份日志都指向同一个 subsystem boundary
- 不同环境中可见症状之间存在不一致

Observation 比 signal 更结构化。一个很有用的理解方式是：

- signal 是点
- observation 是由点整理成的陈述

Observation 往往是 hypothesis formation 的直接输入。

---

### KnowledgeObject

`KnowledgeObject` 是从知识库中检索到的结构化知识单元。

例如：
- issue patterns
- platform notes
- RCA notes
- playbooks
- workaround references
- code notes

Knowledge object 不是当前 case 的现场证据，而是外部 grounding 材料。

它的作用是提供：
- 术语规范化
- 历史模式
- platform-specific qualifiers
- 可能的 failure mechanisms
- 对“下一步值得查什么”的提示

Knowledge object 必须和当前 case 中收集到的 evidence 明确区分开。

---

### Hypothesis

`Hypothesis` 是系统对当前 case 的工作解释。

它不是真正的最终真相，而是当前最值得用来驱动下一步行动的解释。

一个 hypothesis 应当显式说明：
- 系统当前认为的解释是什么
- 为什么这么认为
- 哪些证据在支持它
- 哪些关键证据还缺
- 哪些备选解释还没有被排除
- 当前置信度如何

Hypothesis 是整个闭环的核心对象之一。没有它，checks 会失去目的，evidence 也无法被明确评价。

Hypothesis 应与 root cause 区分：
- hypothesis 是暂时性的
- root cause 是更晚、更稳定的解释结果

---

### Check

`Check` 是系统为了验证、削弱或推翻 hypothesis 而生成的 debug action。

Check 是系统中主要的 action 对象。

至少可以区分两类：
- `DEVICE_CHECK`
- `CODE_CHECK`

Check 不应该只是泛泛建议。它应与以下内容绑定：
- 一个具体 hypothesis
- 一个具体不确定点
- 一个具体 evidence need

一个有价值的 check 至少隐含：
- 为什么需要它
- 它想收集什么证据
- 哪类结果会如何影响当前 hypothesis

Check 在概念上不同于 workflow step。Check 属于推理域；step 属于执行结构。

---

### Evidence

`Evidence` 是通过 checks 或其他取证动作返回的材料。

典型例子包括：
- 新获取的 runtime logs
- device state facts
- module / driver status
- code-path findings
- branch-specific code differences
- commit / symbol / reference 结果

Evidence 是 hypothesis 能被加强、削弱、推翻或修正的基础。

Evidence 应与 observation 区分：
- evidence 是被收集或引用的材料
- observation 是基于 evidence 和 signals 所整理出来的陈述

一个 observation 可能由多个 evidence 支撑。一个 evidence 也可能同时支持多个 observation 或 hypothesis。

---

### Decision

`Decision` 是一轮 iteration 结束时 loop-level 的结果对象。

它表达的是：系统下一步应该做什么，而不只是“当前相信什么”。

典型 decision 包括：
- confirm
- revise
- blocked
- human-needed
- exhausted

Decision 不同于 narrative conclusion。Conclusion 是面向人的输出内容；Decision 是控制闭环如何继续的对象。

正是这个对象，让 loop 保持有界。

---

## Execution / Orchestration Objects

### Workflow

`Workflow` 是顶层执行结构，用来定义一个 case 如何被处理。

它规定：
- 有哪些 phases
- 它们如何排序
- 从哪里开始执行
- 如何在阶段之间迁移

Workflow 本身不是 debug 语义对象，它是组织 debug 语义对象处理过程的结构。

---

### Phase

`Phase` 是 workflow 里的分组单元。

它把一组相关 steps 聚成一个更大的执行阶段，例如：
- intake
- analysis
- evidence execution
- summarization
- closure

Phase 有助于建立执行边界，但它不应与 hypothesis、evidence 这类推理对象混淆。

---

### Step

`Step` 是当前 workflow 模型中的最小执行单元。

一个 step 通常会：
- 消费可见输入或 artifacts
- 执行一种类型的工作
- 产出新的 artifacts 或 state updates

典型例子包括：
- tool step
- LLM step
- LLM tool step
- deterministic step

Step 不等于 check：
- step 是执行单元
- check 是在执行过程中被产出或消费的 debug action 对象

---

### Run

`Run` 是某个 workflow 针对某个 case 的一次具体执行实例。

一个 run 包括：
- 一个 case context
- 一条 workflow path
- 一组 artifacts
- 一段 execution history

同一个 case 在不同时间、不同配置下，可以有多个 runs。

---

### Iteration

`Iteration` 是一个 run 中的一轮 reasoning-action-evidence cycle。

它不应被简单等同于：
- 一个 step
- 一个 phase
- 一个 artifact

Iteration 是逻辑闭环单元，不一定直接对应某个 runtime 单元。

这点很重要，因为概念上的 debug loop 可能跨多个 phases 和 steps。

---

## Representation / Transport Objects

### Artifact

`Artifact` 是某种系统状态的结构化表示，它会被存储、在 step 间传递，或者暴露给后续执行使用。

Artifact 可以表示：
- observations
- hypotheses
- evidence packs
- summaries
- handoff bundles
- intermediate structured outputs

Artifact 本身不是 domain object，而是一个或多个 domain object 在 workflow 可执行形态中的表示。

这个区别很重要：
- object = 语义概念
- artifact = 被传递的表示形式

---

### HandoffBundle

`HandoffBundle` 是一种特殊 artifact，用于把选定的结构化状态从一个 phase 或 layer 传递到另一个。

它的目的包括：
- 在不做 lossy summarization 的前提下保留重要输出
- 控制哪些信息会被带到下游
- 明确 phase boundary

当下游 reasoning 应该消费“整理好的结构化结果”，而不是重新打开所有上游原始上下文时，handoff bundle 非常有用。

---

### VisibilityBoundary

`VisibilityBoundary` 是决定哪些 artifacts 对哪些后续 steps 可见的规则或机制。

这个对象之所以存在，是因为并不是所有下游 step 都应该看到所有上游结果。

Visibility boundaries 用来保证：
- 职责分离
- 上下文卫生
- 减少 prompt pollution
- 显式 handoff 设计

Visibility 不是业务语义对象，但它会强烈影响 reasoning 质量。

---

## 对象之间的关系

从高层看，这些对象的关系大致是：

```text
Case
  -> Signals
  -> Observations
  + KnowledgeObjects
  -> Hypothesis
  -> Checks
  -> Evidence
  -> Decision
```

这些 domain objects 又会被 execution objects 组织起来：

```text
Workflow
  -> Phases
  -> Steps
  -> Artifacts
  -> Run
  -> Iterations
```

更完整地说：

- `Case` 提供源问题
- `Signals` 从原始 case 材料中被提取出来
- `Observations` 把这些 signals 组织成可用陈述
- `KnowledgeObjects` 用历史知识为解释提供 grounding
- `Hypothesis` 提供当前工作解释
- `Checks` 从 hypothesis 及其 evidence gaps 派生
- `Evidence` 是执行 checks 后返回的材料
- `Decision` 决定下一轮闭环动作
- `Artifacts` 把这些状态带入 workflow 执行过程
- `Workflow`、`Phase`、`Step` 组织整体执行
- `Run` 和 `Iteration` 把这个过程定位到具体执行历史中

---

## 第一类对象与支撑对象

不是所有对象都同样核心。

### 第一类闭环对象
这些对象定义了 debug loop 的核心：
- `Hypothesis`
- `Check`
- `Evidence`
- `Decision`

正是这些对象，让系统成为真正的 reasoning-action-evidence 系统，而不只是报告生成器。

### 支撑推理对象
这些对象为闭环状态提供原始材料：
- `Case`
- `Signal`
- `Observation`
- `KnowledgeObject`

### 执行对象
这些对象负责组织处理过程：
- `Workflow`
- `Phase`
- `Step`
- `Run`
- `Iteration`

### 表示对象
这些对象负责在 workflow 中传递结构化状态：
- `Artifact`
- `HandoffBundle`
- `VisibilityBoundary`

---

## 关键区别

### Case vs Run
- `Case` 是外部问题实例
- `Run` 是处理该 case 的一次执行实例

### Signal vs Observation
- `Signal` 是局部证据点
- `Observation` 是由一个或多个 signal 整理成的结构化陈述

### KnowledgeObject vs Evidence
- `KnowledgeObject` 来自 KB
- `Evidence` 来自当前 case 或主动 checks

### Hypothesis vs Root Cause
- `Hypothesis` 是暂时性、活跃在 loop 中的解释
- `Root cause` 是更晚、更稳定的解释结果

### Check vs Step
- `Check` 是 debug action 对象
- `Step` 是 workflow engine 里的执行单元

### Phase vs Iteration
- `Phase` 是执行分组
- `Iteration` 是逻辑上的闭环轮次

### Object vs Artifact
- `Object` 是语义概念
- `Artifact` 是这个概念在 workflow 中可见、可传递的表示

### Decision vs Conclusion
- `Decision` 决定下一步怎么办
- `Conclusion` 面向人类表达“我们学到了什么”

---

## 与其他文档的关系

这份文档建议与以下文档一起阅读：

- `why-parsifal-overlay.md`
  用来理解项目为什么存在、问题背景是什么

- `core-loop.md`
  用来理解 reasoning-action-evidence 闭环如何运作

- `system-objects.md`
  用来理解这里定义的对象模型

- `artifact-strategy.md`
  用来理解这些对象如何被表示、暴露与交接

这些文档放在一起，分别回答：
- 为什么要做
- 闭环怎么运转
- 系统实际上在操作什么
- 状态如何在执行阶段间流转

---

## 结语

`parsifal-overlay` 需要的不只是 workflow，还需要一套稳定的概念模型。

系统并不只是“执行一堆 steps”，它实际上是在操作一组互相关联的对象：
- cases
- signals
- observations
- knowledge objects
- hypotheses
- checks
- evidence
- decisions

这些对象再通过 workflows、phases、steps、runs 和 artifacts 被组织起来。

只有当对象模型清楚，推理、执行、表示这三层才能既相互区分，又能拼成一个连贯的 debug 系统。
