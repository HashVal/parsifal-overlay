# 讨论 agent harness

这篇文档记录了一轮 moonshot 风格的设计讨论，主题是 `agent harness` 这个概念，以及它如何映射到当前和未来的 `simple-rla`。

它是探索性的，不是规范性的。它的目标是完整保留这轮讨论的推理链条，而不是把它压缩成一条短 note。

---

# 核心判断

这一轮讨论的核心问题是：

> 如果用 agent-harness 圈子的语言去看 `simple-rla`，它现在到底是什么、正在变成什么，以及哪些 harness 概念已经可以自然映射进去？

最后收敛出来的判断是：

> `simple-rla` 现在表面上仍然更像一个 workflow engine，
> 但它的架构演化方向已经明显在往一个面向调试问题的 domain-specific debug-agent harness 走。

换句话说：

- 当前外壳：workflow runtime
- 演化方向：debug / analysis agent harness

---

# 什么是 agent harness

这轮讨论采用的工作定义是：

> agent harness 不是 agent 的核心智能本体，而是包在它外面的那层系统壳。

它负责的不是模型“会不会想”，而是把一个会想的模型变成一个能稳定工作的系统。

它通常覆盖这些内容：

- context lifecycle management
- orchestration
- tool mediation
- memory / state handling
- validation
- observability
- recovery
- policy / constraints

可以压成一句话：

> harness 是把“会思考的模型”变成“能稳定做事的系统”的那层基础设施。

这也是为什么在很多真实系统里，agent 的强弱差异往往不只来自模型本身，而更多来自包在模型外面的 harness 质量。

---

# `simple-rla` 现在更像 workflow engine，还是 harness？

这一轮讨论最后的回答是：

> 如果今天非要二选一，`simple-rla` 仍然更接近 workflow engine。
>
> 但它已经不只是一个普通 workflow engine 了，而且很明显正在往 debug-agent harness 的方向长。

## 为什么它现在仍然更像 workflow engine

因为当前系统里最成熟、最显式的对象，仍然主要是：

- workflow
- phase
- step
- artifact
- runtime
- `llm_step` / `llm_tool_step`
- MCP-backed tool execution

这套词汇和结构，本身就带着很强的 workflow-engine 气质。

它的 runtime 看起来仍然主要是在执行：

- YAML workflow definitions
- phase/step orchestration
- structured execution flow

所以就“当前外壳”而言，把它描述为 workflow runtime 仍然是最准确的。

## 为什么它已经开始变成别的东西

但与此同时，`simple-rla` 已经长出了一批明显超出传统 workflow engine 的东西。

这轮讨论里识别出的信号包括：

- structured artifacts
- analysis handoff discipline
- `DEBUG_PLAN`
- `CODE_CHECK` / `DEVICE_CHECK`
- check-execution substrate
- evidence integration
- closure direction
- 甚至包括像 `skill grounding` 这样的 moonshot 想法

这些都已经不只是“把步骤按顺序跑完”了。

它们更像是在搭一层：

> 面向调试 / 分析 agent 的专用运行壳层

这就已经比单纯 workflow runner 更接近 harness。

更准确的一句话是：

> `simple-rla` 目前是一个以 workflow-runtime 为外壳、正在演化成 debug-agent harness 的系统。

---

# harness 圈里三个常见概念如何映射到 `simple-rla`

这一轮讨论接着看了 harness 圈子里经常出现的三个概念：

1. 渐进式披露（progressive disclosure）
2. 仓库即事实源（repo as source of truth）
3. 机械化约束（mechanized constraints）

最后的判断是：

> 这三个概念都能映射到 `simple-rla`，而且不是硬套。
> 但三者的成熟度明显不一样。

---

# 仓库即事实源（repo as source of truth）

## 核心含义

这个概念在讨论里被理解为：

> 关于系统结构、约束、设计意图、项目状态的重要事实，应尽量沉淀在仓库里，而不是只存在于聊天记录、人脑记忆或临时 prompt 中。

## 它如何已经很好地映射到 `simple-rla`

这被认为是三者中目前做得最好的一项。

讨论里给它打的粗略分数是：

> **8/10**

