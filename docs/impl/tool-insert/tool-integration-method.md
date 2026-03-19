# 模型集成说明

更新时间：2026-03-16 12:02

## 说明

本文档用于指示在 [工具集成参考](./multitool-intrgration-reference)中提到的工具的集成方法。


## AlphaFold2

### 集成方法

- NVIDIA NIM

### NVIDIA NIM Integration

#### Model Card

- Description:

  AlphaFold2 is a deep learning model for protein structure prediction developed by the research group at DeepMind, an artificial intelligence (AI) research lab owned by Google (jumper2021alphafold). AlphaFold2 builds on the success of its predecessor, AlphaFold, and represents a significant breakthrough in the field of protein structure prediction. This model is available for commercial use.
- Third-Party Community Consideration

  This model is not owned or developed by NVIDIA. This model has been developed and built to a third-party’s requirements for this application and use case.
- Model Architecture:

  - Architecture Type: Protein Structure Prediction
  - Network Architecture: AlphaFold2
  - Input Type(s): Protein Sequence, Relax Prediction (Default True)
  - Input Format(s): String (less than or equal to 4096 characters), boolean
  - Input Parameters: 1D
  - Other Properties Related to Input: NA
- Output:

  - Output Type(s): Protein Structure(s) in PDB Format
  - Output Format: PDB (text file)
  - Output Parameters: 1D
  - Other Properties Related to Output: Pose (num_atm_ x 3)
- Training Dataset:

  Link: A description of the training dataset and relevant download links are available at https://www.nature.com/articles/s41586-021-03819-2#data-availability. This data was not collected by NVIDIA.
  - ** Data Collection Method by dataset: See the description at https://www.nature.com/articles/s41586-021-03819-2#data-availability.
  - ** Labeling Method by dataset: See the description at https://www.nature.com/articles/s41586-021-03819-2#data-availability.
  - Properties (Quantity, Dataset Descriptions, Sensor(s)): Uniclust dataset of 355,993 sequences with the full MSAs. These predictions were then used to train a final model with identical hyperparameters, except for sampling examples 75% of the time from the Uniclust prediction set, with sub-sampled MSAs, and 25% of the time from the clustered PDB set.
- Evaluation Dataset:

  Link: See the description at https://www.nature.com/articles/s41586-021-03819-2#Sec10.
  - ** Data Collection Method by dataset: [Not Applicable]
  - ** Labeling Method by dataset: [Not Applicable]
  - Properties (Quantity, Dataset Descriptions, Sensor(s)): Uniclust dataset of 355,993 sequences with the full MSAs. These predictions were then used to train a final model with identical hyperparameters, except for sampling examples 75% of the time from the Uniclust prediction set, with sub-sampled MSAs, and 25% of the time from the clustered PDB set.

#### How to use

使用如下示例 Python 代码：

```python
#!/usr/bin/env python3
import os
import requests
import time
from pathlib import Path

# Variables
url = os.getenv("URL", "https://health.api.nvidia.com/v1/biology/deepmind/alphafold2")
status_url = os.getenv("STATUS_URL", "https://health.api.nvidia.com/v1/status")

sequence = ("MVPSAGQLALFALGIVLAACQALENSTSPLSADPPVAAAVVSHFNDCPDSHTQFCFHGTCRFL"
    "VQEDKPACVCHSGYVGARCEHADLLAVVAASQKKQAITALVVVSIVALAVLIITCVLIHCCQVRKHCEWCR"
    "ALICRHEKPSALLKGRTACCHSETVV"
)
output_file = Path("output.json")

# Initial request
headers = {
    "content-type": "application/json",
    "Authorization": "Bearer $NVIDIA_API_KEY",
    "NVCF-POLL-SECONDS": "300",
}
data = {
    "sequence": sequence,
    "algorithm": "mmseqs2",
    "e_value": 0.0001,
    "iterations": 1,
    "databases": ["small_bfd"],
    "relax_prediction": False,
    "skip_template_search" : True
}

print("Making request...")
response = requests.post(url, headers=headers, json=data)

# Check the status code
if response.status_code == 200:
    output_file.write_text(response.text)
    print(f"Response output to file: {output_file}")
elif response.status_code == 202:
    print("Request accepted...")
    # Extract reqId header
    req_id = response.headers.get("nvcf-reqid")

    # Poll the /status endpoint
    while True:
        print("Polling for response...")
        status_response = requests.get(f"{status_url}/{req_id}", headers=headers)

        if status_response.status_code != 202:
            output_file.write_text(status_response.text)
            print(f"Response output to file: {output_file}")
            break
else:
    print(f"Unexpected HTTP status: {response.status_code}")
    print(f"Response: {response.text}")
```

得到结果为 [pdb序列](./bionemo.pdb):

---

## OpenFold3

### 集成方法

- NVIDIA NIM
- Hugging faces(Remote REST)

### NVIDIA NIM Integration

#### Model Card

- Description:
  OpenFold3 is a biomolecular complex structure prediction model from the OpenFold Consortium and the Alquraishi Laboratory. OpenFold3 is a pytorch re-implementation of Google Deepmind's AlphaFold3, with support for both training and inference. See the github repo https://github.com/aqlaboratory/openfold-3.
- Third-Party Community Consideration
  This model is not owned or developed by NVIDIA. This model has been developed and built to a third-party’s requirements for this application and use case.
- Model Architecture:
  - Architecture Type: Protein Structure Prediction
  - Network Architecture: AlphaFold3
  - ** This model was developed based on AlphaFold3
  - ** Number of model parameters: 3.68×10⁸
