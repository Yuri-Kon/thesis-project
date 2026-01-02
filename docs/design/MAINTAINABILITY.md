# 设计文档长期可维护性契约 (Long-Term Maintainability Contract)

本契约用于规范设计文档、索引与 docslice 的**长期演进规则**，确保可检索性、可维护性与稳定接口在持续迭代中不被破坏。

适用范围：
- 设计文档（`docs/design/`）
- 规范索引与主题视图（`docs/index/`）
- docslice 工具与其输出语义

---

## 1. 术语定义

- **SSOT**：Single Source of Truth，规范的唯一来源文档。
- **SID**：Section Identifier，用于稳定定位规范片段的标识符。
- **Section / Block / Spec-Item**：SID 的三种粒度，参见 `docs/index/SECTION_CONTRACT.md`。
- **Index**：`docs/index/index.json`，规范元数据与定位器的机器可读索引。
- **Topic View**：`docs/index/topic_views.json`，按主题聚合 SID 的视图。
- **docslice**：用于按 SID/主题抽取规范片段的工具与 CLI。

---

## 2. 文档演进规则

### 2.1 允许的变更

- 标题文字与自然语言内容可重写、润色或补充。
- 在不改变语义的前提下，可插入说明段或示例段。
- 可新增 Section/Block/Spec-Item，但必须分配**全新 SID** 并更新索引。
- 可调整段落顺序或移动规范位置，但必须同步更新索引定位信息。

### 2.2 禁止的变更

- **禁止修改 SID 字符串**（大小写、层级、分隔符、域名等）。
- **禁止复用既有 SID 表达新的语义**。
- **禁止删除或合并 SID 而不进行弃用标记**。
- **禁止嵌套 BEGIN/END 边界**。
- **禁止将 SSOT 迁移为隐性行为**（无声明、无索引更新）。

### 2.3 SSOT 迁移规则

当规范从 A 文档迁移到 B 文档时，必须同时满足：

- 在 `docs/index/SSOT_MAP.md` 中显式声明迁移关系。
- 更新 `index.json` 的 `doc_key`、`path` 与定位器信息。
- 维护旧 SID 的语义稳定；如需弃用，必须按 3.3 的弃用流程处理。

---

## 3. 索引治理规则

### 3.1 index.json

- **索引应可再生**：允许通过扫描脚本或工具重建，不依赖手工维护。
- 行号（`line_start/line_end`）只作为定位器的**快速路径**，不是语义契约。
- 一切 SID 的新增、迁移、弃用必须在索引中同步体现。

### 3.2 topic_views.json

- 仅引用 SID，不允许引用文档路径或标题文本。
- 主题视图应保持最小必要集合，不应引入过量冗余 SID。
- 对于 deprecated/superseded 的 SID，应从主题视图中移除或降级。

### 3.3 弃用与替换

- 当规范被替换时，旧 SID 必须标记为 `deprecated` 或 `superseded`。
- 新旧 SID 的关系应在文档或索引中明确记录，避免语义漂移。

---

## 4. docslice 稳定性承诺

### 4.1 CLI 接口稳定

docslice 的核心参数应保持长期稳定：

- `--sid`
- `--ref`
- `--topic`
- `--lint`
- `--max-lines`
- `--max-chars`
- `--no-metadata`
- `--repo-root`

新增参数可增量扩展，但禁止破坏现有参数语义。

### 4.2 输出语义稳定

- 抽取结果以 **SID 语义边界** 为准，而非行号。
- Section/Block 以标题边界为准；Spec-Item 以 BEGIN/END 为准。
- 输出元数据字段（SID、Title、Document、Lines、Level、Tags）应保持稳定结构。

### 4.3 内部策略可演进

允许调整内部定位策略（如回退扫描、容错策略），但必须满足：

- 不改变既有 SID 的语义结果。
- 若发生回退，应输出警告信息（stderr），提示索引可能需要更新。

---

## 5. 验收与回归

### 5.1 必须通过的校验

- `docslice --lint` 必须通过。
- 索引解析与 SID 定位不可产生空内容或缺失范围。

### 5.2 Golden 输出

核心主题（如 `hitl` / `planning` / `execution` / `observability`）应维护稳定的 golden 输出，用于回归比对。

---

## 6. 贡献者维护流程（建议）

1. 修改设计文档并保持 SID 稳定。
2. 运行索引再生或更新 `index.json` 与 `index.md`（如有变更）。
3. 更新 `topic_views.json` 以反映新增或弃用 SID。
4. 执行 `docslice --lint` 与相关测试脚本。
5. 在 PR 中明确说明 SID/索引/输出行为是否发生变化。

---

## 7. 允许变更 / 禁止变更速查

**允许：**

- 标题文字重写
- 内容补充与排版调整
- 新增 SID（全新语义）
- 调整内容位置并同步索引

**禁止：**

- 修改或复用已有 SID
- 隐性 SSOT 迁移
- 删除 SID 而不标记弃用
- BEGIN/END 嵌套或断裂
