# Task Builder 草稿保护与恢复 — 设计文档

## 来源

- GitHub Issue: [#318](https://github.com/Yuri-Kon/thesis-project/issues/318)
- 设计文档 SID: `interface.web_workspace.draft_protection` + `interface.task_intake.draft_recovery`
- 文件: `web-operator-workspace.md` + `structured-task-intake-design.md`

## 问题

用户在 Task Builder 中创建 intake 并填写结构化字段后，误点击 sidebar 导航或刷新页面会导致草稿丢失，且无法找回。

## 目标

- 活跃草稿存在时拦截导航，弹出确认对话框
- 浏览器刷新/关闭时触发 `beforeunload` 保护
- 提供草稿恢复入口

## 活跃草稿判定

`TaskIntakeSession.status` 为 `"collecting"` 或 `"needs_confirmation"` 时视为活跃草稿，触发保护。

## 架构决策

**跨组件通信方式**: Lift state to App。App 管理 `activeIntakeId`，TaskBuilderPage 通过 `onActiveIntakeChange` 回调上报，Sidebar/Dashboard 通过 props 接收拦截逻辑。符合项目现有 props 数据流模式，不引入全局状态或 context。

## 组件树与数据流

```
App
├─ activeIntakeId: string | null          ← 新增状态
├─ draftNavigateHref: string | null       ← 新增状态 (非空 → 触发 TaskBuilderPage dialog)
│
├─ WorkbenchSidebar
│   ├─ activeIntakeId: string | null      ← 新增 prop
│   └─ onDraftNavigate(href): void        ← 新增 prop (有活跃草稿时拦截)
│
├─ DashboardPage
│   ├─ activeIntakeId: string | null      ← 新增 prop
│   └─ onDraftNavigate(href): void        ← 新增 prop
│
└─ TaskBuilderPage
    ├─ onActiveIntakeChange(id|null):void ← 新增 prop (上报活跃草稿)
    ├─ draftNavigateHref: string | null   ← 新增 prop (接收拦截信号)
    ├─ onResolveDraftNavigate(action):void← 新增 prop (对话框结果回传 App)
    ├─ DraftProtectionDialog              ← portal 至 document.body
    ├─ DraftRecoverySelect                ← builder-hero 恢复下拉
    ├─ beforeunload 注册/注销
    └─ localStorage recent-intake-ids 管理
```

## 涉及文件

| 文件 | 改动 |
|------|------|
| `src/api/frontend/src/main.tsx` | App: 新增 `activeIntakeId` 状态 + `onActiveIntakeChange` 回调, 传递给子组件 |
| `src/api/frontend/src/pages/TaskBuilderPage.tsx` | 活跃草稿判定、beforeunload 注册、恢复下拉、对话框状态、localStorage 管理 |
| `src/api/frontend/src/components/DraftProtectionDialog.tsx` | **新文件**: 对话框组件, createPortal 渲染 |
| `src/api/frontend/src/components/WorkbenchSidebar.tsx` | 链接点击拦截, 新增 props |
| `src/api/frontend/src/pages/DashboardPage.tsx` | Inspector "New intake" 链接拦截, 新增 props |
| `src/api/frontend/src/styles/app.css` | 对话框/遮罩样式、动画 |

## DraftProtectionDialog 组件

```tsx
interface DraftProtectionDialogProps {
  intakeId: string;
  updatedAt: string;
  status: "collecting" | "needs_confirmation";
  onContinueEditing: () => void;
  onDiscardAndNew: () => void;
  onCancel: () => void;
}
```

- 通过 `createPortal` 渲染到 `document.body`, `z-index: 1000`
- `role="alertdialog"` + `aria-modal="true"`
- Escape 键 → `onCancel`, 点击遮罩不关闭
- Continue Editing 按钮自动聚焦 (默认焦点)
- 入场动画: 遮罩 `opacity 0→1` (150ms), 对话框 `scale(0.95→1)` (200ms ease-out)
- 三按钮: Continue Editing (主按钮, 深色), Discard & New (次要, 边框), Cancel (文本按钮)

## 导航拦截触发机制

App 是导航拦截的协调中心。它通过两个 prop 实现 Sidebar/Dashboard ↔ TaskBuilderPage 的通信:

- `activeIntakeId: string | null` — 从 TaskBuilderPage 上报至 App, App 分发给 Sidebar/Dashboard
- `draftNavigateHref: string | null` — App → TaskBuilderPage 的单向信号, TaskBuilderPage 通过 useEffect 监听并弹出 dialog

### 完整流程

```
Sidebar link click (on TaskBuilder view, activeIntakeId 非空)
  → e.preventDefault()
  → onDraftNavigate(targetHref)     // Sidebar → App
  → App: setDraftNavigateHref(href)  // App → TaskBuilderPage
  → TaskBuilderPage: useEffect 检测到 draftNavigateHref 非空
  → 显示 DraftProtectionDialog

用户选择:
  Continue Editing → onResolve('continue') → App 清空 draftNavigateHref
  Discard & New   → onResolve('discard')  → App 清空 intake 状态, 移除 localStorage, 执行导航
  Cancel          → onResolve('cancel')   → App 清空 draftNavigateHref
```

### WorkbenchSidebar

新增 props: `activeIntakeId: string | null`, `onDraftNavigate: (href: string) => void`

当前 view 为 `task_builder` 且 `activeIntakeId` 非空时, 点击任意 sidebar 链接 → `preventDefault()` + `onDraftNavigate(href)`。

### DashboardPage

新增 props: `activeIntakeId: string | null`, `onDraftNavigate: (href: string) => void`

Inspector 中的 "New intake" 链接同样拦截。

## 草稿恢复下拉

- 位于 `builder-hero` 区域, 仅在 `!intake && recentIds.length > 0` 时显示
- 原生 `<select>`, 数据源 `localStorage` key `recent-intake-ids`
- 每项展示 `intake_id` + `updated_at`
- 选择后通过 `GET /task-intakes/{id}` 恢复完整状态
- 404 时从列表移除并显示提示

## localStorage 契约

```
Key: recent-intake-ids
Value: string[]  (JSON array of intake_id)
Max length: 5

写入: createTaskIntake 成功 → unshift 头部
移除: confirmTaskIntake 成功 → 移除 / Discard & New → 移除 / 404 → 移除
截断: 长度 > 5 → 截断尾部
```

## beforeunload

- 活跃草稿时注册 `window.beforeunload` 监听器
- 处理函数仅设置 `e.returnValue = ""`，触发浏览器原生对话框
- 草稿确认/取消后移除监听器

## CSS 新增

```css
.draft-dialog-backdrop {
  position: fixed; inset: 0; z-index: 1000;
  background: rgba(0, 0, 0, 0.3);
  animation: draftDialogFadeIn 150ms ease-out;
}
.draft-dialog {
  position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
  z-index: 1001; background: var(--surface); border-radius: 12px;
  box-shadow: var(--shadow); padding: 28px 32px 24px; max-width: 440px; width: calc(100vw - 48px);
  animation: draftDialogScaleIn 200ms ease-out;
}
@keyframes draftDialogFadeIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes draftDialogScaleIn { from { transform: translate(-50%, -50%) scale(0.95); opacity: 0; } to { transform: translate(-50%, -50%) scale(1); opacity: 1; } }
```

## 错误处理

- 所有 localStorage 读写 try-catch (隐私模式/配额溢出)
- `GET /task-intakes/{id}` 404 → 从 localStorage 移除, 显示提示
- 恢复请求失败 → ErrorNotice, 不影响当前页面状态

## 不影响

- API 契约 (`POST/PATCH/confirm` 不变)
- Planner 的 ConfirmedTaskSpec
- FSM / PendingAction / Decision 流程
- 后端代码