- Input:
  - Input Type(s): Protein Sequence, Multiple Sequence Alignments; DNA Sequence; RNA Sequence; Ligand CCD code; Ligand SMILES code
  - Input Format(s): String (less than or equal to 1000), a3m-format strings, csv-format string, string
  - Input Parameters: One-Dimensional (1D), One-Dimensional (1D), One-Dimensional (1D); One-Dimensional (1D); One-Dimensional (1D);One-Dimensional (1D); One-Dimensional (1D)
  - Other Properties Related to Input: a3m is a standard file format for storing multiple sequence alignment results. a3m-format strings, csv-format string is a standard format for atomic structures
- Output:
  - Output Type(s): Biomolecular Complex Structure(s) in mmCIF format
  - Output Format: mmCIF/PDB (text)
  - Output Parameters: 1D
  - Other Properties Related to Output: Pose (num_atm_ x 3)

#### How to Use

参照这个 Python示例：

```python
#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

#
# usage
#   (1) Open a bash shell
#   (2) Run the command "export NVIDIA_API_KEY=<your key>"
#   (3) Copy-paste this code into an empty file named example.py 
#       in the current working directory.
#   (4) Run the command "python example.py"
#   (5) View the response in a newly created file output.json in the same directory.
#
# notes:
#   Example with protein-DNA complex (PDB: 5GNJ)
#
import os
import requests
from pathlib import Path

# ----------------------------
# parameters
# ----------------------------
url = os.getenv("URL", "https://health.api.nvidia.com/v1/biology/openfold/openfold3/predict")
output_file = Path("output.json")

# MSA alignment in CSV format
msa_alignment_csv = (
    "key,sequence\n"
    "-1,MGREEPLNHVEAERQRREKLNQRFYALRAVVPNVSKMDKASLLGDAIAYINELKSKVVKTESEKLQIKNQLEEVKLELAGRLEHHHHHH"
)

data = {
    "request_id": "5GNJ",
    "inputs": [
        {
            "input_id": "5GNJ",
            "molecules": [
                {
                    "type": "protein",
                    "id": "A",
                    "sequence": "MGREEPLNHVEAERQRREKLNQRFYALRAVVPNVSKMDKASLLGDAIAYINELKSKVVKTESEKLQIKNQLEEVKLELAGRLEHHHHHH",
                    "msa": {
                        "main_db": {
                            "csv": {
                                "alignment": msa_alignment_csv,
                                "format": "csv",
                            }
                        },
                    },
                },
                {
                    "type": "dna",
                    "id": "B",
                    "sequence": "AGGAACACGTGACCC",
                },
                {
                    "type": "dna",
                    "id": "C",
                    "sequence": "TGGGTCACGTGTTCC",
                },
            ],
            "output_format": "pdb",
        }
    ],
}
print(data)

# ---------------------------------------------------------
# Submit
# ---------------------------------------------------------
headers = {
    "content-type": "application/json",
    "Authorization": "Bearer $NVIDIA_API_KEY",
    "NVCF-POLL-SECONDS": "300",
}
print("Making request...")
response = requests.post(url, headers=headers, json=data)

# ---------------------------------------------------------
# View response
# ---------------------------------------------------------
if response.status_code == 200:
    output_file.write_text(response.text)
    print(f"Response output to file: {output_file}")

else:
    print(f"Unexpected HTTP status: {response.status_code}")
    print(f"Response: {response.text}")
```

Result in [opefold3](./openfold3.json)

### HuggingFaces

### Quick Start for Inference

Make your first predictions with OpenFold3-preview in a few easy steps:

1. Install OpenFold3-preview using our pip package
  ```bash
    pip install openfold3 
    mamba install kalign2 -c bioconda
  ```
2. Setup your installation of OpenFold3-preview and download model parameters:
  ```bash
    setup_openfold
  ```
3. Run your first prediction using the ColabFold MSA server with the run_openfold binary
  ```bash
    run_openfold predict --query_json=examples/example_inference_inputs  /query_ubiquitin.json
  ```
More information on how to customize your inference prediction can be found at our documentation home at https://openfold-3.readthedocs.io/en/latest/. More examples for inputs and outputs can be found in our HuggingFace examples.

---

## MMseqs2

### Introduction

MMseqs2（Many-against-Many sequence searching）是一个面向大规模蛋白质/核酸序列搜索与聚类的工具套件。它同时提供适合快速验证的 `easy-*` 工作流，以及适合集成到生产流水线中的底层模块（如 `createdb`、`createindex`、`search`、`convertalis`、`databases`）。对本系统而言，MMseqs2 最适合承担以下职责：

- `S3` 候选序列质量评估：检索已知同源序列，判断 novelty / redundancy 风险。
- `S5` 可解释评价补充：输出 hits、e-value、bits、identity、coverage 等证据，支撑排序与报告。
- 与 `BLASTP` 形成经典基线互证，但在批量实验中优先作为高吞吐检索主路径。

### Installation

MMseqs2 可通过源码编译、静态二进制、Homebrew、conda 或 Docker 安装。

```bash
# install by brew
brew install mmseqs2
# install via conda
conda install -c conda-forge -c bioconda mmseqs2
# install docker
docker pull ghcr.io/soedinglab/mmseqs2
# MMseqs2-GPU mostly-static AVX2 build requiring glibc >= 2.29 and nvidia driver >=525.60.13
wget https://mmseqs.com/latest/mmseqs-linux-gpu.tar.gz
tar xvfz mmseqs-linux-gpu.tar.gz
export PATH=$(pwd)/mmseqs/bin/:$PATH
# static build with AVX2 (fastest)
wget https://mmseqs.com/latest/mmseqs-linux-avx2.tar.gz
tar xvfz mmseqs-linux-avx2.tar.gz
export PATH=$(pwd)/mmseqs/bin/:$PATH
```