支撑这个判断的点主要包括：

- 关键系统定义已经放在 `docs/spec/`
- milestone definitions 放在 `docs/roadmap/simple-rla-roadmap.md`
- execution/progress summaries 放在 `docs/roadmap/simple-rla-status.md`
- implementation planning 保持在 `simple-rla/TODO.MD`
- workflow definitions、runtime config、artifact behavior 都在 repo 管理文件里
- moonshot ideas 也开始沉淀进 `docs/moonshot/`

这意味着，项目内部已经形成了一套相对清楚的事实分层：

- spec
- roadmap
- status
- implementation board
- code/runtime behavior

如果用 harness 的语言来讲，这已经是一个相当强的 “repo as truth” 模式。

## 还缺什么

讨论里认为主要还缺两块。

### 1. strategy-layer facts 还没有成为 repo 里的一级事实

现在 repo 里已经有：

- system facts
- milestone facts
- implementation facts

但还缺一个稳定存在于仓库里的“策略层事实”集合，例如：

- 可复用的 debugging strategies
- troubleshooting playbooks
- domain anti-patterns
- 类似 skill 的 planning priors

前一轮关于 `skills` 的 moonshot 讨论，其实正好把这个缺口暴露出来了。

### 2. runtime learning 还不能系统性地回流到 repo

现在项目已经有 observability 和 dump 机制，但还没有一个成熟机制来回答：

- 哪些 runtime lessons 值得长期保留
- 哪些新的 domain insight 应该升级成 repo-level fact
- 系统运行经验如何反哺成稳定知识

所以这一项已经很强，但还没有完全闭环。

---

# 机械化约束（mechanized constraints）

## 核心含义

这轮讨论里收敛出来的定义是：

> 重要规则不应只存在于文档、人脑或者 prompt wording 里，
> 而应该尽可能变成机器可以 validate、reject、audit 的约束。

可以再压缩一句：

> 机械化约束的目标，是把规则从“建议”变成“系统边界”。

之所以把它视为一个很重要的 harness 概念，是因为 agent 系统一旦把关键边界只留在“大家都知道”的层面，就很容易随着复杂度上升而退化。

## 机械化约束的四层

讨论里把这个概念拆成了四层。

### 1. Structural constraints
对象必须先变成机器可以识别的结构。

例如：

- `DEBUG_PLAN` 不能只是 prose
- checks 应该有显式 typed fields
- outcomes 应该来自有限词表

如果没有结构，后面就谈不上机械化。

### 2. Validation constraints
对象存在之后，系统还要能检查：

- shape 是否正确
- 必填字段是否齐全
- type 是否正确
- semantic boundary 是否被违反

这包括：

- schema validation
- contract validation
- invariant checking

### 3. Execution constraints
系统不仅要会检查，还要能在执行层面阻断。

例如：

- invalid tool call 要被 block
- malformed check 不能进入 execution
- closure input 不完整应该被 reject
- max tool calls / max turns 这类硬预算要强制执行

### 4. Audit constraints
系统还要留下证据说明发生了什么：

- 哪条规则被触发
- 为什么 reject
- 哪个对象违反了边界
- 当时的相关状态是什么

否则很多东西只是隐藏的 hardcoding，还谈不上 durable engineering。

## `simple-rla` 已经体现了哪些机械化约束

这一项在讨论里被认为：

- 已经有真实基础
- 但离完整还差一段距离

粗略完成度打分是：

> **5/10**

但工程优先级被认为是三者里最高的：

> **9/10 priority**

### 目前已经有的 mechanization signs

#### 1. Structured output / parsed result discipline
系统已经不再完全依赖 unconstrained prose，而是在往：

- parsed outputs
- structured `StepResult`
- 模型输出必须进入 runtime-consumable objects

这个方向上收敛。

这就是一个真实的 mechanized-constraint 信号。

#### 2. Tool permission / registry / execution limits
runtime 不是让模型随便调任何工具。

系统已经有：

- tool registry
- permission
- exposure
- 以及像 max tool calls / turns 这样的预算约束

这意味着行为空间是在 runtime 里被收窄的，而不是只靠 prompt 文案劝导。

