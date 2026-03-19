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