环境约束与部署建议：

- CPU 路径建议优先使用 `AVX2` 构建；最低建议 `SSE4.1`。
- GPU 搜索可用 `--gpu`，官方说明对 Turing 及更新架构提供支持，Ampere 及以上速度最佳。
- `search` 的内存消耗与 target database 大小线性相关；数据库过大时应显式设置 `--split-memory-limit`。
- 临时目录 `tmp/` 会产生较大中间文件，Nextflow 模块应将其挂载到高 IOPS、本地或共享 scratch 空间。
- 如果后续需要 MPI 横向扩展，数据库目录和临时目录必须可被多节点共享；预编译静态版本默认不含 MPI。

### Recommended Integration Pattern

建议区分为两层接入：

1. `quick validation`：使用 `easy-search` 直接对 FASTA 与目标库进行搜索，适合原型验证、手工排障、单步实验。
2. `production workflow`：使用 `createdb -> createindex -> search -> convertalis`，适合 Adapter/Nextflow 正式接入，因为该链路更稳定、可缓存、便于复用索引，并且更容易将中间产物纳入追踪。

对应项目内建议：

- `src/adapters/mmseqs2_adapter.py`：参数校验、命令拼装、失败码标准化、产物登记。
- `nf/modules/mmseqs2.nf`：封装数据库准备、搜索与结果导出；允许 CPU/GPU 两种 profile。
- `src/kg/protein_tool_kg.json`：声明 capability 为 `sequence_similarity_search` / `homology_evidence`，并补充数据库、硬件与输出约束。

### Database Preparation

如果需要使用公共参考库，官方推荐通过 `databases` 工作流下载并初始化数据库。例如：

```bash
mmseqs databases UniProtKB/Swiss-Prot swissprot tmp
```

对本系统更重要的落地要求：

- 固定数据库名称、版本与下载日期，例如 `swissprot_2026_03`。
- 将数据库目录与 `freeze_id` 一起记录到实验元数据，避免后续横向实验口径漂移。
- 若数据库会被高频重复查询，应提前执行索引构建；若走 GPU，还应预生成 padded database。

### Quick Start: easy-search

对于单次查询或联调，可先使用 `easy-search`：

```bash
mmseqs easy-search   query.fasta   swissprot   result.m8   tmp   -s 5.7   --max-seqs 300   --format-output "query,target,evalue,bits,pident,alnlen,qstart,qend,tstart,tend"
```

说明：

- `-s` 用于调节搜索灵敏度；官方示例中较快搜索可取 `1.0`，高灵敏度可提高到 `7.0`。
- `--max-seqs` 可限制保留 hits 数量，便于后续排序与摘要。
- `--format-output` 可直接控制表格列，建议在系统内固定字段集合，避免不同实验批次输出 schema 漂移。
- 官方文档特别提醒：`easy-search` 默认 identity 计算方式与 `search` 默认估计值存在差异；如果需要真实 sequence identity，建议增加 `--alignment-mode 3` 或 `-a`。

### Production Workflow: createdb/search/convertalis

正式集成时，建议使用模块化链路：

```bash
mmseqs createdb query.fasta queryDB
mmseqs createdb target.fasta targetDB
mmseqs createindex targetDB tmp
mmseqs search queryDB targetDB resultDB tmp   -s 5.7   --max-seqs 300   --split-memory-limit 16G
mmseqs convertalis queryDB targetDB resultDB result.tsv   --format-output "query,target,evalue,bits,pident,alnlen,qstart,qend,tstart,tend"
```

如果目标库会被频繁查询且环境具备 GPU，可在索引后额外执行：

```bash
mmseqs makepaddedseqdb targetDB targetDB_padded
mmseqs easy-search query.fasta targetDB_padded result.m8 tmp --gpu 1
```

工程化接入理由：

- `targetDB` 与其索引可长期缓存，适合实验批处理。
- `resultDB` 可作为中间产物保留，后续可重复导出不同字段，不必重复跑搜索。
- `convertalis` 将结果导出为统一 TSV，更适合进入系统的 artifact schema 与报告流水线。

### Suggested Adapter Contract

建议 `mmseqs2_adapter.py` 至少暴露以下输入参数：

- `query_fasta`: 查询序列文件路径。
- `target_db`: 目标数据库路径或逻辑名。
- `tmp_dir`: 临时目录。
- `sensitivity`: 对应 `-s`。
- `max_seqs`: 最大命中数。
- `alignment_mode`: 是否强制真实 identity。
- `format_output`: 统一输出字段列表。
- `gpu`: 是否启用 GPU 搜索。
- `split_memory_limit`: 大库时的内存上限。

建议标准输出产物：

- `result_tsv`: 标准 hits 表。
- `result_db_path`: MMseqs2 原生结果数据库路径。
- `database_manifest`: 数据库名称、版本、下载时间、来源 URL。
- `search_stats`: 命中数、top1 e-value、top1 bits、top1 identity、运行时长。

建议优先固定如下 TSV 列：

```text
query,target,evalue,bits,pident,alnlen,qstart,qend,tstart,tend
```

如果后续排序需要 coverage，可在统一 schema 中补充相应字段，但必须一次定清并版本化。

### Nextflow Module Sketch

