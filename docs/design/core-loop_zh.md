# 核心闭环

## 目的

这份文档描述的是 `parsifal-overlay` 预期行为中的核心 `reasoning-action-evidence` 闭环。

它不是 workflow YAML 参考文档，不是 runtime 实现说明，也不是 milestone checklist。它的目的是解释：当系统处理一个 debug case 时，高层上应该执行怎样的闭环。

更具体地说，这份文档回答的是：

- 为什么这里必须是闭环，而不是单程 pipeline
- 推理与行动应该如何相互作用
- `DEBUG_STEPS` 在系统里到底扮演什么角色
- 新证据应当如何影响下一轮推理
- 什么时候闭环应继续、停止或升级给人工处理

---

## 为什么需要一个闭环

单次 analysis pipeline 有价值，但对真实 debug 工作来说是不够的。

模型当然可以总结 case 信息、提取看起来合理的 observations、检索相关知识，并生成一份看起来不错的分析报告。但这件事本身并不能证明：模型给出的解释就是真的对。

核心问题在于：debug 不只是“解释信息”，它同样是“主动获取证据”。

在很多 case 里：

- 初始 case 描述并不完整
- 日志只能提供局部可见性
- 同一组症状往往对应多个可能根因
- 平台 / branch / 版本限定条件会显著影响判断
- 下一步真正有价值的事情，不是继续总结，而是拿到新证据

因此，`parsifal-overlay` 的设计不应该停在 analysis generation，而应该形成一个闭环：

- 先基于当前证据做推理
- 判断还缺什么证据
- 主动去收集这些证据
- 再用新证据重新推理
- 最终要么收敛、要么修正、要么停止

这就是它从“报告型 workflow”走向“主动寻找证据的 debug 系统”的关键转折。

---

## 核心闭环概览

从高层看，预期中的闭环是这样的：

```text
Case Intake
  -> Signal Extraction
  -> Knowledge Grounding
  -> Hypothesis Formation
  -> Check Generation
  -> Evidence Execution
  -> Evidence Evaluation
  -> Decision
      -> Confirm
      -> Revise and continue
      -> Blocked / Human-needed
```

这不只是几个 workflow phase 的排列，而是一个决策结构。

关键点在于：每一轮的结果，都必须影响下一步：
- 下一步查什么
- 当前解释是否还成立
- 整个 run 是否还值得继续

---

## 闭环阶段

### 1. Case Intake

闭环起点是拿到足够开始推理的最小 case framing。

通常包括：
- Jira 或 issue 上下文
- 附件和已有 artifact
- 平台和环境线索
- 基本 case 元数据

这一阶段的目的不是深度分析，而是建立最基本的上下文，让系统知道：
- 当前有哪些证据来源
- 第一轮最值得看的信号可能在哪

典型输出包括：
- 规范化后的 case context
- artifact manifest
- 初始平台线索
- 第一轮 triage 所需的附件选择

---

### 2. Signal Extraction

拿到 case 输入之后，下一步是从里面提取有效信号。

这一阶段应当识别：
- 主导故障 signature
- trace anchor
- 重复出现的 observation
- 值得关注的症状
- 不应主导后续推理的噪声

这里的目标不是直接给出最终 RCA，而是把原始 case artifact 压缩成可以支持 hypothesis formation 的结构化证据。

典型输出包括：
- observations
- error signatures
- evidence snippets
- failure-mode hints
- conflict / inconsistency 候选

---

### 3. Knowledge Grounding

只有 signal extraction 还不够。系统还需要借助已有知识来理解这些信号“可能意味着什么”。

这一阶段应提供：
- 匹配的历史 pattern
- platform notes
- RCA 参考
- 术语规范化
- 对“下一步通常应该查什么”的 guidance

这里的 KB 不是绝对权威，而是一个 grounding layer，用来约束推理并把当前 case 连接到历史工程知识。

