# 运行时自适应控制与 Lite Belief-State 形式化
<!-- SID:algo.runtime.formalization -->

## 1. 文档目的
<!-- SID:algo.runtime.scope -->

本文档用于把“面向高代价科研工作流的自适应工具链规划算法”中的运行时部分形式化，补齐以下内容：

- Lite belief-state 的变量设计与建模边界
- 六类 schema 的正式定义
- `runtime_adjustment` 的可复现公式
- 动作选择与 `stop` 语义
- 运行时观测到状态更新的正式映射

本文档是 [core-algorithm-spec.md](./core-algorithm-spec.md) 的支持性细化说明；算法 SSOT 仍以 `core-algorithm-spec.md` 为准。
理论对象、代表文献与代码落点的稳定映射见 [core-algorithm-theory-map.md](./core-algorithm-theory-map.md)。

## 2. 设计依据与建模立场
<!-- SID:algo.runtime.design_basis -->

### 2.1 建模立场

本课题面对的是高代价、长链路、可失败、可恢复、必须可审计的科研工作流，而不是低成本的单步 API 选择问题。

因此运行时控制应满足：

- 不做 full POMDP / full RL / full controller 重写
- 必须可解释、可配置、可审计、可复现
- 必须显式服务于 `retry -> patch -> replan`
- 运行时项只能修正静态排序，不能推翻可执行性校验与 FSM 约束

### 2.2 参考研究

以下研究为本设计提供原则性依据：

- Kaelbling, Littman, Cassandra, *Planning and Acting in Partially Observable Stochastic Domains*, 1998
  - https://doi.org/10.1016/S0004-3702(98)00023-X
  - 贡献：说明在部分可观测环境中应通过 belief-state 而非瞬时观测直接决策。
- Guy Shani, *Heuristics for Partially Observable Stochastic Contingent Planning*, 2024
  - https://arxiv.org/abs/2410.05870
  - 贡献：强调在部分可观测规划中，启发式必须显式考虑 stochastic effect 与 information value。
- Carrara et al., *Budgeted Reinforcement Learning in Continuous State Space*, 2019
  - https://arxiv.org/abs/1903.01004
  - 贡献：说明预算约束和风险约束需要被视为一等决策量，而不是后验附加项。
- Toolformer, 2023
  - https://arxiv.org/abs/2302.04761
  - 贡献：支持“何时调用工具”也是决策的一部分。
- Reflexion, 2023
  - https://arxiv.org/abs/2303.11366
  - 贡献：支持利用失败反馈形成结构化恢复。
- Tree of Thoughts, 2023
  - https://arxiv.org/abs/2305.10601
  - 贡献：支持保留多候选并在中途重新评估，而非一次性单轨迹执行。
- OSWorld, 2024
  - https://arxiv.org/abs/2404.07972
  - 贡献：强调必须以执行结果、恢复能力和外部环境稳健性评估 agent。
- Simmhan et al., *Reliable Data Pipelines Using Scientific Workflows*, 2009
  - https://www.microsoft.com/en-us/research/wp-content/uploads/2009/09/ReliablePipelines.pdf
  - 贡献：强调 fail-fast、同步记录 provenance、把 recovery baked into workflow design。

本课题采用的结论是：

- 用 Lite belief-state 表达“运行时不完全可观测但必须决策”的现实；
- 用 budget-aware / risk-aware / recovery-aware 的规则化更新与效用函数替代复杂学习控制器；
- 把 `stop` 视为一种合法、可审计、带理由的终止型控制动作，而不是异常。

## 3. Lite Belief-State：变量设计
<!-- SID:planner.runtime.belief_state_schema -->

### 3.1 设计原则

Lite belief-state 只保留对动作选择真正必要的隐状态，不试图完整重建环境。

保留标准：

- 能直接支持 `continue / patch_local / suffix_replan / stop`
- 能从现有 `StepResult / SafetyResult / EventLog / Snapshot` 稳定更新
- 能被实验和案例分析直接解释

### 3.2 持久化的核心状态量

建议持久化以下 5 个核心状态量：

1. `p_success`
   - 含义：继续当前链路后最终成功完成任务的估计概率
   - 取值范围：$[0,1]$
2. `p_structural_failure`
   - 含义：当前链路遭遇结构性失败、低质量结构结果或后续必然升级到 replan 的估计概率
   - 取值范围：$[0,1]$
3. `recovery_margin`
   - 含义：不丢失有效前缀的前提下，系统继续恢复的余量
   - 取值范围：$[0,1]$
