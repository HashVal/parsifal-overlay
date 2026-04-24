请阅读 `{STAGE_DOC}` 和对应模板 `{TEMPLATE_FILE}`，只完成当前阶段，不要越级把整篇文章一次写完。

输出要求：
1. 严格按模板给出结果
2. 如果信息不足，只追问会改变写法的缺口
3. 不要为了显得完整而把每段写满
4. 不要使用明显模板腔、解释腔、作者动作句、客服式收尾

输出后，再补一行：
`Next stage: ...`

## 阶段 → 文档 / 模板 / 产物对照

| 阶段 | STAGE_DOC | TEMPLATE_FILE | 产物 |
| --- | --- | --- | --- |
| framing | `docs/01-framing.md` | `templates/brief.md` | brief |
| evidence-layering | `docs/02-evidence-layering.md` | `templates/material-ledger.md` | material ledger |
| structuring | `docs/03-structuring.md` | `templates/structure-plan.md` | structure plan |
| packaging | `docs/04-packaging.md` | `templates/packaging-plan.md` | packaging plan |
| drafting | `docs/05-drafting.md` | —（直接出正文） | draft |
| quality-gate | `docs/06-quality-gate.md` | `templates/quality-gate-result.md` | quality gate result |
| de-ai | `docs/07-de-ai.md` | —（flag list 或 rewrite） | de-AI rewrite 或 flag list |
