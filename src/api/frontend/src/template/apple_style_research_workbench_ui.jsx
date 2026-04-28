import React, { useMemo, useState } from "react";
import { motion } from "framer-motion";

const tasks = [
  {
    id: "task_0428_001",
    title: "Stable 120 aa de novo protein",
    status: "WAITING_PLAN_CONFIRM",
    priority: "Review needed",
    phase: "Planning",
    updated: "2 min ago",
    risk: "Low",
    score: 0.91,
  },
  {
    id: "task_0428_002",
    title: "Sequence evaluation batch",
    status: "RUNNING",
    priority: "Autonomous",
    phase: "QC",
    updated: "14 min ago",
    risk: "Low",
    score: 0.74,
  },
  {
    id: "task_0427_018",
    title: "Template constrained refinement",
    status: "DONE",
    priority: "Report ready",
    phase: "Complete",
    updated: "Yesterday",
    risk: "Medium",
    score: 0.86,
  },
];

const candidates = [
  {
    name: "Plan A",
    tag: "Recommended",
    cost: "Medium",
    risk: "Low",
    eta: "34 min",
    detail: "Generate 8 candidates, fold with NIM ESMFold, then rank by pLDDT and hydrophobicity.",
  },
  {
    name: "Plan B",
    tag: "Fast smoke",
    cost: "Low",
    risk: "Low",
    eta: "12 min",
    detail: "Generate 3 candidates with lightweight QC first, defer high-accuracy scoring to a second pass.",
  },
  {
    name: "Plan C",
    tag: "High accuracy",
    cost: "High",
    risk: "Medium",
    eta: "76 min",
    detail: "Increase candidate count and add extra structural scoring before final report generation.",
  },
];

const timeline = [
  ["CREATED", "Task created from confirmed intake", "00:01"],
  ["PLANNING", "Planner generated three candidate plans", "00:08"],
  ["WAITING", "Human review required before execution", "00:11"],
  ["NEXT", "Decision will resume workflow from S2", "pending"],
];

const intakeFields = [
  ["task_kind", "de_novo_design", "llm_extract", "0.84"],
  ["objective_type", "stability", "llm_extract", "0.88"],
  ["length_range", "100–140 aa", "source_span", "0.91"],
  ["run_profile", "balanced", "user_modified", "confirmed"],
];

const TEST_CASES = [
  {
    name: "status tone maps waiting status to amber",
    actual: getStatusTone("WAITING_PLAN_CONFIRM"),
    expected: "amber",
  },
  {
    name: "status tone maps done status to green",
    actual: getStatusTone("DONE"),
    expected: "green",
  },
  {
    name: "candidate fallback keeps invalid index safe",
    actual: getCandidate(candidates, 99).name,
    expected: "Plan A",
  },
  {
    name: "mock data contains at least one pending review task",
    actual: tasks.some((task) => task.status.includes("WAITING")),
    expected: true,
  },
];

function getStatusTone(status) {
  if (typeof status === "string" && status.includes("WAITING")) return "amber";
  if (status === "DONE") return "green";
  return "blue";
}

function getCandidate(list, index) {
  if (!Array.isArray(list) || list.length === 0) {
    return {
      name: "No plan",
      tag: "Unavailable",
      cost: "—",
      risk: "—",
      eta: "—",
      detail: "No candidate is available.",
    };
  }
  return list[index] || list[0];
}

function runSmokeTests() {
  TEST_CASES.forEach((test) => {
    console.assert(
      Object.is(test.actual, test.expected),
      `[UI smoke test failed] ${test.name}: expected ${String(test.expected)}, got ${String(test.actual)}`
    );
  });
}

runSmokeTests();