4. `expected_remaining_cost`
   - 含义：从当前时刻到任务终止的剩余成本暴露
   - 取值范围：非负实数，可大于 $1$
   - 说明：该字段保留原始剩余成本估计，不直接承担预算压力语义
5. `evidence_sufficiency`
   - 含义：当前是否已经积累到足够证据支持继续进入更昂贵步骤
   - 取值范围：$[0,1]$

### 3.3 不持久化、按需派生的量

以下量不建议作为长期持久化主状态，而应由核心状态和上下文派生：

- `budget_pressure`
- `intervention_value`
- `goal_misalignment`
- `local_patchability`
- `prefix_preservability`

原因：

- 这些量对动作选择有帮助，但更依赖当前候选集、阶段或策略配置；
- 让它们派生可以减少状态漂移与快照耦合；
- 这些量更适合作为审计字段和动作解释字段。

### 3.4 派生量定义

#### `budget_pressure`

若任务显式给出预算上限 `budget_cap`：

$$
\operatorname{budget\_pressure}
= \operatorname{clip}\left(
\frac{\operatorname{expected\_remaining\_cost}}{\max(\operatorname{budget\_cap},0.1)},
0,1.5
\right)
$$

若任务未给出预算上限：

$$
\operatorname{budget\_pressure}
= \operatorname{clip}(\operatorname{expected\_remaining\_cost},0,1.5)
$$

因此：

- `expected_remaining_cost` 是可持久化的剩余成本估计；
- `budget_pressure` 是按当前预算上下文派生的归一化压力；
- 动作效用与 stop guard 使用 `budget_pressure`，不得把 `expected_remaining_cost` 直接误解释为 $[0,1]$ 压力。

#### `intervention_value`

`intervention_value` 用于估计“此时让人介入是否可能改善结果”，定义为：

$$
\operatorname{intervention\_value}
= \operatorname{clip}\left(
0.30\,\operatorname{uncertainty}
+ 0.25\,\operatorname{manual\_salvageability}
+ 0.25\,\operatorname{artifact\_salience}
+ 0.20\,\operatorname{decision\_gap},
0,1
\right)
$$

其中：

- $\operatorname{uncertainty}=1-\lvert\operatorname{best\_score}-\operatorname{second\_best\_score}\rvert$
- `manual_salvageability`：人是否有现实改写空间，如参数、工具白名单、预算、结构模板
- `artifact_salience`：当前是否已有足够 artifact 供人判断
- `decision_gap`：候选之间差距是否小到值得人工判断

解释：

- `intervention_value` 高，不代表必须人工介入；
- 它的主要作用是抑制“明明人可能救回来，却自动 stop”的情况。

## 4. 六类 Schema
<!-- SID:algo.schemas.overview -->

以下六类 schema 共同构成 Lite belief-state 与运行时动作选择的最小形式化接口：`cost`、`risk`、`recovery`、`state`、`observation`、`action_utility`。

### 4.1 Cost Schema
<!-- SID:algo.schema.cost -->

#### 4.1.1 成本组成

成本不等于单纯的 wall-clock 时间，而是剩余资源暴露。定义：

$$
\operatorname{Cost}
= 0.35\,\operatorname{ComputeCost}
+ 0.25\,\operatorname{LatencyCost}
+ 0.20\,\operatorname{OpportunityCost}
+ 0.15\,\operatorname{RecoveryCost}
+ 0.05\,\operatorname{HumanCost}
$$

各项均标准化到 $[0,1]$：

- `ComputeCost`
  - GPU/CPU/远程模型资源暴露
- `LatencyCost`
  - 预期排队、执行、网络等待暴露
- `OpportunityCost`
  - 在证据不足时仍进入高代价步骤的浪费风险
- `RecoveryCost`
  - 若当前后缀失败，补救成本有多高
- `HumanCost`
  - 触发 HITL 后的额外认知与时间成本

#### 4.1.2 单步成本先验

对每个工具 `tool_j` 定义先验元数据：

- `compute_cost_prior`
- `latency_cost_prior`
- `failure_impact_prior`
- `human_dependency_prior`
- `reliability_prior`
- `high_cost_flag`

则单步标准成本定义为：

$$
\operatorname{step\_cost}_j
= 0.40\,\operatorname{compute\_cost\_prior}_j
+ 0.25\,\operatorname{latency\_cost\_prior}_j
+ 0.20\,\operatorname{failure\_impact\_prior}_j
+ 0.15\,\operatorname{human\_dependency\_prior}_j
$$

#### 4.1.3 候选剩余成本先验

令 $R(\pi)$ 为候选 $\pi$ 在当前时刻尚未执行的步骤集合，$m_j$ 为阶段乘子：