#### 3. Artifact and phase boundaries
后续 phase 不必直接吃所有 raw context，而是逐渐通过 bounded handoff artifacts 和中间表示来对接。

这也是机械化约束的一部分，因为它限制了下游阶段被允许消费的内容边界。

#### 4. Typed check and outcome directions
显式对象像：

- `CODE_CHECK`
- `DEVICE_CHECK`

以及有限词表像：

- `COMPLETED`
- `INCONCLUSIVE`
- `BLOCKED`
- `FAILED`
- `DEFERRED`

这些都说明系统正在往更强的 typed world 走。

这种受限词汇表，本身就是后续 validation 的前提。

#### 5. 工程文档职责分离
即使在 runtime 之外，repo 里也已经出现了一些“弱机械化”的边界划分：

- `simple-rla/TODO.MD` = implementation checklist and execution board
- `docs/roadmap/simple-rla-roadmap.md` = milestone definitions
- `docs/roadmap/simple-rla-status.md` = progress and state summary

这虽然还不是 runtime enforcement，但已经是结构化边界的体现。

## 还需要补强什么

讨论里认为，最大的缺口主要有这些。

### 1. `DEBUG_PLAN` 还没有被强机械化
现在在 spec 层面，关于 `DEBUG_PLAN` 是什么、应该怎么用，已经有不少清晰共识。

但系统层面还明显缺像下面这样的 enforcement：

- invalid `DEBUG_PLAN` rejection
- illegal check family rejection
- missing critical fields rejection
- 把 supporting capability domains 和 primary check types 混淆的 plan 应被 reject

也就是说，它现在更像 design intent，还不是 runtime boundary。

### 2. Assembled checks 还没有 fully hardened
M3.1 方向已经想清楚了，但这层现在看起来还没有 fully enforced。

理想状态下，未来的 `CODE_CHECK` / `DEVICE_CHECK` assembled objects 应该具备：

- 明确 machine-readable contracts
- 完整 target / scope / purpose / evidence-linkage
- invalid object 在 execution 之前就被 reject

### 3. Evidence integration 和 closure 的边界还没有被机器守住
现在架构上已经明确区分了：

- integration / packaging
- evaluation / closure

但如果这个边界不被 machine-enforced，后面很容易出现 closure semantics 被偷偷塞进 evidence integration 层。

一个更 hardened 的系统里，integrated evidence layer 不应该能够：

- 做 terminal judgment
- 携带 closure-specific decision fields
- 悄悄退化成 closure logic

### 4. 很多 semantic boundaries 仍然主要活在人类共识里
讨论里明确提到的例子包括：

- supporting capability domains are not peer check types
- `REFRAME` is non-terminal
- `correct_rca`, `BLOCKED`, `HELP_NEEDED` are terminal
- M3 is substrate only
- M3.x contains realizations, not substrate

这些现在在设计语言里已经很清楚，但还没有被强编码成 machine-checkable invariants。

### 5. architecture-level guarding 还不够
系统后面还需要更多工程层面的 mechanized protection，例如：

- forbidden legacy dependency usage
- document-responsibility linting
- phase-responsibility guards
- contract invariant tests
- module boundary 的结构检查

否则一个项目很容易慢慢退回 ad hoc flexibility。

## 最后的 mechanized-constraints 判断

这轮讨论里一句比较压缩的总结是：

> `simple-rla` 已经开始从 prompt discipline 走向 contract discipline，
> 但它现在还主要处在“结构雏形 + 文档共识”的阶段，
> 距离 fully hardened 的 machine-enforced boundaries 还有明显距离。

这也是为什么机械化约束被认为是当前最值得优先加强的一块。

---

# 渐进式披露（progressive disclosure）

## 核心含义

这一段讨论最初是从一个很实践化的直觉开始的：

> 一个 case 里常常会同时存在多个信号。
> 如果把所有信号一次性都暴露给模型，模型的注意力就会被这些竞争信号分散。
> 所以某个阶段应当只补充与当前主信号强相关的上下文，让模型把注意力锁在一个更小、更高价值的问题空间上。

这一直觉在讨论里被明确判定为：

> 对，而且已经抓到了 progressive disclosure 的第一层核心。

