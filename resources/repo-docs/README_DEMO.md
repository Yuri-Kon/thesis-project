# 一键演示

本仓库提供了一套最小可运行的端到端演示入口，覆盖：

- FastAPI 输入层（`/docs`、`/health`、`/tasks`）
- Planner / Executor / Safety / Summarizer 工作链路
- 运行时资源（ProteinToolKG、日志、快照、输出目录）

## 快速开始

在仓库根目录执行：

```bash
./run_demo.sh
```

该命令会完成以下动作：

1. 检查运行前置条件（Python 3.12、`uv`、可选的 Nextflow）。
2. 初始化运行时目录与资源：
   - `output/`
   - `data/logs/`
   - `data/snapshots/`
   - 检查 `src/kg/protein_tool_kg.json` 是否可加载
3. 启动 FastAPI 服务。
4. 执行一次 smoke check：
   - `GET /health` 必须返回 `200`
   - `POST /tasks` 创建一个 demo 任务
   - `GET /tasks/{id}` 观察任务状态
   - 校验 `data/logs/{task_id}.jsonl` 已生成

启动后可访问：

- API 文档：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/health`
- HITL 仪表盘：`http://127.0.0.1:8000/ui`
- 事件时间线：`http://127.0.0.1:8000/ui/tasks/<task_id>/events`
- 候选对比演示（内置种子数据、进程内预览）：`uv run python examples/run_hitl_candidate_ui_demo.py`

## 全流程展示

如果要用于中期答辩或评审展示，可以生成一份统一的中文操作手册，把以下内容串成一条主线：

- API 可用性与冒烟检查
- HITL 候选对比界面
- Issue #151 回放/审计证据
- Issue #174 / #152 实验与报告证据

生成展示包：

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/build_full_flow_showcase.py
```

生成文件：

- `reports/showcase/full_flow_showcase_guide.md`
- `reports/showcase/full_flow_showcase_manifest.json`

如果希望在生成手册前顺带刷新一次相关产物，可使用：

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/build_full_flow_showcase.py --prepare
```

## Issue #142 候选对比演示

运行可复现的进程内预览（不需要额外依赖）：

```bash
uv run python examples/run_hitl_candidate_ui_demo.py
```

该脚本会写入固定的演示数据：

- `task_id=task_demo_142`
- `pending_action_id=pa_demo_142`

如果希望启动真实 HTTP UI 服务（需要 `uvicorn`），可执行：

```bash
uv run python examples/run_hitl_candidate_ui_demo.py --serve --port 8012
```

服务启动后，打开：

- `http://127.0.0.1:8012/ui/tasks/task_demo_142`
- `http://127.0.0.1:8012/ui/tasks/task_demo_142/events`
- `http://127.0.0.1:8012/pending-actions/pa_demo_142`

建议检查以下点位：

1. 候选表格中包含 rank / risk / cost / recommendation 字段。
2. 工具字段可见（`tool_id/capability_id/io_type/adapter_mode/source`）。
3. 至少有一个候选在工具元数据缺失时走降级展示路径。
4. 提交决策后，Decision Result 区域能展示状态变化和最新决策/状态迁移事件摘要。

## 常用选项

```bash
./run_demo.sh --port 8010 --model-backend mock --mock-tools
```

常用参数：

- `--host`, `--port`：API 监听地址
- `--model-backend`：写入 demo 元数据的后端标签
- `--mock-tools` / `--no-mock-tools`：切换 mock 工具模式
- `--data-dir`, `--output-dir`：运行时目录
- `--kg-path`：ProteinToolKG 文件路径
- `--smoke-test` / `--no-smoke-test`：启用或关闭 smoke run
- `--smoke-task-config`：任务请求 JSON（默认 `configs/demo_task.json`）
- `--exit-after-smoke`：smoke 检查通过后立即退出，适合 CI

所有参数都在 `scripts/run_demo.py` 中实现。

## 清理

```bash
./run_demo.sh clean
```

该命令会重置：

- `output/`
- `data/logs/`
- `data/snapshots/`

## 手动 Smoke 命令

如果启动 demo 时使用了 `--no-smoke-test`，可以手动执行：

```bash
curl -sS http://127.0.0.1:8000/health
curl -sS -X POST http://127.0.0.1:8000/tasks \
  -H 'content-type: application/json' \
  -d @configs/demo_task.json
curl -sS http://127.0.0.1:8000/tasks/<task_id>
```