- 高代价步骤：$m_j=1.25$
- 低成本证据步骤：$m_j=0.80$
- 其他步骤：$m_j=1.00$

则：

$$
\operatorname{remaining\_cost\_prior}(\pi)
= \operatorname{clip}\left(
\frac{\sum_{j \in R(\pi)} m_j\,\operatorname{step\_cost}_j}
{\max(\lvert R(\pi)\rvert,1)},
0,1
\right)
$$

#### 4.1.4 在线剩余成本

$$
\operatorname{expected\_remaining\_cost}_t
= \operatorname{clip}\left(
0.60\,\operatorname{expected\_remaining\_cost}_{t-1}
+ 0.40\left(
\operatorname{remaining\_cost\_prior}_t
+ 0.25\,\operatorname{recovery\_penalty}_t
+ 0.20\,\operatorname{observed\_overrun}_t
- 0.20\,\operatorname{completed\_credit}_t
\right),
0,1.5
\right)
$$

解释：

- `remaining_cost_prior_t`：基于当前候选后缀和工具元数据的先验暴露
- `recovery_penalty_t`：若已经进入 patch/replan，后续成本上调
- `observed_overrun_t`：当前步骤已发生显著超时、重试或队列等待
- `completed_credit_t`：完成高代价关键步骤后，后续暴露下降

实现层允许采用更直接的计数式更新：

$$
\operatorname{expected\_remaining\_cost}_t
= \max(\operatorname{total\_steps}-\operatorname{completed\_steps}+\operatorname{cost\_penalty},0)
$$

或在缺少显式进度计数时使用启发式一步衰减/惩罚。无论使用哪种方式，持久化字段都保持非负成本尺度；预算压力由本节派生公式单独计算。

### 4.2 Risk Schema
<!-- SID:algo.schema.risk -->

#### 4.2.1 风险组成

风险与成本分离。成本回答“贵不贵”，风险回答“坏结果概率高不高”。

定义：

$$
\operatorname{Risk}
= 0.45\,\operatorname{StructuralRisk}
+ 0.25\,\operatorname{ExecutionRisk}
+ 0.20\,\operatorname{SafetyRisk}
+ 0.10\,\operatorname{CouplingRisk}
$$

#### 4.2.2 候选风险聚合

对于候选 `pi`，每个剩余步骤都有 `step_risk_j`：

$$
\operatorname{step\_risk}_j
= 0.45\,\operatorname{structural\_risk\_prior}_j
+ 0.25\,\operatorname{execution\_risk\_prior}_j
+ 0.20\,\operatorname{safety\_risk\_prior}_j
+ 0.10\,\operatorname{coupling\_risk\_prior}_j
$$

候选整体风险：

$$
\operatorname{risk}(\pi)
= \operatorname{clip}\left(
0.60\,\max_j(\operatorname{step\_risk}_j)
+ 0.40\,\operatorname{mean}_j(\operatorname{step\_risk}_j),
0,1
\right)
$$

硬覆盖规则：

- 若 `SafetyResult.action = block`，则 $\operatorname{risk}(\pi)=1.0$
- 若候选存在未闭合 I/O 或 schema 违规，则不进入风险打分，直接判 infeasible

### 4.3 Recovery Schema
<!-- SID:algo.schema.recovery -->

#### 4.3.1 恢复性组成

定义以下恢复因子，均标准化到 $[0,1]$：

- `retry_budget_ratio`
- `local_patchability`
- `prefix_preservability`
- `evidence_reusability`

定义恢复性与恢复复杂度：

$$
\operatorname{recoverability}
= 0.30\,\operatorname{retry\_budget\_ratio}
+ 0.30\,\operatorname{local\_patchability}
+ 0.25\,\operatorname{prefix\_preservability}
+ 0.15\,\operatorname{evidence\_reusability}
$$

$$
\operatorname{recovery\_complexity}=1-\operatorname{recoverability}
$$

#### 4.3.2 恢复余量

$$
\operatorname{recovery\_margin}_t
= \operatorname{clip}\left(
0.50\,\operatorname{recovery\_margin}_{t-1}
+ 0.50\left(
0.35\,\operatorname{local\_patchability}_t
+ 0.30\,\operatorname{prefix\_preservability}_t
+ 0.20\,\operatorname{retry\_budget\_ratio}_t
+ 0.15\,\operatorname{evidence\_reusability}_t
- 0.25\,p_{\text{structural\_failure},t}
- 0.20\,\operatorname{budget\_pressure}_t
\right),
0,1
\right)
$$

解释：

- 高 `local_patchability`、高 `prefix_preservability`、高 `retry_budget_ratio` 提高恢复余量
- 高结构性失败压力和高预算压力降低恢复余量

