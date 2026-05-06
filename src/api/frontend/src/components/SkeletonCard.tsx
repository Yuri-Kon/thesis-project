/* ShimmerLine -- single shimmer bar */
function ShimmerLine({
  width,
  height = 14,
  delay = 0,
}: {
  width: string;
  height?: number;
  delay?: number;
}) {
  return (
    <div
      className="skeleton-stripe"
      style={{
        width,
        height,
        animationDelay: `${delay}ms`,
      }}
    />
  );
}

/* SkeletonMetricCard -- 80px, label + value */
export function SkeletonMetricCard({ delay = 0 }: { delay?: number }) {
  return (
    <div className="skeleton-card" style={{ minHeight: 72 }}>
      <ShimmerLine width="40%" height={12} delay={delay} />
      <ShimmerLine width="55%" height={22} delay={delay + 100} />
    </div>
  );
}

/* SkeletonListRow -- 56px, two text lines */
export function SkeletonListRow({ delay = 0 }: { delay?: number }) {
  return (
    <div className="skeleton-row">
      <ShimmerLine width="55%" height={14} delay={delay} />
      <ShimmerLine width="75%" height={12} delay={delay + 100} />
    </div>
  );
}

/* SkeletonInspectorCard -- 120px */
export function SkeletonInspectorCard({ delay = 0 }: { delay?: number }) {
  return (
    <div className="skeleton-card" style={{ minHeight: 100 }}>
      <ShimmerLine width="50%" height={14} delay={delay} />
      <ShimmerLine width="70%" height={12} delay={delay + 100} />
      <ShimmerLine width="60%" height={12} delay={delay + 200} />
    </div>
  );
}

/* SkeletonPanel -- 200px */
export function SkeletonPanel({ delay = 0 }: { delay?: number }) {
  return (
    <div className="skeleton-card" style={{ minHeight: 160 }}>
      <ShimmerLine width="35%" height={16} delay={delay} />
      <ShimmerLine width="80%" height={12} delay={delay + 100} />
      <ShimmerLine width="65%" height={12} delay={delay + 200} />
      <ShimmerLine width="50%" height={12} delay={delay + 300} />
    </div>
  );
}

/* SkeletonHero -- 90px */
export function SkeletonHero({ delay = 0 }: { delay?: number }) {
  return (
    <div className="skeleton-hero">
      <div style={{ display: "grid", gap: 8, flex: 1 }}>
        <ShimmerLine width="30%" height={26} delay={delay} />
        <ShimmerLine width="55%" height={14} delay={delay + 100} />
      </div>
    </div>
  );
}

/* MetricStrip -- 3-column skeleton metric area */
export function SkeletonMetricStrip({ delay = 0 }: { delay?: number }) {
  return (
    <div className="skeleton-metric-strip">
      <SkeletonMetricCard delay={delay} />
      <SkeletonMetricCard delay={delay + 150} />
      <SkeletonMetricCard delay={delay + 300} />
    </div>
  );
}

/* DashboardSkeleton -- Dashboard page full skeleton */
export function DashboardSkeleton() {
  return (
    <div className="dashboard-layout">
      <SkeletonHero delay={0} />
      <SkeletonMetricStrip delay={200} />
      <div className="skeleton-dashboard-grid">
        <div style={{ display: "grid", gap: 10 }}>
          <SkeletonListRow delay={400} />
          <SkeletonListRow delay={500} />
          <SkeletonListRow delay={600} />
          <SkeletonListRow delay={700} />
          <SkeletonListRow delay={800} />
        </div>
        <div className="skeleton-side-stack">
          <SkeletonInspectorCard delay={400} />
          <SkeletonInspectorCard delay={600} />
        </div>
      </div>
    </div>
  );
}

/* TaskDetailSkeleton -- TaskDetail page full skeleton */
export function TaskDetailSkeleton() {
  return (
    <div className="task-detail-layout">
      <SkeletonHero delay={0} />
      <SkeletonMetricStrip delay={200} />
      <div className="skeleton-dashboard-grid">
        <div style={{ display: "grid", gap: 16 }}>
          <SkeletonPanel delay={400} />
          <SkeletonPanel delay={600} />
        </div>
        <div className="skeleton-side-stack">
          <SkeletonInspectorCard delay={400} />
        </div>
      </div>
    </div>
  );
}

/* TimelineSkeleton -- EventTimeline page full skeleton */
export function TimelineSkeleton() {
  return (
    <div className="timeline-layout">
      <SkeletonHero delay={0} />
      <SkeletonMetricStrip delay={200} />
      <SkeletonPanel delay={400} />
    </div>
  );
}

/* TaskBuilderSkeleton -- TaskBuilder page full skeleton */
export function TaskBuilderSkeleton() {
  return (
    <div className="task-builder-layout">
      <SkeletonHero delay={0} />
      <SkeletonPanel delay={200} />
    </div>
  );
}