在 `nf/modules/mmseqs2.nf` 中可拆为三个过程：

1. `prepare_mmseqs_db`：下载或挂载目标数据库，执行 `createdb/createindex`，可选 `makepaddedseqdb`。
2. `run_mmseqs_search`：接受 `query_fasta + target_db + params`，输出 `resultDB` 与 TSV。
3. `summarize_mmseqs_hits`：对 hits 进行轻量聚合，产出供 S5 使用的 JSON/TSV 摘要。

这样做的好处是数据库准备可以单独缓存，不会在每次任务中重复下载或建索引。

### Failure Handling And Recovery Mapping

接入时建议提前做失败码归一化，至少覆盖：

- `MMSEQS2_BINARY_MISSING`: 二进制不存在或不可执行。
- `MMSEQS2_DB_MISSING`: 目标数据库目录不存在或未完成初始化。
- `MMSEQS2_UNSUPPORTED_ISA`: 当前机器不支持所下载二进制对应的指令集。
- `MMSEQS2_GPU_UNAVAILABLE`: 请求 GPU 模式但 CUDA/GPU 不可用。
- `MMSEQS2_TMP_NO_SPACE`: 临时目录空间不足。
- `MMSEQS2_OOM_OR_SPLIT`: 内存不足或需要调整 `--split-memory-limit`。
- `MMSEQS2_EMPTY_HITS`: 命中为空；这通常不是执行失败，应作为有效结果上报。

恢复策略建议：

- 先 retry：仅针对偶发 I/O 或 scratch 目录问题。
- 再 patch：降低 `-s`、关闭 GPU、减小 `--max-seqs`、调整 `--split-memory-limit`。
- 最后 replan：切换到 `BLASTP` 基线或跳过同源检索并显式记录降级原因。

### Integration Notes For This Project

为了让 MMseqs2 真正可用于后续系统集成，而不是只停留在命令可运行层面，建议同时落地以下内容：

- 在 ToolKG 中补充 `official_link`、`execution.backend=nextflow|external`、`constraints.database_version_locked=true`。
- 在实验配置中记录 `db_name`、`db_release`、`commandline`、`mmseqs_version`、`gpu_enabled`。
- 在报告层显式区分“无命中”与“执行失败”，避免 novelty 判断被误伤。
- 用 `easy-search` 做开发期 smoke test，用模块化 `search/convertalis` 做正式实验。

### References

- 官方仓库：https://github.com/soedinglab/MMseqs2
- 用户文档（GitHub Wiki）：https://github.com/soedinglab/MMseqs2/wiki
- 用户手册 PDF：https://mmseqs.com/latest/userguide.pdf


---

## BLASTP

### Introduction

BLASTP 是 NCBI BLAST+ 套件中的蛋白质对蛋白质相似性搜索工具，适合在本项目中承担 `MMseqs2` 的经典基线与互证角色。相对于 `MMseqs2`，BLASTP 吞吐更低，但方法学更传统、结果解释成本更低，适合：

- 作为 `S3/S5` 的保守型同源检索基线。
- 对 `MMseqs2` 高速命中结果做 spot check。
- 在论文或实验报告中提供更易被外部读者理解的对照路径。

### Installation

BLASTP 属于 NCBI BLAST+ 工具包。官方手册说明 BLAST+ 既提供可执行安装包，也提供源码包。

建议接入方式：

- Linux 服务器优先使用官方 BLAST+ 二进制或系统包管理器安装。
- Adapter 层只依赖 `blastp`、`makeblastdb`、必要时 `blastdbcmd`。
- 固定 `blastp -version` 输出并写入实验元数据。

### Recommended Integration Pattern

建议分为两层：

1. `quick validation`：直接对本地 FASTA 数据库运行 `blastp`，用于联调和结果抽样检查。
2. `production workflow`：先 `makeblastdb`，后批量运行 `blastp` 并输出统一 tabular schema，供系统聚合和比较。

建议项目落点：

- `src/adapters/blastp_adapter.py`
- `nf/modules/blastp.nf`
- `src/kg/protein_tool_kg.json` 中新增 `sequence_similarity_search_baseline`

### Database Preparation

官方手册明确建议使用 `makeblastdb` 从本地 FASTA 构建数据库，并指出最好为每条序列分配唯一标识符，以便后续检索和 taxid 关联。

示例：

```bash
makeblastdb -in target.fasta -dbtype prot -out target_db
```

工程要求：

- 数据库名、来源、版本日期必须显式记录。
- 如果使用本地构建库，建议保留原始 FASTA 和 `makeblastdb` 命令行。
- 从 BLAST+ 2.13.0 起会生成 `.pjs` 元数据文件，可一并登记到 artifact 清单。

### Quick Start

```bash
blastp   -query query.fasta   -db target_db   -out result.tsv   -outfmt "6 qseqid sseqid evalue bitscore pident length qstart qend sstart send qcovs"   -max_target_seqs 300   -num_threads 8
```

说明：

- `-outfmt 6` 是最适合集成的表格输出形式；官方手册给出了自定义字段的用法。
- `-max_target_seqs` 可限制输出命中数，便于和 `MMseqs2 --max-seqs` 对齐。
- `qcovs` 适合直接进入报告层，补充 identity/bits/e-value 的解释性。
- 若只做互证，不建议默认走 `-remote`，因为 NCBI 远端服务是共享资源，官方手册明确建议不要并行大量远程检索。

### Suggested Adapter Contract

建议输入参数：

- `query_fasta`
- `target_db`
- `outfmt_fields`
- `max_target_seqs`
- `num_threads`
- `evalue_threshold`
- `task`（如后续需要对短序列做专门调整）