### 4.4 State Schema
<!-- SID:algo.schema.state -->

#### 4.4.1 状态向量

Lite belief-state 记为：

$$
x_t = [p_{\text{success}},p_{\text{structural\_failure}},\operatorname{recovery\_margin},\operatorname{expected\_remaining\_cost},\operatorname{evidence\_sufficiency}]
$$

#### 4.4.2 初始化

对默认推荐候选 $\pi^\ast$：

$$
\begin{aligned}
p_{\text{success},0} &= \operatorname{clip}(\operatorname{static\_score}(\pi^\ast),0.15,0.85),\\
p_{\text{structural\_failure},0} &= \operatorname{clip}(\operatorname{risk}(\pi^\ast),0.10,0.90),\\
\operatorname{recovery\_margin}_0 &= \operatorname{clip}(1-\operatorname{recovery\_complexity}(\pi^\ast),0.10,0.90),\\
\operatorname{expected\_remaining\_cost}_0 &= \operatorname{remaining\_cost\_prior}(\pi^\ast),\\
\operatorname{evidence\_sufficiency}_0 &= \operatorname{cheap\_evidence\_coverage}(\pi^\ast).
\end{aligned}
$$

其中：

- $\operatorname{cheap\_evidence\_coverage}(\pi^\ast)$ 反映是否在高代价步骤前插入了低成本验证层

### 4.5 Observation Schema
<!-- SID:algo.schema.observation -->

#### 4.5.1 观测来源

运行时观测 `o_t` 仅允许来自：

- `StepResult.outputs`
- `StepResult.metrics`
- `StepResult.error_details`
- `SafetyResult.risk_flags`
- `SafetyResult.action`
- patch/replan 历史
- 已完成步骤与剩余后缀
- HITL 决策记录

#### 4.5.2 标准化观测分量

建议提取以下标准化观测：

- `quality_obs_t`
  - 结构置信度、objective 达成度、QC 通过度
- `failure_obs_t`
  - 是否失败、失败严重度、是否 retry exhausted
- `safety_obs_t`
  - `allow / warn / block`
- `budget_obs_t`
  - 当前步骤耗时、远程调用次数、超时与排队
- `agreement_obs_t`
  - Top-K 分数差距、候选分歧
- `progress_obs_t`
  - 已完成高代价步骤、是否保留成功前缀

#### 4.5.3 阶段特异观测

#### S1 序列探索

- 候选多样性
- 非法字符率
- 约束满足率

#### S2 结构映射

- `pLDDT`
- 结构预测是否超时
- 是否全部候选失败

#### S3 质量门禁

- reject code
- reject rate
- 结构完整性 / 低复杂度 / 非法输入

#### S4 结构精修

- 相对 baseline 的改进幅度
- 退化轮次
- rollback 是否发生

#### S5 目标打分

- top1-top2 score gap
- 是否达到 objective threshold
- 多指标分歧

### 4.6 Action-Utility Schema
<!-- SID:algo.schema.action_utility -->

#### 4.6.1 动作空间

第一版动作空间限定为：

- `continue`
- `patch_local`
- `suffix_replan`
- `stop`

`expand_candidates`、`shrink_candidates`、`request_hitl`、`full_replan` 视为后续扩展动作。

#### 4.6.2 动作效用

令：

$$
b=\operatorname{budget\_pressure},\quad
s=p_{\text{success}},\quad
f=p_{\text{structural\_failure}},\quad
r=\operatorname{recovery\_margin},\quad
e=\operatorname{evidence\_sufficiency}
$$

则：

$$
\begin{aligned}
U_{\text{continue}} &=
0.38s + 0.14e + 0.12r - 0.22f - 0.14b,\\
U_{\text{patch\_local}} &=
0.20s + 0.24r + 0.18\,\operatorname{local\_patchability}
+ 0.12\,\operatorname{evidence\_reusability}
- 0.14f - 0.12b,\\
U_{\text{suffix\_replan}} &=
0.18(1-s) + 0.20f + 0.16(1-r)
+ 0.18\,\operatorname{prefix\_preservability}
+ 0.14\,\operatorname{budget\_relief}
+ 0.14\,\operatorname{goal\_realignment},\\
U_{\text{stop}} &=
0.32(1-s) + 0.24b + 0.18(1-r)
+ 0.16\,\operatorname{safety\_terminality}
+ 0.10(1-\operatorname{intervention\_value}).
\end{aligned}
$$

解释：