也可以压成一句：

> 渐进式披露的一个重要核心，确实就是控制模型此刻看到的东西，避免多个异质信号同时争夺它的注意力。

但讨论接着又把这个直觉扩展成了一个更完整的系统定义。

## 渐进式披露不只是 query-context trimming

讨论里最后澄清出来的立场是：

> 渐进式披露可以通过在共享状态的多轮系统里控制每次模型调用的 query context 来实现，
> 但它不等于单纯的 prompt trimming。

这个区别很重要。

如果把这个概念收缩成“只是少给模型一些 token”，那它真正的系统意义就丢了。

更完整的版本是：

> 渐进式披露意味着：按阶段控制模型被允许看到什么、被允许解决什么问题、以及被允许使用什么行动/能力空间。

## 渐进式披露的三层

讨论里把这个概念分成了三个维度。

### 1. Context disclosure
这是最直观的一层，也最接近最初的用户直觉。

在一个有共享长期状态的系统里，每次模型调用其实不需要看到整个 global state。

query 可以被构造成只带上：

- relevant artifacts
- relevant summaries
- relevant evidence
- relevant hypotheses
- relevant recent results

而排除掉：

- irrelevant noise
- unrelated branches
- 已经不适合当前 phase 的 raw inputs

这就是最直接的 progressive disclosure。

### 2. Task disclosure
即使上下文不变，系统也还可以通过限定当前 phase 的责任范围来约束模型。

例如某次调用只允许它做：

- analysis normalization
- hypothesis shaping
- check planning
- execution packaging
- closure judgment

而不是把这些脑力活一次性揉在一起。

所以 progressive disclosure 还意味着：

> 在每一步只暴露当前任务目标，而不是把整条端到端推理负担都压到每一轮里。

### 3. Capability disclosure
第三层经常被忽略。

系统还可以渐进式地暴露：

- 哪些 tools 是可见的
- 哪些 check families 是可用的
- 哪些 action types 当前允许
- 哪些 execution surfaces 当前开放

这意味着 progressive disclosure 也可以表现为 staged capability exposure。

某个 phase 下，模型面对的 capability slice 可能故意比别的 phase 窄得多。

## shared global state 与 local query context 的关系

讨论里特别强调了一个区分：

- 系统可以有共享的全局 case state
- 但每一轮 query 不需要把这份全局状态全量暴露给模型

这就得到了一个更精确的表达：

> 渐进式披露通常是在一个 shared-state 的多轮系统上，通过对每次调用分别控制 query context、task objective 和 capability exposure 来实现的。

这也正好把最初那个“是不是就是控制 query context”的直觉，和更完整的系统定义接起来了。

## `simple-rla` 里已经有哪些 progressive disclosure 的雏形

讨论里的判断是：`simple-rla` 已经有一些明显的结构性影子，但还没有把它上升成显式设计原则。

粗略打分是：

> **4/10**

工程优先级大概是：

> **8/10 priority**

### 现有信号

#### 1. Phase / step layering
系统已经不是把整件事当成一个无分化的大模型调用来做。

#### 2. Bounded artifacts and analysis handoff
后续阶段可以消费 summary / normalized outputs，而不是总是直接面对全量 raw analysis material。

这已经是 context disclosure 的一个具体形式。

#### 3. `DEBUG_PLAN -> assembled checks -> integrated evidence`
这条 staged pipeline 本身就是一种披露：

- reasoning 不在一个地方一次性完成
- execution surface 不是一次性全部打开
- 后续阶段消费的是更 bounded、更 specialized 的表示

## 还缺什么

讨论里识别出来的主要缺口包括：

### 1. 还没有 explicit context-disclosure policy
项目现在有结构，但还没有正式 doctrine 去明确：

- 哪个 phase 能看哪类 artifacts
- 哪些 context 是故意延迟披露的
- 哪些 raw evidence 一旦被 summary 后，就不应该再直接暴露给下游 phase

### 2. Strategy disclosure 还只是 moonshot
前一轮关于 `skill grounding` 的讨论，其实天然契合 progressive disclosure，因为它意味着 planning phase 只注入 relevant strategic priors，而不是把所有 strategy 一次性塞进去。