建议输出产物：

- `result_tsv`
- `db_manifest`
- `search_stats`
- `top_hits_summary`

建议默认字段：

```text
qseqid sseqid evalue bitscore pident length qstart qend sstart send qcovs
```

### Failure Handling And Recovery Mapping

建议至少覆盖：

- `BLASTP_BINARY_MISSING`
- `BLASTP_DB_MISSING`
- `BLASTP_DBTYPE_MISMATCH`
- `BLASTP_EMPTY_HITS`
- `BLASTP_FORMAT_ERROR`
- `BLASTP_REMOTE_UNAVAILABLE`

恢复策略建议：

- retry：仅针对临时 I/O 问题。
- patch：收紧 `-evalue`、降低 `-max_target_seqs`、切换到本地数据库。
- replan：如果只是互证工具失败，可保留 `MMseqs2` 主结论并标记 `BLASTP` 缺失。

### Integration Notes For This Project

- `BLASTP` 的输出字段应与 `MMseqs2 convertalis --format-output` 尽量对齐，减少后处理分支。
- 在横向实验里，建议将 `BLASTP` 仅作为基线或 spot-check 工具，而非高吞吐主检索工具。
- 如果后续需要 taxonomy 或 accession 深挖，可额外保留 `blastdbcmd` 访问能力。

### References

- NCBI BLAST Command Line User Manual: https://www.ncbi.nlm.nih.gov/books/NBK279690/
- Building a BLAST database with your local sequences: https://www.ncbi.nlm.nih.gov/sites/books/NBK569841/
- Display BLAST search results with custom output format: https://www.ncbi.nlm.nih.gov/books/NBK569862/

---

## DSSP

### Introduction

DSSP（Dictionary of Secondary Structure in Proteins）用于根据蛋白质三维结构坐标分配二级结构。官方文档明确指出，DSSP 是对结构进行 annotation，而不是做二级结构预测。对本项目而言，DSSP 更适合放在 `S3` 质量门禁和 `S5` 结构解释层：

- 对结构预测结果补充每残基二级结构标签。
- 统计 helix / strand / turn / bend 等比例，作为报告特征。
- 为结构异常或设计偏差提供可解释证据。

### Installation

DSSP 官方仓库当前为 `DSSP 4.5` 系列，已默认支持完整 mmCIF。仓库说明可通过 CMake 构建本地 `mkdssp`，也可以启用 Python module 构建。

本地构建示例：

```bash
git clone https://github.com/PDB-REDO/dssp.git
cd dssp
cmake -S . -B build
cmake --build build
cmake --install build
```

如果希望在 Python 中直接访问结果，可启用：

```bash
cmake -S . -B build -DBUILD_PYTHON_MODULE=ON
cmake --build build
cmake --install build
```

### Recommended Integration Pattern

建议优先使用本地 `mkdssp` CLI 作为执行主路径，原因：

- 更符合当前项目 `nextflow / external` 的工具接入方式。
- 输出文件明确，便于纳入 artifact 管理。
- 与结构文件批处理更容易集成。

Python module 更适合作为：

- 本地分析脚本
- 单元测试中的轻量读取
- 后处理解析器

### Input And Output Considerations

官方仓库和 DSSP 网站说明：

- DSSP 4 默认输出 annotated mmCIF，并将二级结构信息写入 `_struct_conf`。
- 仍可输出 legacy DSSP 格式，但只适用于能容纳于旧格式限制的结构。
- DSSP 4 增加了 Poly-Proline II helix，对应单字符 `P`。
- mmCIF 输出默认不计算 solvent accessibility；如需要该指标，应显式打开 `--calculate-accessibility`。

对本项目的接入含义：

- 如果系统后续更偏向机器读取，应优先保留 mmCIF 输出。
- 如果报告层或现有解析器更依赖传统单字符结果，可额外导出 legacy DSSP。
- 如果要做 SASA/可及性相关门禁，必须明确记录是否开启 `--calculate-accessibility`。

### Quick Start

官方网页建议通过 `mkdssp -h` 查看本地帮助。结合项目需求，推荐的最小调用模式是：

```bash
mkdssp input.cif output.cif
```

如果需要 legacy DSSP 文本结果或更多输出控制，应以本地 `mkdssp -h`/manual page 为准。

如果不希望本地安装，也可以使用 DSSP 官方 REST API 做原型验证：

```bash
curl -X POST https://pdb-redo.eu/dssp/do   -F format=mmcif   -F data=@input.cif
```

这里的 API 输入为 mmCIF 或 PDB 内容，返回值为 `mkdssp` 输出。我的接入建议是：该 API 仅用于快速试验，不建议作为系统正式执行路径，因为网络依赖和配额边界不适合主工作流。

### Suggested Adapter Contract

建议输入参数：

- `input_structure`
- `output_format`：`mmcif | dssp`
- `calculate_accessibility`
- `chain_filter`（如果后续只评估特定链）
- `execution_mode`：`local | remote_api`

建议输出产物：

- `annotated_structure`
- `secondary_structure_table`
- `structure_stats`

建议在后处理阶段统一抽取：

- 各二级结构字符计数与比例：`H/E/G/I/P/T/S/B/coil`
- 每残基 label
- 可及性指标（若启用）
- 链级 summary

### Failure Handling And Recovery Mapping

建议至少覆盖：

