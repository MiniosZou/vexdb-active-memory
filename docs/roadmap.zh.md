# 项目路线图与评审基线

本文档用于统一 VexDB Active Memory 的目标、范围、计划、资源、风险和责任边界。它是 README、架构文档和测试规格之外的项目评审基线。

## 1. 项目目标

VexDB Active Memory 的目标是在 2026-05-31 前完成 v0.1 MVP：让 VexDB 可以作为独立的、数据库原生的智能记忆框架，被 OpenClaw、Hermes 或其他 MCP 客户端直接接入。

SMART 指标：

- Specific：实现数据库原生语义 upsert、LLM/人工冲突裁决入口、自动遗忘归档、SDK 和 MCP 工具。
- Measurable：MCP 暴露核心写入、检索、批量写入、批量检索、裁决和遗忘工具；本地可行性评分达到 9/10；真实 VexDB 上 `smoke-test` 和 `conflict-decay-test` 返回 `ok: true`。
- Achievable：v0.1 只依赖 VexDB 兼容 SQL、Python SDK、psycopg2 和可选 embedding provider；HNSW、PL/Python、REST、后台调度都按渐进能力处理。
- Relevant：所有设计都围绕“VexDB 单独成为融合向量数据库的记忆体框架”，不把 Mem0、MemPalace、LangChain 或 LlamaIndex 作为运行依赖。
- Time-bound：v0.1 在 2026-05-31 前完成；v0.2 在 v0.1 后两周内完成真实库闭环和性能基线；v1.0 再承诺生产 SLO。

## 2. 用户价值

核心用户痛点：

- Agent 长期运行后容易写入重复、冲突、过期的记忆。
- 多 Agent 并发写入时，Python 中间层很难统一保证一致性。
- 传统向量库只负责检索，不负责记忆生命周期和审计。
- 接入不同 Agent 框架时，记忆能力经常被绑定到外部框架，难以独立产品化。

项目价值：

- 用数据库原生事务和函数把去重、裁决、审计、遗忘放到 VexDB 内部。
- 用 MCP 暴露稳定工具，让 OpenClaw、Hermes 和其他 Agent 客户端复用同一套记忆核心。
- 用生命周期策略减少垃圾记忆和存储膨胀，为后续“数据库 + 记忆框架”商业话术提供工程基础。

## 3. 范围边界

v0.1 做：

- SQL schema、函数、触发器、索引和权限初始化。
- `active_memory.upsert_memory`、`resolve_conflict`、`apply_decay`。
- Python SDK、CLI、stdio MCP Server。
- OpenClaw/Hermes 接入文档和验证命令。
- SQL/MCP/SDK 契约测试。

v0.1 不做：

- 独立 REST 服务。
- 后台定时任务调度器。
- Web 管理台。
- 托管 LLM 裁决服务。
- 多数据库兼容层。
- 对 Mem0、MemPalace、LangChain、LlamaIndex 的运行时依赖。

v0.2 做：

- 真实 VexDB conflict/decay 闭环验收记录。
- 写入、检索、冲突裁决、遗忘归档的性能基线。
- 一键测试环境或容器化验证脚本。
- 更完整的升级脚本和回滚策略。

v0.3 做：

- 可插拔 LLM adjudicator provider。
- 冲突 fixture 集、准确率报表、人工复核流。
- 更强的 Agent 工具选择提示和示例 prompt。

v1.0 做：

- 生产 SLO、监控指标、审计报表、发布包和运维文档。

## 4. 里程碑

| 版本 | 目标日期 | 验收标准 |
| --- | --- | --- |
| v0.1 | 2026-05-31 | MCP 9 工具可发现；`smoke-test` 可入库检索；`conflict-decay-test` 可裁决并归档；评分 >= 9/10 |
| v0.2 | v0.1 后 2 周 | 真实 VexDB 闭环证据入库；性能基线完成；容器化或一键测试脚本完成 |
| v0.3 | v0.2 后 4 周 | LLM 裁决 provider 可插拔；冲突 fixture 准确率报告可生成 |
| v1.0 | 业务试点后确定 | 生产 SLO、发布包、升级指南和监控审计完整 |

## 5. 资源与责任矩阵

