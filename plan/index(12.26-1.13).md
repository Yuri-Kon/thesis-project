# C 阶段三周执行计划
> 用途：  
> - 直接作为 **GitHub Project / Issue 列表**  
> - 或作为 **每周周报 / 里程碑跟踪表**

---

## Week 1（12.26 – 12.30）
### 主题：系统级重构落地（v0.3）

| Issue ID | 日期 | 模块 | Issue 标题 | 关键工作内容 | 产出/验收标准 |
|--------|------|------|-----------|-------------|--------------|
| #1 | 12.26 | Core / FSM | Task 状态与 FSM 重构 | 拆分 ExternalStatus / InternalStatus；保留 PATCHING / REPLANNING | FSM 与 architecture.md 完全一致 |
| #2 | 12.26 | Core / FSM | FSM 驱动点统一 | 状态变更仅允许发生在 Planner / Executor / Decision | 无隐式状态跳转 |
| #3 | 12.27 | Model | PendingAction 模型落地 | action_type + candidates + explanation | 可手动构造 WAITING_* |
| #4 | 12.27 | Model | Decision 模型落地 | DecisionChoice + 合法性校验 | 决策结构完整 |
| #5 | 12.27 | Model | TaskSnapshot 最小结构 | state / plan_version / step_index / artifacts | 可用于恢复 |
| #6 | 12.28 | Infra | EventLog 结构定义 | HITL 相关事件类型 | 事件可审计 |
| #7 | 12.28 | Infra | 关键节点强制写日志 | WAITING_* / DECISION_APPLIED 前后约束 | 可回放 |
| #8 | 12.29 | API | GET /tasks/{id} 重构 | WAITING_* 返回 pending_action | curl 可用 |
| #9 | 12.29 | API | Decision 提交接口 | POST /pending-actions/{id}/decision | FSM 正确推进 |
| #10 | 12.30 | Release | v0.3.0 收敛与对齐 | 文档与代码一致 | tag v0.3.0 |

**Week 1 可交付物：**
- ✅ v0.4.0
- ✅ FSM + HITL + Snapshot 结构完整

---

## Week 2（12.31 – 01.06）
### 主题：第一个真实工具接入（ESMFold）

| Issue ID | 日期 | 模块 | Issue 标题 | 关键工作内容 | 产出/验收标准 |
|--------|------|------|-----------|-------------|--------------|
| #11 | 12.31 | Tool | ESMFold 接入方案确认 | 本地 / 容器 / Nextflow 决策 | 接入路径确定 |
| #12 | 01.01 | Tool | ESMFoldAdapter 实现 | run() + 输出标准化 | StepResult 正确 |
| #13 | 01.02 | Executor | StepRunner 真实执行 | 执行时间/失败捕获 | artifacts 生成 |
| #14 | 01.03 | Executor | 真实失败场景测试 | 非法输入 / 超时 | WAITING_* 触发 |
| #15 | 01.03 | Planner | Patch / Replan 触发验证 | 规则版 Patch / Replan | 人工确认生效 |
| #16 | 01.04 | Summarizer | Summarizer 最小适配 | 基于真实结果输出 | 失败不影响 DONE |
| #17 | 01.05 | Demo | 端到端真实 Demo | 输入→ESMFold→总结 | 全链路跑通 |
| #18 | 01.06 | Release | v0.4.0 交付 | 打 tag + Demo | 可正式演示 |

**Week 2 可交付物：**
- ✅ v0.5.0
- ✅ 一个真实蛋白预测任务 Demo

---

## Week 3（01.07 – 01.13）
### 主题：稳定性、恢复与失败治理

| Issue ID | 日期 | 模块 | Issue 标题 | 关键工作内容 | 产出/验收标准 |
|--------|------|------|-----------|-------------|--------------|
| #19 | 01.07 | Infra | Snapshot 恢复验证 | 中断→恢复执行 | 可继续运行 |
| #20 | 01.08 | API | Decision 幂等性 | 重复提交 / 冲突 | 返回 409 |
| #21 | 01.09 | Executor | 多次失败治理 | 连续失败→Replan | FSM 正确 |
| #22 | 01.10 | System | 异常退出与重启 | 重启后状态恢复 | EventLog 回放 |
| #23 | 01.11 | Cleanup | 代码整理与注释 | 清理实验代码 | 可读性提升 |
| #24 | 01.12 | Demo | 最终演示准备 | 演示脚本 | 稳定展示 |
| #25 | 01.13 | Release | v0.4.2 交付 | 打 tag | 工程稳定版 |

**Week 3 可交付物：**
- ✅ v0.4.2
- ✅ 稳定、可恢复、可审计的真实工具系统


