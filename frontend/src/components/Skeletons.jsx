export function SkeletonLine({ width = '100%', height = '1rem' }) {
  return <div className="skeleton-line" style={{ width, height }} />;
}

export function SkeletonCard({ lines = 3 }) {
  return (
    <div className="skeleton-card">
      <SkeletonLine width="40%" height="1.2rem" />
      {Array.from({ length: lines - 1 }).map((_, i) => (
        <SkeletonLine key={i} width={`${60 + Math.random() * 30}%`} />
      ))}
    </div>
  );
}

export function SkeletonStat() {
  return (
    <div className="skeleton-stat">
      <SkeletonLine width="60%" height="0.7rem" />
      <SkeletonLine width="40%" height="1.5rem" />
    </div>
  );
}

export function DashboardSkeleton() {
  return (
    <div className="page">
      <div className="page-header">
        <div>
          <SkeletonLine width="220px" height="1.75rem" />
          <SkeletonLine width="300px" height="0.9rem" />
        </div>
      </div>
      <div className="stats-grid stats-grid-wide">
        {Array.from({ length: 4 }).map((_, i) => <SkeletonStat key={i} />)}
      </div>
      <SkeletonLine width="120px" height="1rem" />
      <div className="stats-grid" style={{ marginTop: '0.75rem' }}>
        {Array.from({ length: 4 }).map((_, i) => <SkeletonStat key={i} />)}
      </div>
      <SkeletonLine width="80px" height="1rem" />
      <div className="card-grid" style={{ marginTop: '0.75rem' }}>
        {Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)}
      </div>
    </div>
  );
}

export function FarmsListSkeleton() {
  return (
    <div className="page">
      <div className="page-header">
        <SkeletonLine width="160px" height="1.75rem" />
      </div>
      <SkeletonLine width="100%" height="2.75rem" />
      <div className="card-grid" style={{ marginTop: '1.5rem' }}>
        {Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} lines={4} />)}
      </div>
    </div>
  );
}

export function FlockDetailSkeleton() {
  return (
    <div className="page">
      <div className="page-header">
        <div>
          <SkeletonLine width="100px" height="0.8rem" />
          <SkeletonLine width="300px" height="1.75rem" />
          <SkeletonLine width="350px" height="0.9rem" />
        </div>
      </div>
      <div className="stats-grid stats-grid-wide">
        {Array.from({ length: 6 }).map((_, i) => <SkeletonStat key={i} />)}
      </div>
      <SkeletonLine width="140px" height="1rem" />
      <div className="feed-progress-grid" style={{ marginTop: '0.75rem' }}>
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="skeleton-card"><SkeletonLine width="50%" /><SkeletonLine width="100%" height="10px" /><SkeletonLine width="70%" height="0.7rem" /></div>
        ))}
      </div>
      <div className="skeleton-chart" />
      <div className="skeleton-chart" />
    </div>
  );
}

export function ReportSkeleton() {
  return (
    <div className="page">
      <div className="page-header">
        <SkeletonLine width="200px" height="1.75rem" />
      </div>
      <div className="stats-grid stats-grid-wide">
        {Array.from({ length: 8 }).map((_, i) => <SkeletonStat key={i} />)}
      </div>
      <div className="skeleton-table">
        {Array.from({ length: 5 }).map((_, i) => <SkeletonLine key={i} width="100%" height="2.5rem" />)}
      </div>
    </div>
  );
}

export function BillSkeleton() {
  return (
    <div className="page">
      <SkeletonLine width="140px" height="0.8rem" />
      <SkeletonLine width="200px" height="1.75rem" />
      <div className="skeleton-card" style={{ maxWidth: 800, marginTop: '1rem' }}>
        <SkeletonLine width="50%" height="1.5rem" />
        <SkeletonLine width="100%" />
        <SkeletonLine width="100%" height="4rem" />
        <SkeletonLine width="30%" height="1rem" />
        {Array.from({ length: 5 }).map((_, i) => <SkeletonLine key={i} width="100%" height="2rem" />)}
        <SkeletonLine width="30%" height="1rem" />
        {Array.from({ length: 3 }).map((_, i) => <SkeletonLine key={i} width="100%" height="2rem" />)}
        <SkeletonLine width="100%" height="4rem" />
      </div>
    </div>
  );
}