典型输出包括：
- retrieval context
- 匹配到的 knowledge objects
- platform-specific qualifiers
- 规范化后的术语与 prior-art references

---

### 4. Hypothesis Formation

当证据和 grounding 都到位后，系统需要形成一个显式的工作假设。

这是一个非常关键的步骤。

如果当前解释始终是隐式的，这个 debug 闭环就很难真正成立。系统必须能够明确说出：
- 当前认为最可能的解释是什么
- 为什么这样认为
- 哪些证据在支持这个判断
- 哪些关键证据还缺失
- 哪些较弱的备选解释还不能完全排除

这里的目标不是立刻证明最终答案，而是把当前解释状态显式化到足以支撑下一轮 checks 生成。

典型输出包括：
- 主假设
- 较弱的备选假设
- 当前置信度
- 支撑证据
- 尚未解决的 evidence gaps

---

### 5. Check Generation

一旦有了工作假设，系统就应生成可以验证、削弱或推翻它的检查项。

这也是 `DEBUG_STEPS` 真正重要的地方。

在这个设计里，`DEBUG_STEPS` 不是工作流终点，而是把 hypothesis 翻译成 action 的 planning artifact。

这些 action 通常应拆成两类：
- `DEVICE_CHECK`
- `CODE_CHECK`

这个区分很重要，因为系统需要从两个不同现实中取证：
- 正在运行的设备 / 系统状态
- 代码库 / branch / source path 状态

check 不应该只是泛泛建议，而应该与某个具体假设和某个具体证据缺口绑定。

一个好的 check 至少隐含三件事：
- 为什么要做这个检查
- 它想拿到什么证据
- 哪类结果会支持或削弱当前假设

典型输出包括：
- 结构化 debug plan
- device-side evidence requests
- code-side evidence requests
- 对预期证据解释方式的提示

---

### 6. Evidence Execution

这一阶段真正执行前面计划中的 action。

对于 `DEVICE_CHECK`，可能包括：
- 查询系统状态
- 读取日志
- 检查 driver/module/device facts
- 检查 boot 或 runtime 行为
- 通过 serial 或 SSH 获取现场证据

对于 `CODE_CHECK`，可能包括：
- 搜索源码
- 检查 branch-specific code path
- 定位 symbol、commit、diff 或 reference
- 验证某个怀疑机制是否真的存在于代码里

这是整个系统里最难的部分之一。

reasoning 的上限，很大程度上取决于 action 层返回证据的质量。如果证据管线弱、脏、结构差，整个闭环就会退化。

典型输出包括：
- device evidence pack
- code evidence pack
- execution metadata
- failed checks / blocked actions
- newly collected observations

---

### 7. Evidence Evaluation

当新证据回来以后，系统必须重新评估当前假设。

这一步是 action 真正产生意义的地方。如果证据拿回来了，却没有反过来影响 reasoning，那这个闭环就是假的。

这一阶段需要回答：
- 新证据是否支持当前假设？
- 是否与当前假设矛盾？
- 是否只是部分支持？
- 是否排除了某个备选解释，却还不足以确认主解释？
- 是否暴露了一个之前没有看到的新方向？

这一阶段不应该只是再追加一堆 note，而应真正更新系统当前的解释状态。

典型输出包括：
- hypothesis strengthened
- hypothesis weakened
- hypothesis rejected
- confidence updated
- new evidence gaps identified

---

### 8. Decision

每一轮闭环的末尾，必须是一个决策点。

系统不应该“默认继续”，而应该只在“有明确价值”时继续。

这一阶段必须判断：
- 是否可以基于当前证据给出足够支撑的结论
- 是否应该修正当前假设并进入下一轮
- 是否应该因为阻塞而停止
- 是否需要人工 review / 人工操作
- 是否因为 loop budget 耗尽而结束

这一阶段让整个闭环成为一个有边界的工程过程，而不是无限漫游。