| 工作项 | Responsible | Accountable | Consulted | Informed |
| --- | --- | --- | --- | --- |
| SQL 核心函数与 schema | 数据库工程 | 项目负责人 | VexDB 内核/DBA | SDK/MCP 工程 |
| Python SDK 与 CLI | SDK 工程 | 项目负责人 | 数据库工程 | Agent 集成方 |
| MCP/OpenClaw/Hermes 接入 | Agent 集成工程 | 项目负责人 | SDK 工程 | 产品/测试 |
| 测试环境与验收证据 | 测试工程 | 项目负责人 | DBA/Agent 集成工程 | 产品/研发 |
| LLM 裁决质量指标 | 产品 + 算法工程 | 产品负责人 | 数据库工程 | 测试/销售 |
| 文档与发布 | 产品技术文档 | 项目负责人 | 全体模块负责人 | 用户/试点方 |

## 6. 风险与预案

| 风险 | 影响 | 预案 |
| --- | --- | --- |
| VexDB 版本对 HNSW 支持不一致 | 检索性能和宣传口径受影响 | HNSW 作为渐进增强；不支持时 fallback 到精确向量排序 |
| PL/Python 权限不可用 | 数据库内 LLM hint 不可用 | 保留 `resolve_conflict`，由外部 reviewer/LLM 写入决策 |
| embedding 服务不可用或成本过高 | 写入/检索失败或成本不可控 | 本地测试用 mock；生产支持 provider 配额、重试和降级策略 |
| Agent 不主动选择 MCP 工具 | 用户体验不稳定 | 强化工具描述、示例 prompt 和上层路由策略 |
| conflict/decay 未跑真实库闭环 | 核心卖点证据不足 | 使用 `conflict-decay-test` 纳入发布前必跑项 |
| 范围蔓延到 REST/UI/调度 | 影响 v0.1 交付 | REST/UI/调度全部列为 v0.1 之外，除非单独立项 |

## 7. LLM 裁决质量指标

v0.3 前不得把 LLM 裁决宣传为完全自动生产能力。进入生产口径前需要：

- 冲突 fixture 集不少于 100 条，覆盖重复、补充、矛盾、过期和无关样本。
- `update/append/reject` 总体准确率达到 90% 以上。
- false merge 率低于 2%，false reject 率低于 5%。
- 低置信度样本进入人工复核或保持 pending。
- 每次裁决记录 actor、request_id、decision、rationale、conflict_id 和最终 memory_id。

## 8. 评审通过定义

项目评审达到 9/10 需要同时满足：

- 目标和范围：SMART 指标明确，v0.1 不做项明确。
- 计划和资源：里程碑、RACI、风险预案完整。
- 技术和设计：核心链路闭环，真实 VexDB 验收命令可执行。
- 文档一致性：README、architecture、test-specs、verification 口径一致。

## 9. 最新功能评审状态

本轮改进后，项目继续坚持 VexDB 原生主线，不引入 Mem0、MemPalace、LangChain 或其他记忆体框架作为运行依赖。

已落地：

- P0：冲突自动裁决开关已加入 SDK，可通过策略自动调用 `resolve_conflict(...)`；真实 OpenClaw/MCP 路径已验证 queued conflict -> auto resolution。
- P0：记忆重要性自动评分已加入 SDK，未传 `importance` 时会综合关键词、记忆类型、来源可信度和置信度估算；LLM provider 仍作为后续增强。
- P1：批量写入 `add_many(...)` 已加入 SDK。
- P1：批量检索 `batch_search(...)` 和 MCP 批量工具已加入。
- P1：标签/分类已加入 `tags` 字段并支持 MCP/SDK 检索过滤。
- P1：`search_memory(...)` 已支持 SQL 层 metadata/tags/space_path 过滤。
- P1：记忆组织层已加入 `space_path` 和 `memory_spaces`，为 Wings/Rooms/Collections 做数据库侧承载。
- P1：自动记忆关联已加入 `link_related_memories(...)`，写入后可生成 `semantic_related` 链接。
- P1：基础 Memory Graph 查询已加入 `get_memory_links(...)`、SDK 和 MCP 工具。
- P1：冲突样本统计报表已加入 `conflict_report(...)`、SDK 和 MCP 工具，用于阈值调优。
- P1：REST API 已作为可选薄适配器加入，核心仍由 VexDB SQL/SDK/MCP 承担。
- P1：TTL/时间有效性写入入口已加入 `valid_from`、`valid_until`、`expires_at`。

仍按后续版本推进：

- PostgreSQL/pgvector：定位为兼容适配包，不替换 VexDB；客户端已支持 `VEXDB_MEMORY_VECTOR_TYPE=vector`，仍需要单独 SQL 方言、测试矩阵和迁移说明。
- 冲突样本集准确率报告：仍需要 fixture、人工标注标准和准确率统计脚本。
- AAAK 压缩、Web 审核台、容器化完整测试环境：列入 P2 或独立子项目。
