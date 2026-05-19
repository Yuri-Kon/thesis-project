const IDENTIFIER_LABELS: Record<string, string> = {
  objective: "目标",
  inputs: "输入",
  design_constraints: "设计约束",
  quality_constraints: "质量约束",
  structure_constraints: "结构约束",
  function_constraints: "功能约束",
  safety_constraints: "安全约束",
  execution_preferences: "执行偏好",
  planner_policy: "规划策略",

  task_kind: "任务类型",
  objective_type: "目标类型",
  objective_weights: "目标权重",
  goal_summary: "目标摘要",
  objective_description: "目标描述",
  sequence: "蛋白质序列",
  template_pdb: "模板 PDB",
  initial_artifacts: "初始产物",
  target_ligand: "目标配体",
  length_range: "长度范围",
  design_count: "设计数量",
  quality_metric: "质量指标",
  min_quality_score: "最低质量分",
  target_fold: "目标折叠",
  secondary_structure_bias: "二级结构偏好",
  motif_pattern: "基序模式",
  binding_partner: "结合对象",
  active_site_residues: "活性位点残基",
  safety_level: "安全等级",
  forbidden_motifs: "禁用基序",
  forbidden_functions: "禁用功能",
  organism: "物种",
  run_profile: "运行模式",
  max_runtime_min: "最长运行时间",
  tools_allowed: "允许工具",
  tools_excluded: "排除工具",
  require_plan_confirm: "需要计划确认",
  allow_replan: "允许重规划",

  de_novo_design: "从头设计",
  sequence_evaluation: "序列评估",
  template_constrained_design: "模板约束设计",
  stability_optimization: "稳定性优化",
  motif_scaffold_design: "基序骨架设计",
  binding_design: "结合设计",
  enzyme_like_design: "类酶设计",

  stability: "稳定性",
  structure: "结构",
  binding: "结合",
  activity: "活性",
  plddt: "pLDDT",
  ptm: "pTM",
  sequence_similarity: "序列相似性",
  custom_score: "自定义评分",
  alpha: "α 螺旋",
  beta: "β 折叠",
  mixed: "混合",
  none: "无",
  fast_smoke: "快速冒烟",
  balanced: "平衡",
  high_accuracy: "高精度",

  required: "必填",
  conditional: "条件必填",
  optional: "可选",
  advanced: "高级",
  condition: "条件",
  true: "是",
  false: "否",
  confirmed: "已确认",
  review: "待复核",
  user_explicit: "用户填写",
  llm_extract: "自动提取",
  system_default: "系统默认",
  kg_derived: "知识图谱",
  user_modified: "用户修改",

  accept: "批准",
  replan: "修改或请求重规划",
  continue: "继续原方案",
  cancel: "拒绝或取消",
  plan_confirm: "计划确认",
  patch_confirm: "补丁确认",
  replan_confirm: "重规划确认",

  blocked: "阻塞",
  degraded: "降级",
  available: "可用",
  unavailable: "不可用",
  ok: "通过",
  warn: "警告",
  block: "阻止",
  idle: "空闲",
  collecting: "收集中",
  needs_confirmation: "待确认",
  low: "低风险",
  medium: "中风险",
  high: "高风险",
};

const STATUS_LABELS: Record<string, string> = {
  UNKNOWN: "未知",
  CREATED: "已创建",
  PLANNING: "规划中",
  WAITING_PLAN_CONFIRM: "等待计划确认",
  PLANNED: "已规划",
  RUNNING: "运行中",
  WAITING_PATCH_CONFIRM: "等待补丁确认",
  WAITING_REPLAN_CONFIRM: "等待重规划确认",
  SUMMARIZING: "汇总中",
  DONE: "已完成",
  FAILED: "失败",
  CANCELLED: "已取消",
  WAITING_PATCH: "等待补丁",
  PATCHING: "补丁处理中",
  WAITING_REPLAN: "等待重规划",
  REPLANNING: "重规划中",
};

export function identifierLabel(value: string | null | undefined): string {
  if (!value) {
    return "无";
  }
  return IDENTIFIER_LABELS[value] ?? value;
}

export function supportLabel(supportLevel: string | null | undefined): string {
  if (supportLevel === "P0") {
    return "P0 已支持";
  }
  if (supportLevel === "P1") {
    return "P1 实验性";
  }
  if (supportLevel === "P2") {
    return "P2 暂不支持";
  }
  return supportLevel ?? "未知";
}

export function statusLabel(value: string | null | undefined): string {
  const normalized = value ?? "UNKNOWN";
  return STATUS_LABELS[normalized] ?? identifierLabel(normalized.toLowerCase());
}

export function booleanLabel(value: boolean): string {
  return value ? "是" : "否";
}

const BEIJING_TIME_FORMATTER = new Intl.DateTimeFormat("zh-CN", {
  timeZone: "Asia/Shanghai",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
});

export function formatBeijingTimestamp(value: string | null | undefined): string {
  if (!value) {
    return "无时间戳";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return `${BEIJING_TIME_FORMATTER.format(parsed)} 北京时间`;
}
