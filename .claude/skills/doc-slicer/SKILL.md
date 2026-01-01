---
name: doc-slicer
description: 从设计文档中精确提取规范片段。当需要查询 FSM 状态、HITL 契约、Agent 职责、工具规范或其他架构规范时使用。支持按 SID、topic 或文档引用提取。
allowed-tools: Bash(./scripts/docslice:*), Read
---

# Doc Slicer - 确定性规范切片工具

## 用途 (Purpose)

Doc Slicer 是本项目的**核心规范检索工具**，用于从设计文档中提取精确的规范片段。

**何时使用此 skill**：

- 实现 FSM 状态转换时，需要查询状态定义
- 实现 HITL 机制时，需要查询 `PendingAction`、`Decision` 契约
- 实现 Agent 时，需要查询职责边界（must / must_not）
- 接入工具时，需要查询 ToolAdapter 约束
- 校验实现与规范一致性时
- 需要按主题（hitl、planning、execution）获取最小规范集合

**不应使用的场景**：

- 探索性地浏览文档（使用 Read 工具直接读取设计文档）
- 模糊搜索或语义理解（此工具仅支持精确匹配）
- 修改设计文档（此工具是只读的）

## 前提条件 (Preconditions)

**假设以下基础设施已存在**：

1. 设计文档位于 `../thesis-project.design/docs/design/` 目录
2. 所有规范已标注 SID（Section Identifier），格式为 `SID:domain.topic.name`
3. 索引文件 `../thesis-project.design/docs/index/index.json` 和 `topic_views.json` 已生成
4. `scripts/docslice` 工具已正确安装且可执行

**验证前提条件**：

```bash
# 验证 docslice 可用
./scripts/docslice --help

# 验证索引文件存在
ls -l ../thesis-project.design/docs/index/index.json
```

## 使用步骤 (Usage Steps)

### 第一步：确定需求

**在调用 docslice 之前，先明确**：

- 你需要哪个具体的规范？（SID、topic 还是文档引用？）
- 是否需要多个相关规范？（使用 topic）
- 是否需要限制输出大小？（使用 `--max-lines` 或 `--max-chars`）

### 第二步：查看帮助信息（首次使用时）

```bash
./scripts/docslice --help
```

### 第三步：根据场景选择命令

#### 场景 1：按 SID 提取单个规范

```bash
# 提取 FSM 状态定义
./scripts/docslice --sid fsm.states.waiting_plan_confirm

# 提取 PendingAction 契约
./scripts/docslice --sid arch.contracts.pending_action

# 提取 PlannerAgent 职责
./scripts/docslice --sid planner.responsibilities.must
```

#### 场景 2：按 topic 提取相关规范集合

```bash
# 获取 HITL 相关的所有规范（限制 500 行）
./scripts/docslice --topic hitl --max-lines 500

# 获取 planning 相关规范（限制 10000 字符）
./scripts/docslice --topic planning --max-chars 10000

# 可用的 topic: hitl, planning, execution, observability
```

#### 场景 3：按文档引用提取（fallback）

```bash
# 当某个章节尚未分配 SID 时
./scripts/docslice --ref "DOC:arch#分层架构"
```

#### 场景 4：验证文档结构

```bash
# 在提交设计文档变更前，验证 SID 一致性
./scripts/docslice --lint
```

### 第四步：处理输出

**默认输出包含元数据**：

```markdown
# SID: arch.contracts.pending_action
# Title: PendingAction 契约定义
# Document: arch (docs/design/architecture.md)
# Lines: 337-355
# Level: Spec-Item
# Tags: arch, contracts, hitl, pending_action

[规范内容...]
```

**如果只需要内容，使用 `--no-metadata`**：

```bash
./scripts/docslice --sid arch.contracts.pending_action --no-metadata
```

## 常见场景 (Common Scenarios)

### 场景 1：实现 FSM 状态转换

**任务**：实现从 `PLANNING` 到 `WAITING_PLAN_CONFIRM` 的状态转换。

**步骤**：

1. 查询 `WAITING_PLAN_CONFIRM` 状态定义：
   ```bash
   ./scripts/docslice --sid fsm.states.waiting_plan_confirm
   ```

2. 查询状态转换规则：
   ```bash
   ./scripts/docslice --sid fsm.transitions.overview
   ```

3. 查询 PlannerAgent 在 HITL 场景下的职责：
   ```bash
   ./scripts/docslice --sid planner.hitl.plan_confirm
   ```

### 场景 2：实现 HITL 机制

**任务**：实现 `PendingAction` 和 `Decision` 的创建与处理逻辑。

**步骤**：

1. 获取所有 HITL 相关规范（限制大小）：
   ```bash
   ./scripts/docslice --topic hitl --max-lines 300 > hitl-specs.md
   ```

