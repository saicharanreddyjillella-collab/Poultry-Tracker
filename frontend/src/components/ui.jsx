// Small building blocks of the Style B design system.

/** Tiny line chart of a series (no axes). Decorative: the tile's text carries the meaning. */
export function Sparkline({ values = [], color = 'var(--primary)', width = 96, height = 30 }) {
  const pts = values.map(Number).filter(v => Number.isFinite(v));
  if (pts.length < 2 || pts.every(v => v === 0)) return null;     // nothing to show
  const max = Math.max(...pts), min = Math.min(...pts);
  const span = max - min || 1;
  const step = width / (pts.length - 1);
  const d = pts.map((v, i) => `${i ? 'L' : 'M'}${(i * step).toFixed(1)} ${(height - 3 - ((v - min) / span) * (height - 6)).toFixed(1)}`).join(' ');
  return (
    <svg className="sparkline" width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      <path d={d} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

/** Key figure: label, big number, optional unit, note and trend line. tone: ok | warn | danger */
export function StatTile({ label, value, unit, note, tone, trend, trendColor, children }) {
  return (
    <div className="stat-card tile">
      <span className="stat-label">{label}</span>
      <div className="tile-row">
        <span className="stat-value">{value}{unit && <span className="tile-unit"> {unit}</span>}</span>
        {trend && <Sparkline values={trend} color={trendColor} />}
      </div>
      {note && <span className={`stat-sub ${tone ? `tone-${tone}` : ''}`}>{note}</span>}
      {children}
    </div>
  );
}

/** Titled box. Without a title, pass `label` so the box still has an accessible name. */
export function Panel({ title, label, actions, children, className = '', id }) {
  const headingId = title ? (id || `p-${String(title).toLowerCase().replace(/[^a-z0-9]+/g, '-')}`) : undefined;
  return (
    <section className={`panel ${className}`} aria-labelledby={headingId} aria-label={title ? undefined : label}>
      {(title || actions) && (
        <div className="panel-head">
          {title && <h2 id={headingId}>{title}</h2>}
          {actions && <div className="panel-actions">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

/** Status chip. tone: ok | warn | danger | info | (none = grey) */
export function Chip({ tone, children }) {
  return <span className={`chip ${tone ? `chip-${tone}` : ''}`}>{children}</span>;
}

/** Thin progress bar with its value, e.g. weight as % of standard. */
export function Meter({ pct, label }) {
  if (pct == null) return <span className="muted">—</span>;
  const tone = pct >= 98 ? 'ok' : pct >= 92 ? 'warn' : 'danger';
  return (
    <span className="meter">
      <span className="meter-track" aria-hidden="true"><span className={`meter-fill meter-${tone}`} style={{ width: `${Math.min(pct, 110) / 1.1}%` }} /></span>
      <span className="num">{label ?? `${pct}%`}</span>
    </span>
  );
}