- `continue` 偏好成功概率和证据充分度
- `patch_local` 偏好局部可修复且保留上下文
- `suffix_replan` 偏好结构性重配但保留前缀
- `stop` 偏好低成功率、高预算压力、低恢复余量、且人工帮助价值低

## 5. 运行时状态更新
<!-- SID:planner.algorithm.runtime_update_rules -->

### 5.1 `p_success`

令：

$$
\operatorname{success\_signal}_t\in[0,1],\quad
\operatorname{failure\_signal}_t\in[0,1],\quad
\operatorname{budget\_penalty}_t=\operatorname{clip}(\operatorname{budget\_pressure}_t,0,1)
$$

定义：

$$
\operatorname{logit}(p_{\text{success},t})
= \operatorname{clip}\left(
\operatorname{logit}(p_{\text{success},t-1})
+ 1.20\,\operatorname{success\_signal}_t
- 1.40\,\operatorname{failure\_signal}_t
- 0.60\,\operatorname{budget\_penalty}_t,
-3.5,3.5
\right)
$$

$$
p_{\text{success},t}
= \operatorname{sigmoid}\left(\operatorname{logit}(p_{\text{success},t})\right)
$$

建议将 `success_signal_t` 分解为：

$$
\operatorname{success\_signal}_t
= 0.35\,\operatorname{quality\_pass}
+ 0.25\,\operatorname{objective\_progress}
+ 0.20\,\operatorname{prefix\_stability}
+ 0.20\,\operatorname{cheap\_gate\_success}
$$

建议将 `failure_signal_t` 分解为：

$$
\operatorname{failure\_signal}_t
= 0.35\,\operatorname{hard\_failure}
+ 0.25\,\operatorname{retry\_exhausted}
+ 0.20\,\operatorname{safety\_warn\_block}
+ 0.20\,\operatorname{cost\_overrun}
$$

### 5.2 `p_structural_failure`

令：

$$
\operatorname{structural\_failure\_signal}_t\in[0,1],\quad
\operatorname{structural\_recovery\_signal}_t\in[0,1]
$$

定义：

$$
\operatorname{logit}(p_{\text{structural\_failure},t})
= \operatorname{clip}\left(
\operatorname{logit}(p_{\text{structural\_failure},t-1})
+ 1.50\,\operatorname{structural\_failure\_signal}_t
- 1.00\,\operatorname{structural\_recovery\_signal}_t,
-3.5,3.5
\right)
$$

$$
p_{\text{structural\_failure},t}
= \operatorname{sigmoid}\left(\operatorname{logit}(p_{\text{structural\_failure},t})\right)
$$

建议：

$$
\operatorname{structural\_failure\_signal}_t
= 0.45\,\operatorname{low\_structure\_confidence}
+ 0.25\,\operatorname{qc\_structural\_reject}
+ 0.20\,\operatorname{repeated\_structure\_failure}
+ 0.10\,\operatorname{safety\_structure\_flag}
$$

$$
\operatorname{structural\_recovery\_signal}_t
= 0.60\,\operatorname{high\_conf\_structure\_success}
+ 0.40\,\operatorname{stable\_refinement\_gain}
$$

### 5.3 `evidence_sufficiency`

定义：

$$
\operatorname{evidence\_sufficiency}_t
= \operatorname{clip}\left(
0.70\,\operatorname{evidence\_sufficiency}_{t-1}
+ 0.30\left(
0.40\,\operatorname{cheap\_validation\_coverage}
+ 0.30\,\operatorname{candidate\_agreement}
+ 0.30\,\operatorname{metric\_completeness}
\right),
0,1
\right)
$$

解释：

- 如果缺少 QC、结构置信度、objective gap 等关键度量，`metric_completeness` 下降；
- 如果 Top-K 差距很大且存在廉价验证信号，`candidate_agreement` 升高；
- 如果高代价步骤前没有任何廉价门禁，`cheap_validation_coverage` 下降。

### 5.4 当前实现的确定性更新表

为保持工程可审计性，当前 $B(x_t,o_t,h_t)$ 采用确定性规则表，而不是学习到的 Bayesian transition model。通用形式为：

$$
x_{t+1}=B(x_t,o_t,h_t)
$$

当前实现可等价表示为：

$$
\begin{aligned}
s_{t+1} &= \operatorname{clip}(s_t+\delta_s(o_t,h_t)),\\
f_{t+1} &= \operatorname{clip}(f_t+\delta_f(o_t,h_t)),\\
r_{t+1} &= \operatorname{clip}(r_t+\delta_r(o_t,h_t)),\\
c_{t+1} &= \max(0,\operatorname{C\_update}(c_t,o_t,h_t)),\\
e_{t+1} &= \operatorname{clip}(0.70e_t+0.30\,\operatorname{evidence\_signal}_t).
\end{aligned}
$$

