# Week 4-6(1.14-2.03)规划

> Precondtion:
> - Week3 已完成 v0.4.2
> - ESMFold 已经跑通
> - FSM/HITL 完整可演示

## Week 4(01.14-01.20)

### 主题: ProteinToolKG最小可用形态(LLM规则成立)

### 核心目标

- ProteinToolKG 成为 Planner 唯一工具事实来源
- Planner 能基于 KG 做出可解释性规划

### 关键 Issue 设计

|模块|Issue|核心内容|验收标准|
|:---|:----|:-------|:-------|
|KG|ProteinToolKG Schema 定义|Tool/IOType/Capability/Constraint|Schema文档+示例|
|KG|ESMFold KG 实例化|IO、限制、语义角色完整|Planner 可检索|
|KG|ProteinMPNN KG 实例化|design工具加入|支持从头设计|
|Planner|KG-only tool_retrieval|禁止 prompt 硬编码工具|删除后仍可规划|
|Planner|KG 驱动候选解释|explanation 引用 KG 事实|日志可读|

### Week 4 可交付物

- ProteinToolKG v0.1(JSON/YMAL)
- Planner 在无工具描述 prompt 下仍可规划
- 可写论文方法部分草稿

---

## Week 5(01.21-01.27)

### 主题：从头蛋白质设计最小闭环(Design → Predict → Decide)

### 核心目标

- 完成一个最小从头设计 pipeline

> LLM → 序列设计 → 结构预测 → 失败/成功 → HITL → DONE

### 关键 Issue 设计

|模块|Issue|核心内容|验收标准|
|:---|:----|:-------|:-------|
|Tool|ProteinMPNNAdapter|序列生成|StepResult 正确|
|Planner|设计任务Plan模板|design + predict steps|KG 驱动|
|Executor|多 step 串联|Step1 → Step2|artifacts 链接|
|Safety|设计失败判定|无效结构/分数|WAITING_*|
|Summarizer|设计总结|输入/输出/失败解释|可读报告|

### Week 5 可交付物

- 一个完整的 "从头蛋白质设计" Demo
- 至少一个失败 → HITL → 修复案例
- 论文实验流程图素材

---

## Week 6(01.28 - 02.03)

### 主题：系统可部署性 + Demo 可视化

### 核心目标

- 降低 Demo 与运行门槛
- 提供 "可理解" 的系统界面

### 关键 Issue 设计

|模块|Issue|核心内容|验收标准|
|:---|:----|:-------|:-------|
|Infra|Demo 启动脚本|一键启动|新环境可运行|
|Frontend|任务状态页|FSM 状态可视化|WAITING_* 可见|
|Frontend|HITL 决策页|PendingAction 提交|API 对接|
|Observability|运行日志视图|EventLog 时间线|可审计|
|Docs|Demo 使用说明|面向评审|可复现|

### Week 6 可交付物

- 可演示 Web UI
- 非开发设也能理解系统流程
- Demo 稳定

---

## 未来一个月(02.04 - 03.01)总体主线

### 继续引入新工具

#### 结构预测与设计工具

引入更多结构预测与设计工具，例如：

- AlphaFold: 用于更准确地蛋白质结构预测，作为ESMFold的补充或替代
- Rosetta: 用于提供更全面的蛋白质设计与模拟能力

#### 评分与评估工具

引入用于评估设计效果的工具：

- DeepRank: 基于结构预测的评分工具，用于评估蛋白质设计的质量
- PyMOL: 用于结构的可视化和分析，帮助人工决策和修复

#### 优化与重建工具

随着系统逐渐稳定，引入优化和重建工具，例如：

- FoldX: 用于蛋白质稳定性评估和突变分析
- RosettaDesign: 提供针对蛋白质序列的优化算法，用于精细化设计

#### 其他辅助工具

- HADDOCK: 用于蛋白质-蛋白质对接的工具，能够为多体设计提供更多可能性
- MODeller: 用于蛋白质是结构的同源建模，以补充AlphaFold和ESMFold

### 稳定性与复现性

- 固定 Demo 场景
- 固定模型版本
- 固定输出示例
- CI/lint/docslice 保持通过

### 系统增强

- ExecutionBackend 抽象(为 Nextflow 预留)
- ProteinToolKG → Neo4j PoC(仅作为扩展验证，不替换主存储)


