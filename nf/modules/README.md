# Nextflow 模块说明

本目录包含用于蛋白质设计工作流的 Nextflow 模块。

## 模块列表

### ESMFold (`esmfold.nf`)

ESMFold 结构预测模块，通过 Nextflow 容器化执行。

**功能**：
- 输入：单条氨基酸序列
- 输出：PDB 结构文件 + pLDDT 置信度指标

**环境要求**：
- **必需**：Docker 或 Podman（用于容器化执行）
- **推荐**：NVIDIA GPU + CUDA（用于加速预测）
- Nextflow >= 21.04

**输入参数**：
```bash
--sequence      氨基酸序列（必需）
--task_id       任务 ID（必需）
--step_id       步骤 ID（必需）
--output_dir    输出目录（默认：output）
```

**输出文件**：
```
output/
├── pdb/
│   └── ${task_id}_${step_id}.pdb           # PDB 结构文件
├── metrics/
│   └── ${task_id}_${step_id}_metrics.json  # 预测指标（pLDDT 等）
└── artifacts/                              # 其他产物
```

**使用示例**：
```bash
nextflow run nf/modules/esmfold.nf \
  --sequence "MKFLKFSLLTAVLLSVVFAFSSCGDDDDTGYLPPSQAIQDLLKRMKV" \
  --task_id "task123" \
  --step_id "S1" \
  --output_dir "./output"
```

**容器配置**（生产环境）：
- 在 `esmfold.nf` 中取消注释容器配置：
  ```groovy
  container = 'ghcr.io/sokrypton/esmfold:latest'
  ```
- 确保 Nextflow 配置启用 Docker/Podman

**GPU 支持**：
- 在 Nextflow 配置文件中启用 GPU：
  ```groovy
  docker.runOptions = '--gpus all'
  ```

### 其他模块

- `protein_mpnn.nf` - ProteinMPNN 序列设计
- `rdkit_props.nf` - RDKit 属性计算

## 开发说明

### 测试模式

当前模块包含 mock 实现，用于测试和开发：
- 生成模拟 PDB 文件
- 返回模拟指标数据
- 不需要真实的 GPU 环境

### 切换到生产模式

1. 取消注释容器配置行
2. 替换 `script` 部分为真实的容器调用
3. 配置 GPU 支持（如需要）

## 环境前置条件总结

**最小要求（测试）**：
- Nextflow >= 21.04
- Bash shell

**生产要求（真实预测）**：
- Nextflow >= 21.04
- Docker >= 20.10 或 Podman >= 3.0
- NVIDIA GPU（推荐）+ CUDA toolkit
- 足够的内存（建议 >= 16GB）

## 故障排查

**问题：Nextflow 找不到模块**
- 解决：确保从项目根目录运行，或使用绝对路径

**问题：容器无法启动**
- 解决：检查 Docker/Podman 是否正确安装和运行
- 运行 `docker run hello-world` 测试

**问题：GPU 不可用**
- 解决：检查 NVIDIA 驱动和 CUDA 安装
- 运行 `nvidia-smi` 验证 GPU 可见性
- 确保容器运行时支持 GPU（如 nvidia-docker2）

## 参考文档

- [Nextflow 文档](https://www.nextflow.io/docs/latest/index.html)
- [ESMFold 论文](https://www.biorxiv.org/content/10.1101/2022.07.20.500902v2)
- [ESMFold 容器](https://github.com/sokrypton/ColabFold)
