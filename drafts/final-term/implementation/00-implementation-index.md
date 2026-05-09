# 系统实现章节素材索引

本文档用于汇总系统实现章节可直接使用的素材。材料来源以当前 `../thesis-project.dev/` 实现为主，结合设计文档中的架构边界整理，写作时应保持“原型实现/当前实现/后续扩展”之间的区别。

## 文件结构

| 文件 | 用途 | 适合放入论文的位置 |
| --- | --- | --- |
| `01-tech-stack-and-structure.md` | 技术栈、目录结构、关键选型理由 | 系统实现章节开头 |
| `02-backend-api-implementation.md` | 后端 API、数据契约、任务接入与 HITL 接口 | 后端实现与接口设计 |
| `03-frontend-workbench-implementation.md` | React 工作台、页面结构、状态加载与人工审查界面 | 前端实现与交互设计 |
| `04-workflow-runtime-implementation.md` | Workflow、PlanRunner、StepRunner、RuntimeState、恢复闭环 | 工作流执行与运行时控制 |
| `05-code-snippets.md` | 可直接放入论文的代码片段 | “关键代码实现”小节 |
| `06-figure-placeholders.md` | 截图与实现图占位符清单 | 系统实现截图、界面展示、流程图 |

## 系统实现主线

建议系统实现章节按以下逻辑组织：

1. 先说明技术栈：Python 3.12、FastAPI、Pydantic、React 19、Vite、TypeScript、文件日志/快照、ToolAdapter、远程模型适配等。
2. 再说明后端如何把自然语言任务转成结构化任务、暴露 Task/PendingAction/Decision/Timeline/API。
3. 接着说明前端工作台如何围绕 Dashboard、Task Detail、Pending Review、Event Timeline 组织操作员视图。
4. 最后说明工作流运行时如何执行 PlanStep、更新 WorkflowContext、进入 WAITING 状态、应用人工决策、写入快照与日志，并把 CEBRA-WP 的运行时动作映射到 patch/replan/stop。

## 论文表述注意点

- 当前 API 原型使用内存 `TASK_STORE` 保存任务记录，同时通过日志和快照模块保留事件与恢复信息；不要写成已经完成生产级数据库部署。
- Nextflow 在当前设计和实现语义中是单步执行后端边界，不是系统全局多步编排器。
- Web 端已有结构展示占位与 PDB 链接，但 3D Viewer 仍可表述为“预留结构可视化区域/产物链接入口”，不要写成完整三维渲染已完成。
- CEBRA-WP 的工程落点主要是候选评分、RuntimeState、runtime adjustment、action utility 与恢复动作选择，不应写成另起一个独立 Agent。

