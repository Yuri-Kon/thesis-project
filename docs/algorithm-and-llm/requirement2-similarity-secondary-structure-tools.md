# Requirement-2 Similarity And Secondary Structure Tools

本说明覆盖 `mmseqs2`、`blastp`、`dssp` 三个本地工具的最小接入方式，以及仓库内统一输出字段。

## 1. 本地依赖

- `mmseqs2`: 需要 `mmseqs`
- `blastp`: 需要 NCBI BLAST+ 的 `blastp`
- `dssp`: 需要 `mkdssp`

当前仓库实现为 Python Adapter 调用本地 CLI。
如果二进制缺失，Adapter 会抛出 `CANDIDATE_TOOL_UNAVAILABLE`。

## 2. 最小输入

### MMseqs2 / BLASTP

- `sequence`: 查询序列
- `database_path`: 本地数据库路径
- 可选:
  - `query_id`
  - `max_seqs` / `max_target_seqs`
  - `evalue`
  - `sensitivity`

### DSSP

- `pdb_path`: 输入结构文件路径
- 可选:
  - `sequence`

## 3. 统一输出字段

### 相似性检索

- `capability_id = sequence_similarity_search`
- `io_type = sequence_to_similarity_hits`
- `similarity_hits`: 归一化 hits 列表
- `top_hit`: 第一条 hit
- `hit_count`

每条 hit 至少包含：

- `query_id`
- `target_id`
- `identity`
- `coverage`
- `query_coverage`
- `target_coverage`
- `evalue`
- `bitscore`
- `alignment_length`
- `query_start`
- `query_end`
- `target_start`
- `target_end`
- `query_length`
- `target_length`

说明：

- `coverage` 当前定义为 `query_coverage`
- `query_coverage = alignment_length / query_length`
- `target_coverage = alignment_length / target_length`

### DSSP

- `capability_id = secondary_structure_annotation`
- `capabilities = [secondary_structure_annotation, quality_qc]`
- `io_type = sequence_structure_to_qc_metrics`
- `secondary_structure`: residue-level rows
- `secondary_structure_summary`
- `qc_metrics.secondary_structure_summary`

每个 residue row 至少包含：

- `index`
- `residue_number`
- `chain_id`
- `amino_acid`
- `q8`
- `q3`

## 4. Requirement-2 统计对齐

新增 capability bucket：

- `similarity_search -> sequence_similarity_search`
- `secondary_structure -> secondary_structure_annotation`

因此 `requirement2_tool_capability_slices.csv` 会新增：

- 工具切片：`mmseqs2` / `blastp` / `dssp`
- capability bucket 切片：`similarity_search` / `secondary_structure`

## 5. 运行提示

- 这三个 Adapter 默认不自动安装数据库
- 真实本地实验前，需要先准备对应数据库
- 当前测试主要覆盖：
  - 命令封装
  - 输出解析
  - Requirement-2 统计对齐