- `DSSP_BINARY_MISSING`
- `DSSP_INPUT_FORMAT_UNSUPPORTED`
- `DSSP_INPUT_INVALID_STRUCTURE`
- `DSSP_ACCESSIBILITY_DISABLED`
- `DSSP_REMOTE_API_UNAVAILABLE`
- `DSSP_OUTPUT_PARSE_ERROR`

恢复策略建议：

- retry：仅针对临时文件或 API 网络问题。
- patch：将输入统一转换为 mmCIF；关闭 accessibility；改走本地执行。
- replan：如果 DSSP 只作为补充注释，可在失败时保留主结构结果并显式标记“缺少 DSSP 注释”。

### Integration Notes For This Project

- `DSSP` 应作为结构注释工具，而不是结构预测工具写入 ToolKG。
- 建议把单字符标签进一步标准化到项目内部 schema，避免后续报告层直接依赖原始格式。
- 若未来需要 `Q3/Q8` 聚合，应在 Adapter 或 summarizer 层集中实现，不要散落在实验脚本中。

### References

- 官方仓库：https://github.com/PDB-REDO/dssp
- DSSP 主页：https://pdb-redo.eu/dssp
- DSSP 下载与本地使用说明：https://pdb-redo.eu/dssp/download
- DSSP API 说明：https://pdb-redo.eu/dssp/api-doc
- DSSP 输出格式说明：https://pdb-redo.eu/dssp/about

---

## Inspect AI

### Introduction

Inspect AI 是 UK AI Security Institute 开源的评测框架，重点支持 agent、tool use、multi-agent、sandbox 等复杂评测场景。官方主页明确列出了 tool calling、MCP tools、内置 bash/python/web 工具，以及对外部 agent（如 Codex CLI）的支持。

对 Issue #172 的横向对比来说，Inspect AI 很适合作为主评测平台，因为它天然覆盖：

- agent/tool loop
- 多步任务日志
- tool-use 行为观察
- browser / CLI 型 agent 评测

### Installation

官方 quickstart：

```bash
pip install inspect-ai
```

评测运行既可以走 CLI，也可以直接走 Python API。

### Recommended Integration Pattern

建议接入位置：

- `scripts/benchmarks/inspect_issue172.py`
- `output/experiment/w12-expr-3/issue172-horizontal/inspect/`

建议用法：

1. 用固定 dataset 构造 `Task`。
2. 用统一的 solver / agent wrapper 调用系统目标。
3. 用 scorer 记录最终输出与 tool-use 行为。
4. 把 Inspect 日志作为横向实验的主要 trace 产物。

### Quick Start

官方示例显示，`@task` 标注的任务可被 `inspect eval` 自动发现：

```python
from inspect_ai import Task, task
from inspect_ai.dataset import example_dataset
from inspect_ai.scorer import model_graded_fact
from inspect_ai.solver import chain_of_thought, generate, self_critique

@task
def theory_of_mind():
    return Task(
        dataset=example_dataset("theory_of_mind"),
        solver=[chain_of_thought(), generate(), self_critique()],
        scorer=model_graded_fact(),
    )
```

运行方式：

```bash
inspect eval theory.py --model openai/gpt-4
```

官方文档也给出了 Python 调用入口：

```python
from inspect_ai import eval
eval(theory_of_mind(), model="openai/gpt-4o")
```

### Logging And Artifacts

官方说明：默认 eval 日志写入当前目录下的 `./logs`，并可通过 `inspect view` 打开浏览器中的日志查看器。

```bash
inspect view
```

对本项目的含义：

- `./logs` 应重定向或归档到 `output/experiment/.../inspect/logs/`
- 每次横向实验必须保存日志路径、模型标识、预算、工具白名单
- Inspect 的 log viewer 很适合人工复核单个失败样本

### Suggested Integration Contract

建议统一记录：

- `dataset_id`
- `model_id`
- `tool_whitelist`
- `budget_config`
- `inspect_log_path`
- `sample_scores`
- `aggregate_scores`

### Integration Notes For This Project

- 如果要评测的是外部 agent 行为而不是单个 prompt，Inspect 应优先于 Promptfoo。
- Inspect 更适合作为“主评测平台”，因为它能完整记录工具轨迹和 agent transcript。
- 建议将 Inspect 结果作为 ground truth-like trace 层，供后续分析脚本复用。

### References

- 官方文档：https://inspect.aisi.org.uk/
- 官方 GitHub：https://github.com/UKGovernmentBEIS/inspect_ai

---

## LangSmith

### Introduction

LangSmith 是 LangChain 提供的 framework-agnostic 平台，用于 tracing、evaluation、prompt testing 和 deployment。官方文档强调它既可做离线评测，也可做在线监控，并支持对 experiments 做比较分析。

在本项目中的更合理定位是“观测与对比层”，不是主执行链路的一部分。

### Recommended Integration Pattern

建议接入位置：

- `scripts/benchmarks/langsmith_issue172.py`
- 平台端保存 experiment URL / dataset ID / run IDs

更适合承担的职责：

- 保存统一 dataset
- 跟踪每次 agent 运行 trace
- 对多轮实验做 compare
- 快速定位 regressions 和 improvements

### Setup

官方 quickstart 中，最小环境要求包括：

- `LANGSMITH_API_KEY`
- `OPENAI_API_KEY`（或其他模型提供方密钥）
- 如果做 tracing，还需要 `LANGSMITH_TRACING=true`

Python quickstart 安装示例：

```bash
pip install -U langsmith openai
```

如果要运行评测 quickstart，官方示例还使用：

```bash
pip install -U langsmith openevals openai
```

### Evaluation Pattern

LangSmith 官方把离线评测拆成三个关键部件：

