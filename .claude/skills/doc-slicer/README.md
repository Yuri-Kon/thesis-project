# docslice 脚本说明（供人工审阅）

本文档面向人工审阅，聚焦 `docslice` 命令及其参数在不同场景下的行为表现。脚本路径为 `/.claude/skills/doc-slicer/scripts/docslice`。

## 1. 命令概览

```bash
docslice --sid SID
docslice --ref DOC:doc_key#anchor
docslice --topic topic_name [--max-lines N] [--max-chars N]
docslice --lint

docslice [--no-metadata] [--repo-root PATH]
```

- `--sid` / `--ref` / `--topic` / `--lint` **互斥且必选其一**。
- `--max-lines` / `--max-chars` **仅在 `--topic` 下生效**。
- `--no-metadata` / `--repo-root` 为通用选项。

## 2. 仓库与依赖文件

脚本运行时依赖以下索引文件（基于 `--repo-root` 或自动探测）：

- `docs/index/index.json`
- `docs/index/topic_views.json`

`index.json` 里记录了每个 SID 的定位信息与文档路径；`topic_views.json` 维护主题到 SID 的映射。

## 3. 参数与行为细节

### 3.1 `--sid`

**输入格式**
- 支持 `SID:xxx.yyy.zzz` 或 `xxx.yyy.zzz`。
- 若 SID 不存在，命令报错并退出码为 1。

**定位方式**
`index.json` 中每个 SID 都带有 `locator.type`，脚本按类型提取内容：

- `comment`：从 SID 标记行附近向上找标题，再按标题层级截取到下一个同级或更高标题。
- `inline`：返回标记行附近的小范围文本（最多向上/下各 10 行，遇到空行或标题停止）。
- `begin_end`：根据 `line_start` / `line_end` 取块；若范围无效或标记不一致，会 **降级扫描** `<!-- SID:xxx BEGIN -->` 与 `<!-- SID:xxx END -->`。

**降级扫描提示**
当 `begin_end` 需要降级时，会向 stderr 打印：
```
Warning: Falling back to marker scan for SID <sid> (<reason>)
```

### 3.2 `--ref`

**输入格式**
- 必须为 `DOC:<doc_key>#<anchor>`。
- `doc_key` 仅匹配 `[a-z]+`（脚本正则限定）。

**匹配规则**
- 在对应文档中查找标题（`#` 开头的行）。
- 先尝试标题文本与 `anchor` **完全匹配**；不匹配时尝试 **lowercase + 空格转连字符** 的规范化匹配。

**失败行为**
- 未找到对应文档或 anchor，直接报错，退出码为 1。

### 3.3 `--topic`

**输入格式**
- `topic` 必须存在于 `topic_views.json` 的 `topics` 下。

**提取流程**
- 逐个按 topic 中列出的 SID 顺序提取。
- 若某个 SID 解析失败，会在 stderr 输出警告并 **跳过该 SID**，继续处理后续 SID。

**`--max-lines` / `--max-chars`**
- 仅对 `--topic` 生效，且是 **累计上限**。
- 一旦加入下一个片段会超过上限，就**停止追加**，不会截断片段。
- 统计的是 `fragment.content` 的行/字符数，**不包含元数据和分隔符**；因此最终输出可能超过你设定的上限。
- `0` 或不传视为“无上限”；负数为 truthy，会导致几乎立刻停止（因累计值必然大于负数）。

**输出分隔与统计**
- 多个片段之间会插入分隔线：`"="*80`。
- 结束时会在 stderr 打印统计信息（Topic 名称、片段数量、总行数、总字符数）。

**空结果**
若最终没有成功提取任何片段，会在 stderr 打印 `No fragments found...` 并返回退出码 1。

### 3.4 `--lint`

结构校验，错误输出到 stderr。检查内容包括：

- 所有文档中 SID 是否重复；
- `BEGIN` / `END` 是否成对；
- `index.json` 中 SID 的 locator 行号是否合法；
- 解析结果是否为空；
- topic 是否引用不存在或 deprecated 的 SID；
- `depends_on` 是否指向有效 SID。

**退出码**
- 无错误：退出码 0
- 有错误：退出码 1

### 3.5 `--no-metadata` - 默认输出包含元数据（SID、标题、文档路径、行号等）。 设置 `--no-metadata` 则只输出正文内容。

### 3.6 `--repo-root`

用于指定“设计文档索引”的仓库根目录。

**自动探测逻辑（默认）**
1. 从脚本位置向上查找包含 `docs/index/index.json` 的目录；
2. 未找到时，向上查找 `.git` 根目录；
3. 若存在同级目录 `thesis-project.design` 且包含索引文件，则优先使用该目录；
4. 仍未命中则退回脚本所在目录。

## 4. 输出与退出码

**标准输出 (stdout)**
- 正常情况下输出提取内容（可带元数据）。

**标准错误 (stderr)**
- 警告信息（如提取失败、触发上限、降级扫描）。
- `--topic` 的统计摘要。
- `--lint` 的错误详情。

**退出码**
- `0`：成功（包括 `--lint` 无错误、`--topic` 有片段输出）
- `1`：失败（参数错误、索引缺失、文档缺失、SID/anchor/topic 不存在、`--topic` 无片段、`--lint` 有错误等）

## 5. 常见命令示例

```bash
# 按 SID 提取（允许带 SID: 前缀）
docslice --sid SID:arch.contracts.pending_action

# 按文档锚点提取
docslice --ref DOC:arch#分层架构

# 按主题提取，限制行数
docslice --topic hitl --max-lines 300

# 校验文档结构
docslice --lint
```
