# 00 · Workflow Overview

## 这套 workflow 是什么

这不是一条“把品牌材料直接改成正文”的 prompt，而是一条分阶段执行的写作 workflow。

默认目标不是一次性把所有规则塞进上下文，而是：
1. 先判断当前阶段
2. 再只读取下一步真正需要的文档
3. 产出一个小而稳的中间件
4. 再进入下一阶段

## 何时使用

当出现以下任一情况时使用：
- 需要写软文、品牌稿、展前稿、品牌材料改写
- 需要把客户问答、产品资料、采访提纲、新闻稿，改成更像文章的内容
- 需要让“宣传信息”藏在信息推进里，而不是一眼像通稿
- 需要更稳定地复现写作质量，而不是临场 freestyle

## 不适用场景

不要硬套到这些任务：
- 强销售转化文案
- 直播带货口播
- 海报文案 / slogan
- 官方声明 / 董事长致辞 / 强表态稿

## 非品牌稿适配

这套 workflow 的术语默认按品牌稿写。用于技术文章、项目介绍等非品牌场景时，做以下映射：

| 品牌稿术语 | 技术文章对应 |
| --- | --- |
| 钩子 | 为什么现在写 |
| 前置卖点 | 最该被记住的一件事 |
| 品牌出场 | 项目 / 系统首次出现 |
| 主推对象 | 核心论点或设计选择 |
| 陪衬对象 | 辅助论据 / 对照物 |
| 编辑口味 | 目标读者的阅读偏好 |

## 核心原则

### 1. 先判断阶段，不直接起稿
大多数跑偏都发生在“题没锁、边界没锁、读者没锁”就直接写全文。

### 2. 只读当前需要的文档
不要一上来把全部阶段文档都读完。对 Claude Code 也一样。

### 3. 保留中间件
推荐至少保留：
- brief
- material ledger
- structure plan
- packaging plan
- draft
- quality gate result

### 4. 结构问题不要靠润色补
焦点、证据、结构没站住时，不要靠“把句子写顺”来掩盖。

### 5. 语言收口单独做
如果结构和证据已经过线，但语言还像 AI、翻译稿、材料整理件，再进入 `07-de-ai.md`。

## 三条推荐路径

### 最短路径
适合尽快出一版：
1. 01 framing
2. 05 drafting
3. 06 quality-gate
4. 07 de-ai（如需要）

跳过 02 的代价：容易把口径混进事实。只在素材来源单一、你已经知道什么能写什么不能写的时候跳。跳过 04 的代价：packaging 里的"作者动作句检查"不会执行，需要在 07 de-ai 里补拦。

### 标准路径
适合多数正常任务：
1. 01 framing
2. 02 evidence-layering
3. 03 structuring
4. 04 packaging
5. 05 drafting
6. 06 quality-gate
7. 07 de-ai（如需要）

### 编辑适配路径
适合编辑明确嫌“像整理回复、不像文章”的场景：
1. 01 framing
2. 03 structuring
3. 04 packaging
4. 05 drafting
5. 06 quality-gate
6. 07 de-ai（如需要）

## 阶段选择规则

### 进入 01 framing 的信号
- 题还没锁
- 主读者不清楚
- 不知道为什么现在写
- 主推对象和陪衬对象还混着

### 进入 02 evidence-layering 的信号
- 素材多而杂
- 事实、公司口径、外部补料混在一起
- 不知道哪些能写满，哪些只能轻写

### 进入 03 structuring 的信号
- 方向已定，但还没有段落功能表
- 用户要提纲或结构
- 你知道写什么，但不知道怎么铺

### 进入 04 packaging 的信号
- 结构有了，但像问答件、说明件、材料整理件
- 标题和板块不够像成稿
- 顺序基本还是客户问答顺序

### 进入 05 drafting 的信号
- brief 已锁
- 结构已锁
- 你缺的不是信息，而是把它写成一版正文

### 进入 06 quality-gate 的信号
- 初稿已成
- 需要决定能不能交稿，或者该回哪一层修

### 进入 07 de-ai 的信号
- 结构没大问题，但语言太像 AI / 翻译稿 / 模板稿

## 阶段交接规则

| 阶段 | 文档 | 模板 | 产物 |
| --- | --- | --- | --- |
| 01 framing | `docs/01-framing.md` | `templates/brief.md` | brief |
| 02 evidence-layering | `docs/02-evidence-layering.md` | `templates/material-ledger.md` | material ledger |
| 03 structuring | `docs/03-structuring.md` | `templates/structure-plan.md` | structure plan |
| 04 packaging | `docs/04-packaging.md` | `templates/packaging-plan.md` | packaging plan |
| 05 drafting | `docs/05-drafting.md` | —（直接出正文） | draft |
| 06 quality-gate | `docs/06-quality-gate.md` | `templates/quality-gate-result.md` | quality gate result |
| 07 de-ai | `docs/07-de-ai.md` | —（flag list 或 rewrite） | de-AI rewrite 或 flag list |

## 停止条件

本轮 workflow 至少要满足：
- 已识别当前阶段
- 已产出该阶段对应中间件
- 已知道下一阶段是什么
- 没有无意义地把全部文档灌进上下文

## 一句话记忆

> 先找阶段，再做当前步；每一层只解决一类问题。
