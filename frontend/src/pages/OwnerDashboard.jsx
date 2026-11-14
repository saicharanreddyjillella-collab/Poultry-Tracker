import { useState, useEffect } from 'react';
import { reportAPI } from '../api/client';

const ALERT_ICON = { danger: '🔴', warning: '🟠', info: '🔵' };
const RATING_CLASS = { Excellent: 'text-ok', Good: 'text-ok', Fair: '', Poor: 'text-danger' };

export default function OwnerDashboard() {
  const [data, setData] = useState(null);
  const [period, setPeriod] = useState(90);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = (p) => {
    setLoading(true); setError('');
    reportAPI.ownerDashboard(p)
      .then(r => setData(r.data))
      .catch(() => setError('Could not load the dashboard.'))
      .finally(() => setLoading(false));
  };
  useEffect(() => { load(period); /* eslint-disable-next-line */ }, [period]);

  const fmt = (n) => (n == null ? '—' : Number(n).toLocaleString('en-IN'));

  return (
    <div className="page">
      <div className="page-header">
        <h1>Owner Dashboard</h1>
        <div className="form-group" style={{ margin: 0 }}>
          <label>Period</label>
          <select value={period} onChange={e => setPeriod(parseInt(e.target.value))}>
            {[30, 90, 180, 365].map(d => <option key={d} value={d}>Last {d} days</option>)}
          </select>
        </div>
      </div>

      {error && <div className="alert-banner alert-banner-danger">{error}</div>}
      {loading ? <p className="muted">Loading…</p> : data && (
        <>
          <div className="stats-grid stats-grid-wide">
            <div className="stat-card"><span className="stat-label">Active Flocks</span><span className="stat-value">{data.overview.active_flocks}</span></div>
            <div className="stat-card stat-info"><span className="stat-label">Live Birds</span><span className="stat-value">{fmt(data.overview.total_live_birds)}</span></div>
            <div className="stat-card"><span className="stat-label">Closed ({data.period_days}d)</span><span className="stat-value">{data.overview.closed_in_period}</span></div>
            <div className="stat-card"><span className="stat-label">Farms</span><span className="stat-value">{data.overview.total_farms}</span></div>
          </div>

          {/* Alerts */}
          <h2 style={{ marginTop: '1.5rem' }}>Alerts {data.alerts.length > 0 && <span className="badge">{data.alerts.length}</span>}</h2>
          {data.alerts.length === 0 ? <p className="muted">No active alerts. 🎉</p> : (
            <div className="alert-list">
              {data.alerts.map((a, i) => (
                <div key={i} className={`alert-row alert-row-${a.type}`}>
                  <span>{ALERT_ICON[a.type] || '•'}</span>
                  <span><strong>{a.farm_code}</strong> {a.farm_name}</span>
                  <span className="alert-msg">{a.message}</span>
                </div>
              ))}
            </div>
          )}

          {/* Active cycle */}
          <h2 style={{ marginTop: '1.5rem' }}>Active Cycle</h2>
          {data.active_cycle.length === 0 ? <p className="muted">No active flocks.</p> : (
            <div className="table-wrapper">
              <table>
                <thead><tr><th>Farm</th><th>Region</th><th>Age</th><th>Live</th><th>Phase</th><th>Mort%</th><th>Rating</th></tr></thead>
                <tbody>
                  {data.active_cycle.map(f => (
                    <tr key={f.flock_id}>
                      <td>{f.farm_code} — {f.farm_name}</td><td>{f.region || '—'}</td>
                      <td>{f.age_days}d</td><td>{fmt(f.live_birds)}</td><td>{f.feed_phase || '—'}</td>
                      <td className={f.mortality_pct > 5 ? 'text-danger' : ''}>{f.mortality_pct}%</td>
                      <td className={RATING_CLASS[f.rating] || ''}>{f.rating} ({f.score})</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Leaderboard */}
          {data.leaderboard.top.length > 0 && (
            <>
              <h2 style={{ marginTop: '1.5rem' }}>Performance Leaderboard (by EPEF)</h2>
              <div className="leaderboard-grid">
                <div>
                  <h4>Top performers</h4>
                  <div className="table-wrapper"><table>
                    <thead><tr><th>Farm</th><th>EPEF</th><th>FCR</th><th>Grade</th></tr></thead>
                    <tbody>{data.leaderboard.top.map(f => (
                      <tr key={f.flock_id}><td>{f.farm_code}</td><td className="text-ok">{f.epef}</td><td>{f.fcr}</td><td>{f.grade || '—'}</td></tr>
                    ))}</tbody>
                  </table></div>
                </div>
                {data.leaderboard.bottom.length > 0 && (
                  <div>
                    <h4>Needs attention</h4>
                    <div className="table-wrapper"><table>
                      <thead><tr><th>Farm</th><th>EPEF</th><th>FCR</th><th>Grade</th></tr></thead>
                      <tbody>{data.leaderboard.bottom.map(f => (
                        <tr key={f.flock_id}><td>{f.farm_code}</td><td className="text-danger">{f.epef}</td><td>{f.fcr}</td><td>{f.grade || '—'}</td></tr>
                      ))}</tbody>
                    </table></div>
                  </div>
                )}
              </div>
            </>
          )}

          {/* Region summary */}
          {data.region_summary.length > 0 && (
            <>
              <h2 style={{ marginTop: '1.5rem' }}>Region Summary ({data.period_days}d)</h2>
              <div className="table-wrapper">
                <table>
                  <thead><tr><th>Region</th><th>Flocks</th><th>Placed</th><th>Sold</th><th>Avg FCR</th><th>Avg EPEF</th><th>Avg Mort%</th><th>Paid</th></tr></thead>
                  <tbody>
                    {data.region_summary.map(r => (
                      <tr key={r.region}>
                        <td>{r.region}</td><td>{r.flocks}</td><td>{fmt(r.birds_placed)}</td><td>{fmt(r.birds_sold)}</td>
                        <td>{r.avg_fcr ?? '—'}</td><td>{r.avg_epef ?? '—'}</td><td>{r.avg_mortality_pct}%</td>
                        <td>₹{fmt(r.settlement_paid)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