- `Dataset`
- `Target function`
- `Evaluators`

SDK 方式的核心调用模式是：

```python
experiment_results = client.evaluate(
    target,
    data="Sample dataset",
    evaluators=[correctness_evaluator],
    experiment_prefix="first-eval-in-langsmith",
    max_concurrency=2,
)
```

这对本项目的价值在于：

- 可将我们已有实验样本集变成 LangSmith dataset
- 每次比较不同 agent / prompt / tool policy 时，直接形成可点击 experiment
- 方便把 trace 与评分结果放在同一平台下查看

### Comparison And Tracing

官方比较页面支持对多个 experiment 做 side-by-side comparison，并支持打开 trace 查看单条运行细节。对本项目最有价值的点：

- 可以直接比较不同实验的 feedback 分数
- 可以从比较视图跳转到 trace
- 可以利用 experiment metadata 作为图表标签

因此，建议在每次实验运行时附加 metadata：

- `freeze_id`
- `budget_policy`
- `tool_whitelist`
- `agent_variant`
- `dataset_version`

### Integration Notes For This Project

- LangSmith 更适合作为“可视化比对与追踪面板”，不是唯一评测结论来源。
- 如果团队希望快速回看单个失败样本的完整工具轨迹，LangSmith 的 trace UI 会比手工读日志更高效。
- 若要保证公平对比，必须把 prompt、dataset、tool whitelist 固定住，再用 experiment metadata 标记变量。

### References

- LangSmith 文档主页：https://docs.langchain.com/langsmith
- Evaluation quickstart：https://docs.langchain.com/langsmith/evaluation-quickstart
- Evaluation overview：https://docs.langchain.com/langsmith/evaluation
- Compare experiment results：https://docs.langchain.com/langsmith/compare-experiment-results
- Tracing quickstart：https://docs.langchain.com/langsmith/observability-quickstart

---

## MLflow GenAI Evaluation

### Introduction

MLflow 的 GenAI Evaluation 面向 LLM/agent 应用的系统化评测，核心接口是 `mlflow.genai.evaluate()`。官方文档明确将其定位为从开发到生产持续评估和监控 GenAI 应用的工具，并强调 trace-first 的评测方式。

对本项目而言，MLflow 最适合承担“实验版本化 + 指标记录 + trace 复用”的角色。

### Recommended Integration Pattern

建议接入位置：

- `scripts/benchmarks/mlflow_issue172.py`
- 实验输出继续落在 `output/experiment/...`，同时把关键指标写入 MLflow tracking server

更适合承担：

- 统一记录实验 run、参数、指标、产物
- 复用 traces 做离线评测，避免每次重跑 agent
- 用 scorer 评估最终输出与工具轨迹

### Setup

官方 agent evaluation 文档示例安装：

```bash
pip install --upgrade 'mlflow[genai]>=3.3' openai
```

本地启动 tracking server 的官方示例：

```bash
uvx mlflow server
```

### Evaluation Pattern

MLflow 官方把评测拆成三部分：

- `data`
- `predict_fn`
- `scorers`

典型调用：

```python
results = mlflow.genai.evaluate(
    data=eval_dataset,
    predict_fn=predict_fn,
    scorers=[
        exact_match,
        ToolCallCorrectness(),
        ToolCallEfficiency(),
    ],
)
```

若直接评估已记录的 traces，官方文档说明可以不提供 `predict_fn`，而是直接将 trace 集合传给 `mlflow.genai.evaluate()`。

### Why It Fits This Project

这对本项目尤其有价值，因为横向实验往往成本较高：

- 可以先跑一次 agent，把 traces 存下来。
- 后续修改 scorer 或评价标准时，直接复用 traces 重新打分。
- 对工具调用顺序、效率、轨迹完整性等 agent 行为有天然支持。

官方还提供了针对 tool use 的 built-in scorers，例如 `ToolCallCorrectness` 与 `ToolCallEfficiency`。

### Parallelization And Scaling

官方说明可通过设置 `MLFLOW_GENAI_EVAL_MAX_WORKERS` 调整后台并行评测线程数：

```bash
export MLFLOW_GENAI_EVAL_MAX_WORKERS=10
```

这对于批量横向实验有现实意义，但应注意统一并行度，避免不同平台因吞吐差异影响 wall-clock 指标。

### Integration Notes For This Project

- MLflow 最适合作为“结果账本”和“实验谱系管理层”。
- 如果我们已经有本地 `output/experiment` 目录结构，建议在脚本里做字段映射，而不是改变现有目录语义。
- 对 agent 评测，优先保存 traces，再做多轮 scorer 迭代。

### References

- MLflow GenAI Evaluation overview：https://mlflow.org/docs/latest/genai/eval-monitor/
- Evaluating agents：https://mlflow.org/docs/latest/genai/eval-monitor/running-evaluation/agents/
- Evaluating prompts：https://mlflow.org/docs/latest/genai/eval-monitor/running-evaluation/prompts/
- Evaluating traces：https://mlflow.org/docs/latest/genai/eval-monitor/running-evaluation/traces/

---

## Promptfoo

### Introduction

Promptfoo 是一个开源 CLI / library，面向 prompt、model、RAG pipeline 的评测与红队测试。官方文档强调它支持 declarative YAML、assertions、web viewer、CI/CD 和多 provider 对比。

对本项目而言，Promptfoo 更适合做“轻量回归和阈值断言”，而不是复杂 agent/tool loop 的主评测平台。

### Installation

官方常见启动方式：

```bash
npx promptfoo@latest init --example getting-started
```