但这目前还只是一个 moonshot 想法，没有进入真实系统。

### 3. Capability disclosure 还不够语义化
系统已经有 tool permission / tool registry，但还没有形成一个强 phase-conditioned capability-slice model。

也就是说，系统现在还没有真正做到：

> 在这个 phase 里，只允许这一个特定 action surface 被看到

## 最后的 progressive-disclosure 判断

这轮讨论里一个压缩得比较好的表述是：

> 渐进式披露的第一层核心，确实是减少竞争信号导致的注意力碎裂；
> 但它不只是 context trimming，还包括 task objective 和 capability space 的渐进开放。

也就是说，最初的用户直觉是对的，但只对应了第一层。

更完整的架构级解释是：

> 渐进式披露 = 分阶段暴露最相关的 context、task 和 capability，
> 让模型在一个 bounded local problem space 里收敛，而不是在整个 global problem field 中发散。

---

# 与前一轮 `skills` moonshot 的关系

前一轮关于 `skills` 的 moonshot，其实和这轮 harness 讨论是直接连着的。

那一轮讨论里得出的结论是：

- `skill` 不是 workflow
- skill 更像 reusable domain strategy package / troubleshooting playbook
- 如果未来引入 `simple-rla`，最自然的落点应该是在 planning / assembly 上游，而不是 runtime primitive 层

这里最关键的连接点，就是 `skill grounding` 这个想法。

那一轮里把它表述成：

- `kb_ground_case` = fact grounding
- `skill_grounding` = strategy grounding

意思是，未来的 `DEBUG_PLAN` 不只应该受到这些东西的塑形：

- case-local evidence
- hypothesis state
- KB grounding

还应该受到一组 strategy priors 的塑形，例如：

- matched skills
- recommended directions
- recommended check templates
- evidence expectations
- reframe triggers
- anti-patterns

这个想法之所以和 harness 讨论高度相关，是因为它恰好填补了两个缺口：

- repo-as-source-of-truth：strategy knowledge 可以变成 durable repo knowledge
- progressive disclosure：planning phase 只暴露 relevant strategies，而不是一锅端全部策略库

所以 `skills` 那轮 moonshot 不是一个孤立的话题，而是这轮 harness 讨论的一个前导层。

---

# 最后的评分

讨论最后给这三个 harness 概念分别打了“当前完成度”和“工程优先级”两个分数。

## 当前完成度

- **repo as source of truth: 8/10**
- **mechanized constraints: 5/10**
- **progressive disclosure: 4/10**

## 下一步工程优先级

- **mechanized constraints: 9/10**
- **progressive disclosure: 8/10**
- **repo as source of truth: 6/10**

这就导向一个很清楚的实践判断：

> 当前最强的 trait 是 repo-as-source-of-truth。
>
> 当前最值得优先补的是 mechanized constraints。
>
> progressive disclosure 已经有结构影子，但还没有被提升成正式组织原则。

---

# 最后的核心结论

整轮讨论最终收敛成了下面这些核心判断：

1. `simple-rla` 今天最准确的描述仍然是 workflow-runtime shell。
2. 它的设计轨迹已经明显在往 domain-specific debug-agent harness 走。
3. repo-as-source-of-truth 是当前系统里最强的 harness-like trait。
4. mechanized constraints 是下一步最值得强化的方向，因为很多关键边界仍然主要存在于 spec、TODO 和人类共识里，而不是 runtime-enforced contracts。
5. progressive disclosure 首先被正确理解成“在竞争信号之间做 attention management”，但它完整的系统含义还包括 task objective 和 capability space 的分阶段披露。
6. 前一轮 `skills` moonshot 很自然地嵌进了这一图景里，作为未来 planning 的 strategy-grounding layer。

最后可以压成一小段话：

> `simple-rla` 已经长出了一些明显的 harness-shaped structures，
> 但还没有完全跨过从 workflow engine 到 harness 的那条线。
> 当前最清晰的推进路径是：把 mechanized constraints 硬起来，把 progressive disclosure 明确成原则，并在未来让 repo-resident strategy knowledge 通过 skill grounding 进入 planning。
