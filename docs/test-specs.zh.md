# 测试规格

这些规格用于判断 VexDB Active Memory 是否已经具备作为独立记忆框架的可行性。总分 10 分，9 分视为通过。

## SMART 验收目标

- 具体：v0.1 必须提供数据库原生 upsert、冲突队列裁决、遗忘归档、Python SDK 和 stdio MCP Server。
- 可衡量：MCP 必须暴露写入、检索、批量写入、批量检索、冲突裁决和遗忘工具；`smoke-test` 和 `conflict-decay-test` 必须在真实 VexDB 上返回 `ok: true`；总体评分必须达到 9/10。
- 可实现：HNSW 和 PL/Python 按渐进增强处理，环境不支持时不能阻断基础写入、检索、裁决和归档。
- 相关性：所有能力都服务于“VexDB 单独成为融合向量数据库的记忆体框架”，不依赖外部记忆体框架。
- 有时限：v0.1 目标日期为 2026-05-31；v0.2 在 v0.1 后两周内补齐性能基线和真实 conflict/decay 证据；v1.0 再进入生产 SLO。

范围、里程碑、风险和责任矩阵见 `docs/roadmap.zh.md`。

## 评分模型

- OpenClaw/Hermes 接入易用性：2 分
- MCP 协议兼容性：2 分
- 数据入库和检索可靠性：2 分
- 安全与密钥处理：2 分
- 架构成熟度和可维护性：2 分

## 必测规格

### 1. MCP 工具发现

命令：

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli mcp-smoke
```

通过标准：

- 返回 `ok: true`
- 暴露 `vexdb_memory_status`
- 暴露 `vexdb_memory_add`
- 暴露 `vexdb_memory_batch_add`
- 暴露 `vexdb_memory_search`
- 暴露 `vexdb_memory_hybrid_search`
- 暴露 `vexdb_memory_batch_search`
- 暴露 `vexdb_memory_resolve_conflict`
- 暴露 `vexdb_memory_list_conflicts`
- 暴露 `vexdb_memory_apply_decay`
- 暴露 `vexdb_memory_graph`
- 暴露 `vexdb_memory_conflict_report`
- 暴露 `vexdb_memory_auto_capture`
- 暴露 `vexdb_memory_auto_recall`
- 输出 OpenClaw 前缀工具名

### 2. MCP 参数契约

命令：

```bash
PYTHONPATH=python pytest tests/test_mcp_server.py
```

通过标准：

- 必填参数缺失会返回错误
- 未知参数会返回错误
- 工具 schema 设置 `additionalProperties: false`
- 工具描述能引导 agent 在“记住/查询记忆”场景中调用对应工具

### 3. 数据库健康检查

命令：

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"vexdb_memory_status","arguments":{}}}' \
  | scripts/openclaw-vexdb-memory-mcp.sh
```

通过标准：

- `status` 为 `ready`
- `database.ok` 为 `true`
- `active_memory_schema` 为 `true`
- `memories_table` 为 `true`
- 输出中不包含 DSN、密码或 API key

### 4. 入库和检索

命令：

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli smoke-test \
  --namespace feasibility_test \
  --scope local \
  --memory-type fact
```

通过标准：

- 返回 `ok: true`
- `result_count >= 1`
- 返回可解析的 memory id

### 5. 去重与并发契约

命令：

```bash
PYTHONPATH=python pytest tests/test_concurrent_contract.py tests/test_normalize.py
```

通过标准：

- 同一规范化文本落到同一 advisory lock 桶
- 规范化和 hash 行为稳定

### 6. SQL/VexDB 契约

命令：

```bash
PYTHONPATH=python pytest tests/test_sql_contract.py
```

通过标准：

- schema 使用 VexDB `floatvector(1024)`
- 查询函数使用向量距离操作符
- `active_memory.memories` 是核心表

### 7. 冲突裁决与遗忘闭环

命令：
```bash
PYTHONPATH=python python -m vexdb_active_memory.cli conflict-decay-test
```

通过标准：
- 返回 `ok: true`
- `resolution.action` 为 `updated`、`appended` 或 `rejected`
- `decay.archived_count >= 1`
- `stale_memory_status` 为 `archived`
- `events` 中包含 `RESOLVE` 和 `ARCHIVE`

### 8. OpenClaw 接入

命令：

```bash
openclaw mcp show
```

通过标准：

- 存在 `vexdb-active-memory`
- `type` 为 `stdio`
- `command` 指向 `scripts/openclaw-vexdb-memory-mcp.sh`

### 9. Hermes 接入

命令：

```bash
hermes mcp test vexdb-active-memory
```

通过标准：

- 连接成功
- 发现 13 个工具
- 工具名包含 `vexdb_memory_status`、`vexdb_memory_add`、`vexdb_memory_batch_add`、`vexdb_memory_search`、`vexdb_memory_hybrid_search`、`vexdb_memory_batch_search`、`vexdb_memory_resolve_conflict`、`vexdb_memory_list_conflicts`、`vexdb_memory_apply_decay`、`vexdb_memory_graph`、`vexdb_memory_conflict_report`、`vexdb_memory_auto_capture`、`vexdb_memory_auto_recall`

## 当前实测评分

当前本机目标验证结果为 9.1/10。这个分数基于 MCP 自检、Hermes/OpenClaw 工具发现、数据库 status、入库检索和安全脱敏测试；如果换到新机器，需要按上面的规格重新跑一遍。

扣分项：

- OpenClaw/Hermes 的自然语言 agent 不一定每次主动选择 MCP 工具，需要继续用更强的工具描述、示例 prompt 和上层路由策略优化。
- 集成测试仍依赖本机 VexDB 环境，后续应补充一键测试环境或容器化测试脚本。

## 一键验证建议

在安装了 `pytest` 且配置好 `VEXDB_DSN` 的环境中，推荐按这个顺序跑：

```bash
python -m pip install -e .[dev]
PYTHONPATH=python pytest tests
PYTHONPATH=python python -m vexdb_active_memory.cli mcp-smoke
PYTHONPATH=python python -m vexdb_active_memory.cli smoke-test \
  --namespace feasibility_test \
  --scope local \
  --memory-type fact
PYTHONPATH=python python -m vexdb_active_memory.cli conflict-decay-test
hermes mcp test vexdb-active-memory
openclaw mcp show
```

如果没有真实 VexDB，`tests/test_integration_vexdb.py` 会跳过数据库集成测试，但这只能说明代码契约通过，不能证明数据库链路通过。