典型输出包括：
- final conclusion
- next-iteration request
- blocked state
- human-needed state
- stop reason

---

## 什么才算“真正的闭环”

一个 workflow 不是因为 phase 多了，就自动变成了真正的 debug loop。

只有在下面三个条件同时成立时，它才是真闭环。

### 1. 假设必须显式
系统必须能够明确说出“它当前认为最可能的解释是什么，以及为什么”。

如果假设不显式，后面的 checks 就会失去目的性。

### 2. Checks 必须绑定假设
系统生成 action，必须是因为存在一个具体的不确定点。

如果 checks 不和 hypothesis 或 evidence gap 绑定，它们就会退化成泛泛探索，而不是 debug。

### 3. 证据必须改变下一步决策
收集回来的证据必须能够改变：
- 置信度
- hypothesis 排序
- 下一步 checks
- 是否终止

如果 action 不影响下一轮 reasoning，那这个 loop 只是表演。

---

## 闭环退出条件

这个闭环必须在明确条件下停止。

### Confirmed
主假设已经被足够支持。

### Sufficiently likely
证据还不到形式化证明的程度，但已经足够支撑一个结论和建议动作。

### Rejected and replaced
当前假设被推翻，系统应该带着新解释进入下一轮。

### Blocked
关键证据无法自动获得，或者某个关键依赖不可用。

### Human-needed
这个 case 需要专家判断、特权操作、实验室介入，或者某种不可自动化的决策。

### Exhausted
达到 loop 上限，或者继续下一轮的边际收益已经过低。

这些退出都应当被视为有效结果。  
blocked 或 human-needed 不是设计失败，而是在 automation 应该停止时给出的正确输出。

---

## 核心闭环里的 `DEBUG_STEPS`

`DEBUG_STEPS` 值得单独强调，因为它最容易被误解。

在这个设计里：

- `DEBUG_STEPS` 不是最终目标
- `DEBUG_STEPS` 不是一段格式化的报告内容
- `DEBUG_STEPS` 是连接 reasoning 和 action 的桥梁

它的职责是把：

- 当前工作假设
- 当前 evidence gaps
- 当前 case context

转化成：

- 具体的 device-side checks
- 具体的 code-side checks
- 一个可执行的 evidence plan

如果把 `DEBUG_STEPS` 当成终点，系统仍然只是报告生成器。  
如果把 `DEBUG_STEPS` 当成活的执行计划，系统才会真正变成 debug loop。

---

## 非目标

这个 core loop 并不意味着：

- 可以无限制自主调用 tools
- 可以无限迭代直到“某个答案突然出现”
- 保证所有 case 都能自动解决
- 取代资深工程师判断
- 默认自动写回知识库
- 把 patch generation 当成核心目标

这个闭环的目标更窄，也更实际：

- 提高证据质量
- 降低重复 debug 成本
- 提高收敛到正确解释的概率
- 在 automation 不该继续时安全停下

---

## 与其他文档的关系

这份文档应与周边 design 文档一起阅读。

- `why-parsifal-overlay.md`
  解释项目为什么存在、解决什么问题

- `core-loop.md`
  解释 reasoning-action-evidence 闭环是如何运作的

- `system-objects.md`
  应解释闭环中的核心概念对象

- `artifact-strategy.md`
  应解释闭环状态如何被表示、分层和交接

这些文档合在一起，分别回答：
- 为什么做
- 高层怎么运转
- 依赖哪些核心概念
- 推理状态如何被组织

---

## 结语

`parsifal-overlay` 的核心，不是一份报告，也不是一条静态 workflow。

它的核心是一个有边界的闭环，连接了：
- case understanding
- signal extraction
- knowledge grounding
- explicit hypothesis formation
- targeted action
- evidence collection
- evidence-based revision
- conclusion or escalation

也正是这一点，把它从一个“产出文档的 pipeline”，变成了一个“主动寻找证据的 debug 系统”。
