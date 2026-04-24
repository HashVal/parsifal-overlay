# 软文 Workflow 分享包

这是一个可直接分享给他人的中性化写作 workflow 包，目标是把“软文 / 品牌稿 / 材料改写”从一次性 prompt，改成分阶段执行的稳定流程。


## 适用场景

适合以下任务：
- 软文
- 品牌稿
- 展前稿 / 展会稿
- 品牌材料改写
- 客户 Q&A / 新闻稿 / 产品资料改写成“像文章”的内容

不适合：
- 强销售转化文案
- 标题口号 / 海报文案 / 直播口播
- 官方声明 / 第一人称表态稿
- 只靠润色掩盖事实没理顺的问题

## 推荐路径

### 最短路径
`framing -> drafting -> quality-gate -> de-ai（如需要）`

### 标准路径
`framing -> evidence-layering -> structuring -> packaging -> drafting -> quality-gate -> de-ai（如需要）`

### 编辑适配路径
`framing -> structuring -> packaging -> drafting -> quality-gate -> de-ai（如需要）`

## 目录结构

- `docs/00-workflow-overview.md`：总入口与路由规则
- `docs/01-framing.md`
- `docs/02-evidence-layering.md`
- `docs/03-structuring.md`
- `docs/04-packaging.md`
- `docs/05-drafting.md`
- `docs/06-quality-gate.md`
- `docs/07-de-ai.md`
- `templates/*.md`：各阶段模板
- `prompts/*.md`：Claude Code 可直接复制使用的提示词

## 快速起手

如果要让 Claude Code 直接开始跑，先把 `prompts/claude-code-router-prompt.md` 的内容贴进去。

如果已经知道当前只需要某一阶段，就把 `prompts/claude-code-stage-prompt.md` 贴进去，并把其中的阶段名换成对应文档。

## 一句话说明

这套东西的核心不是“把软文写得更像广告”，而是：

> 先定题，再分层，再铺结构，再做包装，再起稿，再过门禁；语言最后单独收口。