function Icon({ name, size = 16, className = "" }) {
  const common = {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.9,
    strokeLinecap: "round",
    strokeLinejoin: "round",
    className,
    "aria-hidden": "true",
  };

  const paths = {
    activity: <><path d="M22 12h-4l-3 8L9 4l-3 8H2" /></>,
    alert: <><path d="M12 9v4" /><path d="M12 17h.01" /><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" /></>,
    arrow: <><path d="M5 12h14" /><path d="m13 6 6 6-6 6" /></>,
    box: <><path d="m3 7 9 5 9-5" /><path d="M12 22V12" /><path d="M21 7v10l-9 5-9-5V7l9-5 9 5Z" /></>,
    check: <><path d="m5 12 4 4L19 6" /></>,
    clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
    command: <><path d="M9 6V5a3 3 0 1 0-3 3h1" /><path d="M15 6V5a3 3 0 1 1 3 3h-1" /><path d="M9 18v1a3 3 0 1 1-3-3h1" /><path d="M15 18v1a3 3 0 1 0 3-3h-1" /><path d="M9 8h6v8H9z" /></>,
    cpu: <><rect x="7" y="7" width="10" height="10" rx="2" /><path d="M4 9h3" /><path d="M4 15h3" /><path d="M17 9h3" /><path d="M17 15h3" /><path d="M9 4v3" /><path d="M15 4v3" /><path d="M9 17v3" /><path d="M15 17v3" /></>,
    file: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" /><path d="M14 2v6h6" /><path d="M8 13h8" /><path d="M8 17h5" /></>,
    flask: <><path d="M9 3h6" /><path d="M10 3v6l-5 9a2 2 0 0 0 1.8 3h10.4A2 2 0 0 0 19 18l-5-9V3" /><path d="M8 15h8" /></>,
    gauge: <><path d="M12 14l4-4" /><path d="M3.3 18a9 9 0 1 1 17.4 0" /><path d="M7 18h10" /></>,
    git: <><circle cx="6" cy="6" r="2" /><circle cx="18" cy="18" r="2" /><circle cx="6" cy="18" r="2" /><path d="M6 8v8" /><path d="M8 6h4a4 4 0 0 1 4 4v6" /></>,
    layers: <><path d="m12 3 9 5-9 5-9-5 9-5Z" /><path d="m3 12 9 5 9-5" /><path d="m3 16 9 5 9-5" /></>,
    dashboard: <><rect x="3" y="3" width="7" height="8" rx="2" /><rect x="14" y="3" width="7" height="5" rx="2" /><rect x="14" y="12" width="7" height="9" rx="2" /><rect x="3" y="15" width="7" height="6" rx="2" /></>,
    filter: <><path d="M4 6h16" /><path d="M7 12h10" /><path d="M10 18h4" /></>,
    monitor: <><rect x="3" y="4" width="18" height="12" rx="2" /><path d="M8 20h8" /><path d="M12 16v4" /><circle cx="17" cy="8" r="1" /></>,
    pause: <><circle cx="12" cy="12" r="9" /><path d="M10 9v6" /><path d="M14 9v6" /></>,
    play: <><path d="M8 5v14l11-7-11-7Z" /></>,
    plus: <><path d="M12 5v14" /><path d="M5 12h14" /></>,
    search: <><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></>,
    settings: <><path d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z" /><path d="M19.4 15a1.8 1.8 0 0 0 .4 2l.1.1a2 2 0 0 1-2.8 2.8l-.1-.1a1.8 1.8 0 0 0-2-.4 1.8 1.8 0 0 0-1 1.6V21a2 2 0 0 1-4 0v-.1a1.8 1.8 0 0 0-1-1.6 1.8 1.8 0 0 0-2 .4l-.1.1a2 2 0 0 1-2.8-2.8l.1-.1a1.8 1.8 0 0 0 .4-2 1.8 1.8 0 0 0-1.6-1H3a2 2 0 0 1 0-4h.1a1.8 1.8 0 0 0 1.6-1 1.8 1.8 0 0 0-.4-2l-.1-.1A2 2 0 0 1 7 4l.1.1a1.8 1.8 0 0 0 2 .4 1.8 1.8 0 0 0 1-1.6V3a2 2 0 0 1 4 0v.1a1.8 1.8 0 0 0 1 1.6 1.8 1.8 0 0 0 2-.4l.1-.1A2 2 0 0 1 20 7l-.1.1a1.8 1.8 0 0 0-.4 2 1.8 1.8 0 0 0 1.6 1H21a2 2 0 0 1 0 4h-.1a1.8 1.8 0 0 0-1.5 1Z" /></>,
    shield: <><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z" /><path d="m9 12 2 2 4-5" /></>,
    sparkles: <><path d="m12 3 1.7 4.3L18 9l-4.3 1.7L12 15l-1.7-4.3L6 9l4.3-1.7L12 3Z" /><path d="m19 14 .8 2.2L22 17l-2.2.8L19 20l-.8-2.2L16 17l2.2-.8L19 14Z" /><path d="m5 14 .8 2.2L8 17l-2.2.8L5 20l-.8-2.2L2 17l2.2-.8L5 14Z" /></>,
    terminal: <><rect x="3" y="4" width="18" height="16" rx="2" /><path d="m7 9 3 3-3 3" /><path d="M13 15h4" /></>,
  };

  return <svg {...common}>{paths[name] || paths.activity}</svg>;
}

