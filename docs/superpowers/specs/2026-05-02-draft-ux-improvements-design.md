# Task Builder 草稿处理 UX 改进 — 设计文档

## 来源

- GitHub PR: [#323](https://github.com/Yuri-Kon/thesis-project/pull/323)
- 问题: Issue [#318](https://github.com/Yuri-Kon/thesis-project/issues/318)
- 基础设计: `docs/superpowers/specs/2026-05-02-draft-protection-design.md`

## 问题

当前 PR 实现存在两个 UX 缺陷：

1. **导航拦截对话框缺少"保存后离开"选项** — 用户只有 Continue Editing / Discard & New / Cancel 三个选择。点击任何侧边栏链接离开 Task Builder 时，无法保留草稿 — 只能丢弃或留下。
2. **草稿恢复下拉在恢复后消失** — `showRecovery = !intake && recentIds.length > 0` 意味着一旦加载了一个草稿，下拉就不可见了。用户无法切换到其他草稿，也无法在当前草稿与历史草稿之间切换。

参考邮箱草稿体验（Gmail）: 草稿应随时可保存、可恢复、可切换。

## 目标

- 导航拦截对话框新增 "Save & Leave" 按钮，允许用户保留草稿并离开
- 将仅恢复用途的下拉升级为始终可见的 Draft Switcher，支持切换
- 切换草稿前自动保存当前状态（auto-save before switch）
- 新增显式 "Save Draft" 按钮提供保存确认

## 设计变更

### 变更一：DraftProtectionDialog 四按钮布局

从三按钮改为四按钮，水平排列不加换行:

```
[Cancel]  [Discard & Leave]  [Save & Leave]  [Continue Editing]
```

| 按钮 | 样式 | 行为 |
|---|---|---|
| Cancel | 文本按钮 (muted) | 关闭对话框，不做任何事 |
| Discard & Leave | 边框按钮 (danger text) | 从 recent-intake-ids 移除当前 id，清空前端状态，导航 |
| **Save & Leave** | **实心主按钮 (dark)** | 保留在 recent-intake-ids，清空前端状态，导航 |
| Continue Editing | 边框按钮 (neutral) | 关闭对话框，留在当前草稿 |

按钮命名从 "Discard & New" 改为 "Discard & Leave"，因为拦截的导航目标不一定是 Task Builder（可能是 Overview 等），"New" 不准确。

新增 prop: `onSaveAndLeave: () => void`

### 变更二：Draft Switcher（替换 Recovery Dropdown）

**显示条件** 从 `!intake && recentIds.length > 0` 改为 `recentIds.length > 0`。无论是否有活跃 intake，只要有历史草稿就显示。

**UI**: 保持原生 `<select>` 元素，与现有的 `.recovery-select` 样式保持一致。当前草稿的 option 标记 `(current)` 并设为 `disabled`，防止重复选择。下拉标签改为 "Drafts"。

**切换行为（auto-save before switch）**:
1. 用户在下拉中选择另一条草稿
2. 如果当前有活跃 intake 且已创建（有 intake_id）: 调用 `patchTaskIntake` 确保服务器最新
3. 如果当前有活跃 intake 但未创建（无 intake_id）: 自动调用 `createTaskIntake`（如果 API 要求先创建），然后加入 `recent-intake-ids`
4. 调用 `GET /task-intakes/{selectedId}` 加载选中草稿
5. 保存失败时留在当前草稿并显示错误提示

不弹出确认对话框 — 切换是无摩擦的，类比 Gmail 草稿切换。

### 变更三：Save Draft 按钮

- 位于 `builder-hero-actions` 区域，仅在 `intake !== null` 时显示
- 点击后调用 `patchTaskIntake` 将当前字段推送到服务器
- 成功后以临时状态（如 pill 变为 "Saved" 2 秒）提供视觉确认
- 同时 `addDraftId` 将当前 id 提到 `recent-intake-ids` 首位

## 涉及文件

| 文件 | 改动 |
|------|------|
| `src/api/frontend/src/components/DraftProtectionDialog.tsx` | +1 prop `onSaveAndLeave`，+1 按钮，按钮文案调整，布局 |
| `src/api/frontend/src/pages/TaskBuilderPage.tsx` | 恢复下拉→Draft Switcher，+Save Draft 按钮，+auto-save 切换逻辑，对话框集成 |
| `src/api/frontend/src/main.tsx` | `handleResolveDraftNavigate` 新增 `"save"` action |
| `src/api/frontend/src/styles/app.css` | 可能需要微调对话框按钮间距或最大宽度 |

## App 协调变更

`handleResolveDraftNavigate` action 类型从 `"continue" | "discard" | "cancel"` 扩展为:

```tsx
(action: "continue" | "discard" | "save" | "cancel") => {
  if (action === "discard" && draftNavigateHref) {
    window.location.href = draftNavigateHref; return;
  }
  if (action === "save" && draftNavigateHref) {
    window.location.href = draftNavigateHref; return;
  }
  setDraftNavigateHref(null);
}
```

`"save"` 与 `"discard"` 的区别仅在 TaskBuilderPage 侧: save 保留 `recent-intake-ids` 条目，discard 移除。

## 错误处理

- auto-save 失败（网络错误）: 留在当前草稿，显示 ErrorNotice，不加载目标草稿
- auto-save 时 404（当前草稿已被删除）: 从 `recent-intake-ids` 移除，自动创建新 intake 或直接切换到目标
- Save Draft 失败: ErrorNotice，不影响当前编辑

## 不影响

- `recent-intake-ids` localStorage 契约不变（仍然 string[], max 5）
- `POST/PATCH/confirm` API 契约不变
- 后端代码不变
- FSM / PendingAction / Decision 流程不变
- beforeunload 防护行为不变