运行评测与查看结果：

```bash
npx promptfoo@latest eval
npx promptfoo@latest view
```

也可使用全局安装或 brew 安装。

### Configuration Pattern

Promptfoo 的核心是 `promptfooconfig.yaml`。官方 getting started 中将配置拆为：

- `prompts`
- `providers`
- `tests`
- `assert`

简化示例：

```yaml
prompts:
  - 'Convert the following English text to {{language}}: {{input}}'
providers:
  - openai:gpt-5.2
  - openai:gpt-5-mini
tests:
  - vars:
      language: French
      input: Hello world
    assert:
      - type: contains
        value: 'Bonjour le monde'
```

### Recommended Integration Pattern

建议接入位置：

- `scripts/benchmarks/promptfoo/`
- `promptfooconfig.issue172.yaml`
- 输出导出到 `output/experiment/.../promptfoo/`

适合承担：

- Prompt regression checks
- 多 provider / 多 prompt 组合矩阵测试
- 在 CI 中执行轻量阈值断言

### Why It Is Secondary In This Project

官方文档显示 Promptfoo 非常适合 prompt/model 组合评测，但对复杂 agent 执行轨迹、工具调用细节的表达力不如 Inspect AI 或 MLflow trace。基于这一点，我建议：

- 将 Promptfoo 定位为“回归保护层”
- 不把它作为 Issue #172 的唯一结论来源
- 用于快速比较提示词或小范围参数改动是否越线

### Custom Provider Path

如果未来希望直接评测本项目而不是裸模型，Promptfoo 官方支持 Python provider。也就是说，可以通过 `file://provider.py` 的方式，把我们的系统封装成一个 provider，再让 Promptfoo 跑矩阵测试。

这很适合做：

- `tool whitelist` 固定后的黑盒回归
- 对单一步骤 prompt 的自动断言
- PR/CI 阶段的快速 smoke eval

### Integration Notes For This Project

- 最好把 Promptfoo 配置拆成多个小文件，按 use case 分治，而不是塞进一个超大 YAML。
- 只在适合 declarative assertions 的场景使用 Promptfoo；复杂 agent 轨迹评测交给 Inspect AI / MLflow。
- 如果要纳入 CI，应控制样本规模与 provider 成本。

### References

- 官方介绍：https://www.promptfoo.dev/docs/intro/
- Getting started：https://www.promptfoo.dev/docs/getting-started/
- Configuration guide：https://www.promptfoo.dev/docs/configuration/guide/
- Python provider：https://www.promptfoo.dev/docs/providers/python/

---

## OpenAI Evals（可选）

### Introduction

这里需要区分两个东西：

1. OpenAI 官方当前主推的是平台内的 Evals / Evals API / Dashboard 工作流。
2. `openai/evals` GitHub 仓库仍然存在，适合作为开源 eval harness 与 benchmark registry 参考，但官方仓库首页已经明确提示“现在也可以直接在 OpenAI Dashboard 中配置并运行 Evals”。

因此，对本项目的建议是：

- 如果目标是接入现行 OpenAI 平台能力，优先参考 `developers.openai.com` 的 Evals API 文档。
- 如果目标是复用历史开源基准或本地 harness，可以把 `openai/evals` 作为补充方案，但优先级低于 Inspect / LangSmith / MLflow。

### Recommended Integration Pattern

建议接入位置：

- `scripts/benchmarks/openai_evals/`

更适合承担：

- 对 OpenAI 模型或 OpenAI 风格评测工作流做补充验证
- 复用 Evals API 的 dataset / run / grading 模式
- 作为与 OpenAI 生态对齐的补充评测层

### Evals API Pattern

OpenAI 官方“Working with evals”文档给出的核心流程是：

1. 定义 eval（任务、数据 schema、testing criteria）
2. 上传测试数据文件（`purpose="evals"`）
3. 创建 eval run
4. 分析 run 结果

官方文档明确写到：

- 构建 eval 有三个步骤
- 创建 eval 是从描述一个 task 开始
- 测试数据可上传为 JSONL 文件
- 通过 `POST /v1/evals/{eval_id}/runs` 创建运行

这很适合做结构化、可回放的 prompt/model 评测。

### Quick Start Shape

根据官方文档，最小数据上传形式是：

```bash
curl https://api.openai.com/v1/files   -H "Authorization: Bearer $OPENAI_API_KEY"   -F purpose="evals"   -F file="@tickets.jsonl"
```

随后可创建 eval run：

```bash
curl https://api.openai.com/v1/evals/YOUR_EVAL_ID/runs   -H "Authorization: Bearer $OPENAI_API_KEY"   -H "Content-Type: application/json"   -d '{ ... }'
```

### openai/evals Repository

OpenAI 官方 `openai/evals` 仓库仍然说明其可以：

- 提供 benchmark registry
- 支持自定义 eval
- 用于更高级的 prompt chains 或 tool-using agents（通过 Completion Function Protocol）

但从当前官方信号看，它更像补充性开源框架，而非我们首选的平台接入路径。

### Why Optional In This Project

- 它与项目主实验体系的耦合度不如 Inspect AI / MLflow。
- 对复杂 agent/tool trace 的可视化与比较能力，不如 LangSmith / MLflow 成熟。
- 如果没有明确的 OpenAI 平台对齐需求，引入它会增加一套额外评测语义。

因此，我建议把它保留为“可选补充工具”，而不是近期主平台。

### References

- OpenAI Evals API guide：https://developers.openai.com/api/docs/guides/evals
- OpenAI Evals repository：https://github.com/openai/evals