function Pill({ children, tone = "neutral" }) {
  const tones = {
    neutral: "bg-zinc-100 text-zinc-700 ring-zinc-200/70",
    blue: "bg-blue-50 text-blue-700 ring-blue-200/70",
    green: "bg-emerald-50 text-emerald-700 ring-emerald-200/70",
    amber: "bg-amber-50 text-amber-700 ring-amber-200/70",
    dark: "bg-zinc-950 text-white ring-zinc-900",
  };
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ring-1 ${tones[tone] || tones.neutral}`}>
      {children}
    </span>
  );
}

function GlassCard({ children, className = "" }) {
  return (
    <div className={`rounded-[28px] border border-white/70 bg-white/72 p-5 shadow-[0_20px_60px_rgba(15,23,42,0.08)] backdrop-blur-2xl ${className}`}>
      {children}
    </div>
  );
}

function MiniMetric({ label, value, icon = "activity" }) {
  return (
    <div className="rounded-3xl border border-zinc-200/70 bg-zinc-50/80 p-4">
      <div className="mb-3 flex items-center justify-between text-zinc-500">
        <span className="text-xs font-medium uppercase tracking-[0.18em]">{label}</span>
        <Icon name={icon} size={16} />
      </div>
      <div className="text-2xl font-semibold tracking-tight text-zinc-950">{value}</div>
    </div>
  );
}

function StructurePreview() {
  const bars = [76, 88, 91, 84, 72, 94, 89, 81, 86, 93, 79, 90];
  return (
    <GlassCard className="overflow-hidden p-0">
      <div className="flex items-center justify-between border-b border-zinc-200/70 px-5 py-4">
        <div>
          <div className="text-sm font-semibold text-zinc-950">Structure workspace</div>
          <div className="text-xs text-zinc-500">NGL Viewer placeholder · candidate synchronized</div>
        </div>
        <div className="flex gap-2">
          <Pill tone="green">cartoon</Pill>
          <Pill>pLDDT</Pill>
        </div>
      </div>
      <div className="grid gap-0 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="relative min-h-[310px] overflow-hidden bg-[radial-gradient(circle_at_30%_20%,rgba(59,130,246,0.20),transparent_30%),radial-gradient(circle_at_70%_55%,rgba(16,185,129,0.18),transparent_32%),linear-gradient(135deg,#f8fafc,#eef2ff)]">
          <motion.div
            initial={{ rotate: -8, scale: 0.96 }}
            animate={{ rotate: 4, scale: 1 }}
            transition={{ duration: 5, repeat: Infinity, repeatType: "reverse", ease: "easeInOut" }}
            className="absolute left-1/2 top-1/2 h-44 w-44 -translate-x-1/2 -translate-y-1/2 rounded-[42%] border border-blue-200/60 bg-white/35 shadow-2xl backdrop-blur-xl"
          >
            <div className="absolute left-6 top-8 h-16 w-28 rounded-full border-8 border-blue-300/80" />
            <div className="absolute bottom-8 right-5 h-24 w-16 rounded-full border-8 border-emerald-300/80" />
            <div className="absolute left-20 top-16 h-24 w-10 rotate-45 rounded-full border-8 border-indigo-300/80" />
          </motion.div>
          <div className="absolute bottom-5 left-5 rounded-2xl bg-white/70 px-3 py-2 text-xs text-zinc-600 shadow-sm backdrop-blur-xl">
            PDB · candidate_A_rank01.pdb
          </div>
        </div>
        <div className="space-y-5 bg-white/65 p-5">
          <div>
            <div className="mb-2 flex items-center justify-between text-xs text-zinc-500">
              <span>Residue confidence</span>
              <span>avg 88.4</span>
            </div>
            <div className="flex h-28 items-end gap-2 rounded-3xl bg-zinc-50 p-3">
              {bars.map((bar, index) => (
                <div key={index} className="flex flex-1 items-end">
                  <div className="w-full rounded-full bg-zinc-900/80" style={{ height: `${bar}%` }} />
                </div>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <MiniMetric label="pLDDT" value="88.4" icon="gauge" />
            <MiniMetric label="RMSD" value="1.8Å" icon="activity" />
          </div>
        </div>
      </div>
    </GlassCard>
  );
}

function CandidateComparison({ selected, setSelected }) {
  return (
    <GlassCard>
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-zinc-950">Pending review</div>
          <div className="text-xs text-zinc-500">Compare candidates before resuming workflow</div>
        </div>
        <Pill tone="amber"><Icon name="pause" size={13} className="mr-1" /> WAITING_PLAN_CONFIRM</Pill>
      </div>
      <div className="grid gap-3 xl:grid-cols-3">
        {candidates.map((item, index) => (
          <button
            key={item.name}
            onClick={() => setSelected(index)}
            className={`rounded-[24px] border p-4 text-left transition ${selected === index ? "border-zinc-950 bg-zinc-950 text-white shadow-2xl shadow-zinc-900/15" : "border-zinc-200/80 bg-white/70 text-zinc-950 hover:border-zinc-300 hover:bg-white"}`}
          >
            <div className="mb-4 flex items-center justify-between">
              <span className="text-lg font-semibold tracking-tight">{item.name}</span>
              <span className={`rounded-full px-2 py-1 text-[11px] ${selected === index ? "bg-white/15 text-white" : "bg-zinc-100 text-zinc-600"}`}>{item.tag}</span>
            </div>
            <p className={`mb-4 text-sm leading-6 ${selected === index ? "text-zinc-200" : "text-zinc-600"}`}>{item.detail}</p>
            <div className="grid grid-cols-3 gap-2 text-xs">
              <div><div className="opacity-60">cost</div><div className="font-medium">{item.cost}</div></div>
              <div><div className="opacity-60">risk</div><div className="font-medium">{item.risk}</div></div>
              <div><div className="opacity-60">eta</div><div className="font-medium">{item.eta}</div></div>
            </div>
          </button>
        ))}
      </div>
    </GlassCard>
  );
}

function TaskBuilder() {
  return (
    <GlassCard>
      <div className="mb-5 flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-zinc-950">Task Builder</div>
          <div className="text-xs text-zinc-500">Natural language intake with structured confirmation</div>
        </div>
        <Pill tone="blue"><Icon name="sparkles" size={13} className="mr-1" /> Draft ready</Pill>
      </div>
      <div className="rounded-[24px] border border-zinc-200/80 bg-zinc-50/80 p-4">
        <div className="mb-3 text-xs font-medium uppercase tracking-[0.18em] text-zinc-400">Raw request</div>
        <p className="text-sm leading-6 text-zinc-700">Design a stable small de novo protein around 120 aa, use a balanced run profile, and ask for plan confirmation before execution.</p>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {intakeFields.map(([k, v, source, conf]) => (
          <div key={k} className="rounded-3xl border border-zinc-200/70 bg-white/80 p-4">
            <div className="mb-2 text-xs text-zinc-400">{k}</div>
            <div className="mb-3 text-sm font-semibold text-zinc-950">{v}</div>
            <div className="flex items-center justify-between text-[11px] text-zinc-500">
              <span>{source}</span>
              <span>{conf}</span>
            </div>
          </div>
        ))}
      </div>
    </GlassCard>
  );
}

function TimelinePanel() {
  return (
    <GlassCard>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <div className="text-sm font-semibold text-zinc-950">Event timeline</div>
          <div className="text-xs text-zinc-500">WAITING → DECISION → RESUME chain</div>
        </div>
        <Pill>4 events</Pill>
      </div>
      <div className="space-y-3">
        {timeline.map(([state, desc, time], index) => (
          <div key={state} className="flex gap-3 rounded-3xl border border-zinc-200/70 bg-white/70 p-3">
            <div className="mt-1 flex h-7 w-7 items-center justify-center rounded-full bg-zinc-950 text-white">
              {index < 2 ? <Icon name="check" size={14} /> : index === 2 ? <Icon name="pause" size={14} /> : <Icon name="arrow" size={14} />}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-3">
                <div className="text-sm font-semibold text-zinc-950">{state}</div>
                <div className="text-xs text-zinc-400">{time}</div>
              </div>
              <div className="mt-1 text-sm text-zinc-600">{desc}</div>
            </div>
          </div>
        ))}
      </div>
    </GlassCard>
  );
}

function RightInspector({ selected }) {
  const plan = getCandidate(candidates, selected);
  return (
    <aside className="hidden h-full min-w-[320px] max-w-[360px] flex-col gap-4 xl:flex">
      <GlassCard>
        <div className="mb-4 flex items-center justify-between">
          <div>
            <div className="text-sm font-semibold text-zinc-950">Context inspector</div>
            <div className="text-xs text-zinc-500">Current decision boundary</div>
          </div>
          <Icon name="settings" size={18} className="text-zinc-400" />
        </div>
        <div className="space-y-3">
          <div className="rounded-3xl bg-zinc-950 p-4 text-white">
            <div className="mb-1 text-xs text-zinc-400">Selected candidate</div>
            <div className="text-xl font-semibold tracking-tight">{plan.name}</div>
            <div className="mt-3 text-sm leading-6 text-zinc-300">{plan.detail}</div>
          </div>
          <div className="grid grid-cols-3 gap-2">
            <MiniMetric label="Risk" value={plan.risk} icon="shield" />
            <MiniMetric label="Cost" value={plan.cost} icon="cpu" />
            <MiniMetric label="ETA" value={plan.eta} icon="clock" />
          </div>
        </div>
      </GlassCard>

      <GlassCard>
        <div className="mb-4 text-sm font-semibold text-zinc-950">Decision</div>
        <div className="grid gap-2">
          <button className="flex items-center justify-center gap-2 rounded-2xl bg-zinc-950 px-4 py-3 text-sm font-semibold text-white shadow-xl shadow-zinc-900/10">
            <Icon name="play" size={16} /> Accept and resume
          </button>
          <button className="rounded-2xl border border-zinc-200 bg-white px-4 py-3 text-sm font-semibold text-zinc-700">Request replan</button>
          <button className="rounded-2xl border border-zinc-200 bg-white px-4 py-3 text-sm font-semibold text-zinc-700">Continue without change</button>
          <button className="rounded-2xl border border-zinc-200 bg-white px-4 py-3 text-sm font-semibold text-zinc-500">Cancel task</button>
        </div>
      </GlassCard>

      <GlassCard>
        <div className="mb-4 flex items-center justify-between">
          <div className="text-sm font-semibold text-zinc-950">Artifacts</div>
          <Pill>5</Pill>
        </div>
        <div className="space-y-2 text-sm text-zinc-600">
          {["report.html", "candidate_A_rank01.pdb", "metrics.json", "events.log", "snapshot.json"].map((file) => (
            <div key={file} className="flex items-center gap-2 rounded-2xl bg-zinc-50 px-3 py-2">
              <Icon name="file" size={15} className="text-zinc-400" /> {file}
            </div>
          ))}
        </div>
      </GlassCard>
    </aside>
  );
}

function Sidebar({ selectedTask, setSelectedTask }) {
  const navItems = [
    ["dashboard", "Dashboard", "12"],
    ["pause", "Pending review", "3"],
    ["box", "Reports", "8"],
    ["terminal", "CLI handoff", ""],
  ];

  return (
    <aside className="hidden min-w-[280px] max-w-[300px] flex-col gap-4 lg:flex">
      <div className="flex items-center gap-3 px-2">
        <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-zinc-950 text-white shadow-xl shadow-zinc-900/20">
          <Icon name="command" size={18} />
        </div>
        <div>
          <div className="text-sm font-semibold text-zinc-950">Design Workbench</div>
          <div className="text-xs text-zinc-500">Research control surface</div>
        </div>
      </div>

      <GlassCard className="p-3">
        <div className="mb-3 flex items-center gap-2 rounded-2xl bg-zinc-100 px-3 py-2 text-sm text-zinc-500">
          <Icon name="search" size={16} /> Search task, event, artifact
        </div>
        <nav className="space-y-1">
          {navItems.map(([icon, label, count]) => (
            <button key={label} className="flex w-full items-center justify-between rounded-2xl px-3 py-2.5 text-sm font-medium text-zinc-700 hover:bg-zinc-100">
              <span className="flex items-center gap-2"><Icon name={icon} size={16} /> {label}</span>
              {count && <span className="text-xs text-zinc-400">{count}</span>}
            </button>
          ))}
        </nav>
      </GlassCard>

      <div className="px-2 text-xs font-semibold uppercase tracking-[0.18em] text-zinc-400">Recent tasks</div>
      <div className="space-y-3">
        {tasks.map((task, index) => (
          <button
            key={task.id}
            onClick={() => setSelectedTask(index)}
            className={`w-full rounded-[24px] border p-4 text-left transition ${selectedTask === index ? "border-zinc-950 bg-white shadow-2xl shadow-zinc-900/10" : "border-white/80 bg-white/55 hover:bg-white"}`}
          >
            <div className="mb-3 flex items-center justify-between gap-3">
              <Pill tone={getStatusTone(task.status)}>{task.status}</Pill>
              <span className="text-xs text-zinc-400">{task.updated}</span>
            </div>
            <div className="text-sm font-semibold leading-5 text-zinc-950">{task.title}</div>
            <div className="mt-2 flex items-center justify-between text-xs text-zinc-500">
              <span>{task.phase}</span>
              <span>{Math.round(task.score * 100)}%</span>
            </div>
          </button>
        ))}
      </div>
    </aside>
  );
}

export default function App() {
  const [selectedTask, setSelectedTask] = useState(0);
  const [selectedCandidate, setSelectedCandidate] = useState(0);
  const task = tasks[selectedTask] || tasks[0];

  const statusTone = useMemo(() => getStatusTone(task.status), [task.status]);

  return (
    <div className="min-h-screen overflow-hidden bg-[radial-gradient(circle_at_15%_0%,rgba(59,130,246,0.14),transparent_30%),radial-gradient(circle_at_85%_12%,rgba(16,185,129,0.12),transparent_28%),linear-gradient(180deg,#f8fafc_0%,#eef2f7_55%,#e7ebf0_100%)] p-4 text-zinc-950 md:p-6">
      <div className="mx-auto flex max-w-[1680px] gap-5">
        <Sidebar selectedTask={selectedTask} setSelectedTask={setSelectedTask} />

        <main className="min-w-0 flex-1 space-y-5">
          <header className="flex flex-wrap items-center justify-between gap-4 rounded-[32px] border border-white/70 bg-white/65 p-4 shadow-[0_20px_60px_rgba(15,23,42,0.07)] backdrop-blur-2xl">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-3xl bg-zinc-950 text-white">
                <Icon name="flask" size={20} />
              </div>
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h1 className="text-xl font-semibold tracking-tight md:text-2xl">{task.title}</h1>
                  <Pill tone={statusTone}>{task.status}</Pill>
                </div>
                <div className="mt-1 text-sm text-zinc-500">{task.id} · {task.phase} · updated {task.updated}</div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button className="rounded-2xl border border-zinc-200 bg-white px-3 py-2 text-sm font-medium text-zinc-700"><Icon name="filter" size={15} className="mr-1 inline" /> Filter</button>
              <button className="rounded-2xl bg-zinc-950 px-4 py-2 text-sm font-semibold text-white"><Icon name="plus" size={15} className="mr-1 inline" /> New intake</button>
            </div>
          </header>

          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <MiniMetric label="Current step" value="S2" icon="git" />
            <MiniMetric label="Candidates" value="3" icon="layers" />
            <MiniMetric label="Risk" value={task.risk} icon="alert" />
            <MiniMetric label="Sync" value="Live" icon="monitor" />
          </section>

          <TaskBuilder />
          <CandidateComparison selected={selectedCandidate} setSelected={setSelectedCandidate} />

          <section className="grid gap-5 2xl:grid-cols-[1.15fr_0.85fr]">
            <StructurePreview />
            <TimelinePanel />
          </section>
        </main>

        <RightInspector selected={selectedCandidate} />
      </div>
    </div>
  );
}
