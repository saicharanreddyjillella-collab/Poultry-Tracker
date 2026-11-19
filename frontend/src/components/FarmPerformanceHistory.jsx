import { useState, useEffect } from 'react';
import { farmAPI } from '../api/client';
import { useAuth } from '../context/AuthContext';

const TREND = {
  improving: { icon: '▲', cls: 'text-ok', label: 'improving' },
  declining: { icon: '▼', cls: 'text-danger', label: 'declining' },
  flat: { icon: '▬', cls: '', label: 'flat' },
};

export default function FarmPerformanceHistory({ farmId }) {
  const { isAdmin } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    farmAPI.performanceHistory(farmId)
      .then(r => setData(r.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [farmId]);

  if (loading) return null;
  if (!data || data.cycle_count === 0) {
    return (
      <div className="documents-section">
        <h3>Performance History</h3>
        <p className="muted">No closed cycles yet.</p>
      </div>
    );
  }

  const fmt = (n) => (n == null ? '—' : Number(n).toLocaleString('en-IN'));
  const t = (key) => data.trends[key] ? TREND[data.trends[key]] : null;
  const TrendBadge = ({ k }) => {
    const tr = t(k);
    if (!tr) return null;
    return <span className={`trend-badge ${tr.cls}`} title={tr.label}>{tr.icon}</span>;
  };

  return (
    <div className="documents-section">
      <h3>Performance History <span className="muted">({data.cycle_count} cycles)</span></h3>

      {/* Averages with trend direction */}
      <div className="stats-grid stats-grid-wide" style={{ marginBottom: '1rem' }}>
        <div className="stat-card"><span className="stat-label">Avg FCR <TrendBadge k="fcr" /></span><span className="stat-value">{fmt(data.averages.fcr)}</span></div>
        <div className="stat-card stat-info"><span className="stat-label">Avg EPEF <TrendBadge k="epef" /></span><span className="stat-value">{fmt(data.averages.epef)}</span></div>
        <div className="stat-card"><span className="stat-label">Avg Livability <TrendBadge k="livability_pct" /></span><span className="stat-value">{fmt(data.averages.livability_pct)}%</span></div>
        {isAdmin && <div className="stat-card"><span className="stat-label">Avg Cost/kg <TrendBadge k="cost_per_kg" /></span><span className="stat-value">₹{fmt(data.averages.cost_per_kg)}</span></div>}
      </div>

      <div className="table-wrapper">
        <table>
          <thead>
            <tr><th>Placed</th><th>Chicks</th><th>FCR</th><th>EPEF</th><th>Livability</th><th>Mort%</th>{isAdmin && <th>Cost/kg</th>}<th>Grade</th><th>Paid</th></tr>
          </thead>
          <tbody>
            {data.cycles.map(c => (
              <tr key={c.flock_id}>
                <td>{c.placement_date}</td>
                <td>{fmt(c.chicks_placed)}</td>
                <td>{c.fcr ?? '—'}</td>
                <td>{c.epef ?? '—'}</td>
                <td>{fmt(c.livability_pct)}%</td>
                <td className={c.mortality_pct > 5 ? 'text-danger' : ''}>{c.mortality_pct}%</td>
                {isAdmin && <td>{c.cost_per_kg != null ? `₹${fmt(c.cost_per_kg)}` : '—'}</td>}
                <td>{c.grade || '—'}</td>
                <td>{c.settlement_paid != null ? `₹${fmt(c.settlement_paid)}` : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