其中：

$$
\operatorname{evidence\_signal}_t
= 0.40\,\operatorname{cheap\_validation\_coverage}_t
+ 0.30\,\operatorname{candidate\_agreement}_t
+ 0.30\,\operatorname{metric\_completeness}_t
$$

下表与实现中的 `BELIEF_STATE_UPDATE_RULES` 对齐。表中 $n_{\text{warn}}$ / $n_{\text{block}}$ 表示对应安全标记数量；$p,q,g$ 均先裁剪到 $[0,1]$；未列字段保持不变。

| 观测信号 | 触发条件 | $\delta_s$ | $\delta_f$ | $\delta_r$ | $c_t$ 更新 | $e_t$ 更新 | 解释 |
| --- | --- | ---: | ---: | ---: | --- | --- | --- |
| `step_result.success` | 任意步骤成功 | $+0.12$ | $-0.08$ | $+0.06$ | $\operatorname{cost\_reward}\mathrel{+}=0.35$；无进度计数时约为 $c_t-1.35$ | 进入平滑项 | 完成一步提高链路可行性并释放恢复余量 |
| `step_result.success@structural` | 结构阶段或结构工具成功 | $+0.04$ | $-0.05$ | $0$ | $0$ | 进入平滑项 | 结构验证降低潜在结构失败压力 |
| `step_result.failed` | 任意步骤失败 | $-0.18$ | $+0.14$ | $-0.12$ | $\operatorname{cost\_penalty}\mathrel{+}=0.75$；无进度计数时约为 $c_t+1.25$ | 进入平滑项 | 失败降低当前后缀可信度并增加剩余成本暴露 |
| `step_result.failed@structural` | 结构阶段或结构工具失败 | $0$ | $+0.08$ | $0$ | $0$ | 进入平滑项 | 结构失败更强地指向 suffix replan |
| `step_result.retry_exhausted` | 步骤 metrics 标记 retry exhausted | $-0.05$ | $0$ | $-0.06$ | $\operatorname{cost\_penalty}\mathrel{+}=0.40$ | 进入平滑项 | retry 耗尽会消耗局部恢复空间 |
| `step_result.skipped` | 步骤被跳过 | $-0.02$ | $0$ | $0$ | $\operatorname{cost\_penalty}\mathrel{+}=0.15$ | 进入平滑项 | skipped 是弱负证据与小成本残留 |
| `safety_result.warn` | SafetyAgent 返回 warn | $-0.04-0.01n_{\text{warn}}$ | $+0.05$ | $-0.03$ | $\operatorname{cost\_penalty}\mathrel{+}=0.25$ | candidate agreement $-0.08$ 后进入平滑项 | 安全警告降低信心但不终止路线 |
| `safety_result.block` | SafetyAgent 返回 block | $-0.18-0.02n_{\text{block}}$ | $+0.12+0.01n_{\text{block}}$ | $-0.16$ | $\operatorname{cost\_penalty}\mathrel{+}=0.75$ | candidate agreement $-0.18$ 后进入平滑项 | 安全阻断是强负证据和高恢复压力 |
| `failure_context.patch_local` | 恢复动作归一化为 `patch_local` | $-0.04$ | $0$ | $-0.07$ | $\operatorname{cost\_penalty}\mathrel{+}=0.60$ | candidate agreement $+0.04$ 后进入平滑项 | 局部修补保留前缀但消耗修复余量 |
| `failure_context.suffix_replan` | 恢复动作为 `suffix_replan` 或 `replan` | $-0.10$ | $+0.08$ | $-0.12$ | $\operatorname{cost\_penalty}\mathrel{+}=1.20$ | candidate agreement $-0.08$ 后进入平滑项 | 后缀重规划承认当前后缀不可靠 |
| `failure_context.stop` | 恢复动作为 `stop` | $-0.15$ | $0$ | 设为 $0$ | $0$ | candidate agreement $-0.08$ 后进入平滑项 | stop 在语义上耗尽恢复余量 |
| `objective_evidence.progress` | objective ranker 给出进展 `p` | $+0.04p$ | $0$ | $0$ | $0$ | 平滑前 $e_t\mathrel{+}=0.03p$ | 目标进展支持当前目标方向 |
| `objective_evidence.sufficiency` | objective ranker 给出证据充分度 `q` | $0$ | $0$ | $0$ | $0$ | 平滑前 $e_t\mathrel{+}=0.05q$ | 直接目标证据提升证据充分度 |
| `objective_evidence.gap` | objective ranker 给出目标差距 `g` | $0$ | $0$ | $+0.02g$ | $0$ | 进入平滑项 | 可见目标差距保留有用重排空间 |
| `progress_counters` | 有 `completed_steps,total_steps` | $0$ | $0$ | $0$ | $\max(\operatorname{total\_steps}-\operatorname{completed\_steps}+\operatorname{cost\_penalty},0)$ | 进入平滑项 | 显式进度覆盖启发式一步成本衰减 |