2. 或者逐个查询关键契约：
   ```bash
   ./scripts/docslice --sid arch.contracts.pending_action
   ./scripts/docslice --sid arch.contracts.decision
   ./scripts/docslice --sid arch.contracts.task_snapshot
   ```

### 场景 3：校验 Decision / Contract 一致性

**任务**：验证代码实现的 `Decision` 数据结构是否符合规范。

**步骤**：

1. 提取 Decision 契约定义：
   ```bash
   ./scripts/docslice --sid arch.contracts.decision --no-metadata
   ```

2. 对比代码中的 `Decision` 类定义（如 `src/models/decision.py`）

3. 确保字段、类型、验证逻辑一致

### 场景 4：接入 Tool Adapter

**任务**：为新工具（如 ESMFold）实现 ToolAdapter。

**步骤**：

1. 查询 ToolAdapter 设计原则：
   ```bash
   ./scripts/docslice --sid tools.adapter.constraints
   ```

2. 查询具体工具规约（如果已定义）：
   ```bash
   ./scripts/docslice --sid tools.esmfold.spec
   ```

3. 查询 Executor 如何调用工具：
   ```bash
   ./scripts/docslice --sid executor.responsibilities.must
   ```

### 场景 5：按主题聚合规范（实现前注入最小上下文）

**任务**：开始实现 PlannerAgent，需要获取相关规范。

**步骤**：

```bash
# 获取 planning 主题的所有规范（限制 500 行）
./scripts/docslice --topic planning --max-lines 500 > planning-context.md

# 查看获取到的规范数量（从 stderr 输出）
# 示例输出：
# Topic: planning
# Fragments: 12
# Total lines: 487
# Total chars: 15234
```

## 输出保证与限制 (Output Guarantees & Limits)

### 保证 (Guarantees)

✓ **确定性**：同样的输入始终产生相同的输出
✓ **精确性**：SID 对应唯一的文档片段，不会产生歧义
✓ **只读**：工具不会修改任何设计文档
✓ **可追溯**：输出包含文件路径和行号，可快速定位源文档
✓ **可验证**：`--lint` 命令验证 SID 系统的一致性

### 限制 (Limits)

✗ **不支持模糊搜索**：必须提供准确的 SID 或 topic 名称
✗ **不支持语义理解**：无法根据自然语言描述查找规范
✗ **不支持跨项目**：仅适用于本项目的设计文档
✗ **依赖索引**：所有定位必须经由 `index.json`，无法访问未索引的内容

### 大小控制

- **topic 提取**：使用 `--max-lines N` 或 `--max-chars N` 限制输出
- **超限处理**：达到限制时停止提取，输出警告到 stderr
- **建议限制**：
  - 快速查询：`--max-lines 100`
  - 中等上下文：`--max-lines 500`
  - 完整主题：`--max-chars 20000`

## 反模式 (Anti-patterns)

### ❌ 反模式 1：全文注入设计文档

**错误做法**：

```bash
# 不要这样做！
cat ../thesis-project.design/docs/design/architecture.md
cat ../thesis-project.design/docs/design/agent-design.md
# 然后让 Claude 从中查找信息
```

**为什么错误**：

- 浪费上下文窗口（设计文档可能有数千行）
- 难以聚焦关键信息
- 增加 token 成本

**正确做法**：

```bash
# 使用 docslice 精确提取
./scripts/docslice --topic hitl --max-lines 300
```

### ❌ 反模式 2：猜测 SID 名称

**错误做法**：

```bash
# 猜测 SID 可能叫什么
./scripts/docslice --sid fsm.state.plan_confirm  # 错误的 SID
```

**为什么错误**：

- SID 格式固定（`domain.topic.name`），猜测容易出错
- 失败时无法获取正确信息

**正确做法**：

1. 先查看 index.md 或使用 topic 查询：
   ```bash
   # 使用 topic 获取相关规范
   ./scripts/docslice --topic planning --max-lines 100
   ```

2. 或者使用 grep 在索引中搜索：
   ```bash
   grep -i "plan_confirm" ../thesis-project.design/docs/index/index.md
   ```

### ❌ 反模式 3：修改设计文档后不运行 lint

**错误做法**：

- 手动修改设计文档（在 `thesis-project.design` 中）
- 添加或修改 SID 标记
- 直接提交，不验证

**为什么错误**：

- 可能引入重复 SID
- BEGIN/END 标记可能不配对
- 破坏索引一致性

**正确做法**：

```bash
# 修改设计文档后，务必运行 lint
cd ../thesis-project.design
../thesis-project/scripts/docslice --lint

# 或者从主仓库运行
./scripts/docslice --lint
```