最后统一执行：

$$
s_{t+1},f_{t+1},r_{t+1},e_{t+1}\in[0,1],
\qquad c_{t+1}\ge 0
$$

## 6. `runtime_adjustment` 公式
<!-- SID:planner.algorithm.runtime_adjustment_formula -->

### 6.1 设计原则

`runtime_adjustment` 必须满足：

- 只作用于已通过可执行性校验的候选
- 只修正静态排序，不替代静态评分
- 上下界有限，避免 runtime 项压过静态可执行性和任务匹配项
- 能分解成“状态项 + 候选形状项”

### 6.2 统一公式

记：

$$
s_t=p_{\text{success}},\quad
f_t=p_{\text{structural\_failure}},\quad
r_t=\operatorname{recovery\_margin},\quad
c_t=\operatorname{expected\_remaining\_cost},\quad
e_t=\operatorname{evidence\_sufficiency},\quad
bp_t=\operatorname{clip}(\operatorname{budget\_pressure},0,1)
$$

定义：

$$
\Delta(\pi,x_t)
= k_s(s_t-0.5)\operatorname{Conf}(\pi)
+ k_e(2e_t-1)\max(\operatorname{Conf}(\pi),F_s(\pi))
- k_f f_t(1-\operatorname{RiskScore}(\pi))
+ k_r r_t\operatorname{RecoveryScore}(\pi)
- k_c bp_t(1-\operatorname{CostScore}(\pi))
+ k_a\operatorname{ActionBias}(\pi,x_t)
$$

其中：

- $\operatorname{Conf}(\pi)$：候选自身置信度或工程可靠性；
- $F_s(\pi)$：软可行性分数；
- $\operatorname{RiskScore}(\pi)=1-R_{\text{norm}}(\pi)$；
- $\operatorname{CostScore}(\pi)=1-C_{\text{norm}}(\pi)$；
- $\operatorname{RecoveryScore}(\pi)=1-\operatorname{Rec}(\pi)$；
- $\operatorname{ActionBias}(\pi,x_t)$：根据候选类型、恢复余量、预算压力和前缀保留价值形成的小幅偏置。

`ActionBias` 的解释语义：

- patch 候选在 fallback/recovery 充足时加分；
- suffix_replan 在结构性失败压力高且保留前缀可行时加分；
- stop 是 terminal action；对普通候选排序只能以受保护方式影响，不得绕过 stop guard。

实现中该理论对象由 `metadata.runtime_adjustment.action_bias` 承载，包含：

- `action`
- `value`
- `factors`
- `source_refs`

每个 factor 同时保留工程解释 `message` 与论文展示层可用的理论字段：

$$
\operatorname{term}\in
\{\operatorname{recovery\_margin},\operatorname{budget\_pressure},
\operatorname{evidence\_sufficiency},\operatorname{ActionBias},
\operatorname{recoverability},\ldots\}
$$

$$
\operatorname{formula\_ref}\in
\{\operatorname{Eq.(runtime\_delta)},\operatorname{Eq.(ActionBias)}\}
$$

为避免单次观测过度影响排序：

$$
\Delta(\pi,x_t)\in[-0.35,0.35]
$$

最终：

$$
U_\pi(\pi,x_t)
= \operatorname{clip}\left(S_{\text{post}}(\pi)+\Delta(\pi,x_t),0,1\right)
$$

其中 $S_{\text{post}}(\pi)$ 表示用后验目标评分 $G_{\text{post}}(\pi;g,o_t)$ 替换静态目标项后的基础分。无后验证据时，$S_{\text{post}}(\pi)=S_{\text{static}}(\pi)$。实现中，完成 posterior objective binding 后的 `score_breakdown.overall` / `static_score` 对应该基础分，`final_score` 对应 $S_{\text{post}}(\pi)+\Delta(\pi,x_t)$ 的裁剪结果。

### 6.3 常量来源

常量取值遵循以下原则：

- 绝对值不超过 $0.18$ 的项是“二级修正项”
- $0.10 \sim 0.18$ 范围用于状态主修正
- $[-0.35,0.35]$ 的总截断范围保证 static score 仍是主导项
- 风险与预算惩罚项略强于正向奖励项，以符合高代价科研工作流中的保守偏好