### ❌ 反模式 4：绕过 docslice 直接读取设计文档

**错误场景**：

需要实现 PendingAction 创建逻辑，直接：

```bash
grep -r "PendingAction" ../thesis-project.design/docs/design/
```

**为什么不推荐**：

- 可能找到多个定义（SSOT 不清晰）
- 缺少上下文（行号、依赖关系）
- 难以区分规范定义与示例代码

**推荐做法**：

```bash
# 使用 docslice 获取权威定义
./scripts/docslice --sid arch.contracts.pending_action
```

### ❌ 反模式 5：在主仓库中查找不存在的 docs/

**错误认知**：

认为 `docs/design/` 在主仓库 `thesis-project` 中。

**实际情况**：

- 设计文档在 `thesis-project.design` 工作树中
- 主仓库仅包含 `scripts/docslice` 工具
- docslice 会自动检测并查找工作树

**正确理解**：

```bash
# 在主仓库运行 docslice，它会自动找到工作树
cd thesis-project
./scripts/docslice --sid arch.contracts.pending_action

# docslice 内部逻辑会查找 ../thesis-project.design/
```

## 高级用法 (Advanced Usage)

### 查询依赖关系

虽然 docslice 不直接显示依赖关系，但可以通过 `index.json` 查询：

```bash
# 查找某个 SID 依赖了哪些其他规范
jq '.specs[] | select(.sid == "planner.algorithm.hitl_gate") | .depends_on' \
  ../thesis-project.design/docs/index/index.json
```

### 批量提取多个 SID

```bash
# 创建需要的 SID 列表
cat > sids.txt <<EOF
arch.contracts.pending_action
arch.contracts.decision
fsm.states.waiting_plan_confirm
EOF

# 批量提取
while read sid; do
  echo "=== $sid ==="
  ./scripts/docslice --sid "$sid" --no-metadata
  echo
done < sids.txt
```

### 验证 SID 是否存在

```bash
# 快速检查 SID 是否有效
if ./scripts/docslice --sid arch.contracts.pending_action >/dev/null 2>&1; then
  echo "SID exists"
else
  echo "SID not found"
fi
```

## 与项目架构的一致性 (Alignment with Project Architecture)

本 skill 与项目的核心架构原则保持一致：

1. **Contract-First**：通过 SID 系统确保契约的唯一性和可追溯性
2. **FSM-Driven**：支持精确查询 FSM 状态和转换规则
3. **HITL-Aware**：为 HITL 机制提供完整的契约定义（PendingAction、Decision、TaskSnapshot）
4. **SSOT (Single Source of Truth)**：每个规范有唯一的 SID，避免重复定义
5. **Separation of Concerns**：设计文档在工作树中，实现代码在主仓库，docslice 作为桥梁

## 故障排查 (Troubleshooting)

### 问题 1：`FileNotFoundError: Required index file not found`

**原因**：找不到 `index.json`

**解决**：

1. 确认设计工作树存在：
   ```bash
   ls -la ../thesis-project.design/docs/index/index.json
   ```

2. 如果不存在，检查工作树配置：
   ```bash
   git worktree list
   ```

### 问题 2：`ValueError: SID not found: xxx`

**原因**：提供的 SID 不存在于索引中

**解决**：

1. 查看可用的 SID：
   ```bash
   less ../thesis-project.design/docs/index/index.md
   ```

2. 或者使用 topic 查询：
   ```bash
   ./scripts/docslice --topic hitl --max-lines 50
   ```

### 问题 3：`ValueError: Topic not found: xxx`

**原因**：提供的 topic 不存在

**可用 topic**：

- `hitl`
- `planning`
- `execution`
- `observability`

### 问题 4：Lint 报告错误

**示例错误**：

```
✗ Found 2 error(s):
  - Duplicate SID 'arch.contracts.pending_action' found at: ...
  - BEGIN marker without END for SID: planner.algorithm.hitl_gate
```

**解决**：

1. 检查重复 SID：确保每个 SID 只出现一次
2. 检查 BEGIN/END 配对：确保每个 BEGIN 都有对应的 END
3. 修复后重新运行 lint

## 总结

Doc Slicer 是本项目**规范驱动开发**的核心工具。使用它可以：

✓ 避免全文注入设计文档
✓ 精确获取实现所需的规范片段
✓ 确保实现与设计的一致性
✓ 提高开发效率和代码质量

**记住核心原则**：

1. **优先使用 SID**：精确、确定、唯一
2. **使用 topic 聚合**：获取最小必要上下文
3. **控制输出大小**：避免上下文溢出
4. **运行 lint 验证**：确保设计文档一致性
5. **遵循 SSOT**：每个规范只有一个权威来源