换言之，常量不是来自统计学习，而是来自如下可解释约束：

- 不能因为一次局部成功就把高风险链路抬得过高
- 不能因为一次局部失败就让一个本可 patch 的链路立即崩塌
- 不能让 runtime 调整抹掉 static feasibility 的作用

## 7. 优先级冲突处理
<!-- SID:planner.algorithm.action_priority_resolution -->

#### 7.1 硬约束优先级

以下情况优先于效用比较：

1. `SafetyResult.action = block`
   - `continue` 禁用
   - 优先 `suffix_replan`
   - 若无可保留前缀或人工帮助价值极低，则允许 `stop`
2. schema / I-O / tool availability 违规
   - 当前候选直接淘汰
   - 若问题局部可修，走 `patch_local`
   - 否则走 `suffix_replan`
3. 终止态与 WAITING 语义
   - 任何自动动作不得跳过 snapshot / event log / pending action 规则

#### 7.2 软冲突优先级

在无硬覆盖时采用如下 tie-break：

1. `patch_local` 优先于 `suffix_replan`
- 条件：$\operatorname{local\_patchability}\ge 0.55$ 且 $\operatorname{recovery\_margin}\ge 0.30$
2. `suffix_replan` 优先于 `full_replan`
- 条件：$\operatorname{prefix\_preservability}\ge 0.40$
3. `stop` 只能在以下条件同时满足时压过 `suffix_replan`
   - $U_{\text{stop}}\ge 0.68$
   - $U_{\text{stop}}-\operatorname{second\_best}\ge 0.06$
   - $\operatorname{intervention\_value}\le 0.35$

## 8. `stop` 的系统语义
<!-- SID:planner.algorithm.stop_semantics -->

#### 8.1 基本语义

`stop` 表示：

- 当前剩余后缀不再值得继续投入；
- 推荐终止进一步高代价执行；
- 该终止应被当作一种“带理由的控制动作”，而不是异常。

#### 8.2 与现有架构的兼容设计

第一版不强制新增 FSM 状态。

推荐做法：

- 将 `stop` 作为 `replan_confirm` 候选集合中的一种特殊候选；
- 其语义为 `terminal_stop`，等价于“采用空后缀并结束任务”；
- 这样仍复用现有 `WAITING_REPLAN_CONFIRM` / `Decision` / `Snapshot` / `EventLog` 闭环。

即：

- `replan_mode = terminal_stop`
- `terminal_policy = stop`
- `preserve_prefix_until_step_index` 可保留已验证前缀
- `accept(stop)` 后写入终止快照并进入 `FAILED`

#### 8.3 为什么不默认映射到 `CANCELLED`

`CANCELLED` 表示用户主动终止；
`stop` 表示系统根据成本、风险与恢复性做出的“止损建议”。

因此：

- 用户主动停止：`CANCELLED`
- 系统建议并被接受的止损：`FAILED`，且失败原因应显式标记为
  - `economic_stop`
  - `evidence_exhausted`
  - `unsafe_to_continue`
  - `recovery_exhausted`

#### 8.4 自动 stop 规则

仅当以下条件满足时允许自动 stop：

- $\operatorname{allow\_auto\_stop}=\text{true}$
- $U_{\text{stop}}\ge 0.72$
- $p_{\text{success}}\le 0.20$
- $\operatorname{budget\_pressure}\ge 0.85$
- $\operatorname{recovery\_margin}\le 0.20$
- $\operatorname{intervention\_value}\le 0.25$

否则必须走 HITL。

## 9. 工程实现建议
<!-- SID:impl.runtime.integration_guidelines -->

#### 9.1 持久化字段

建议持久化：

- `runtime_state`
  - `p_success`
  - `p_structural_failure`
  - `recovery_margin`
  - `expected_remaining_cost`
  - `evidence_sufficiency`
  - `last_update_source`
- `runtime_observation_summary`
  - 最近一次关键观测
- `runtime_action_summary`
  - 最近一次动作建议及其证据

#### 9.2 审计字段

候选与事件中建议增加：

- `runtime_adjustment`
- `runtime_adjustment_breakdown`
- `suggested_action`
- `action_utility`
- `intervention_value`
- `budget_pressure`
- `terminal_policy`（若为 stop）

## 10. 本文档的实践含义

这套设计的核心不是把系统变成一个复杂 controller，而是：

- 用最小但关键的隐状态表达高代价工作流的运行时现实；
- 用有限、可解释、可测试的公式稳定地修正静态排序；
- 在继续、局部修补、保前缀重规划和止损之间作出可审计决策。
