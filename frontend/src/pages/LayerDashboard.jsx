import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { layerAPI } from '../api/client';

export default function LayerDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    layerAPI.dashboard().then(r => { setData(r.data); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  const fmt = (n) => n != null ? Number(n).toLocaleString('en-IN', { maximumFractionDigits: 2 }) : '0';

  if (loading) return <div className="loading">Loading…</div>;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Layer Farm</h1>
          <p className="farm-meta">Per-flock cost &amp; egg production</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <Link to="/layer/new" className="btn btn-primary">+ New Entry</Link>
          <Link to="/layer/flocks" className="btn btn-secondary">Flocks</Link>
          <Link to="/layer/feed" className="btn btn-secondary">Feed Mill</Link>
          <Link to="/layer/masters" className="btn btn-secondary">Masters</Link>
        </div>
      </div>

      <div className="stats-grid stats-grid-wide">
        <div className="stat-card"><span className="stat-label">Total Cost (all flocks)</span><span className="stat-value">₹{fmt(data?.total_cost)}</span></div>
        <div className="stat-card"><span className="stat-label">Total Egg Revenue</span><span className="stat-value text-ok">₹{fmt(data?.total_revenue)}</span></div>
        <div className="stat-card"><span className="stat-label">Net Position</span><span className={`stat-value ${data?.net_position >= 0 ? 'text-ok' : 'text-danger'}`}>₹{fmt(data?.net_position)}</span></div>
        <div className="stat-card"><span className="stat-label">Active Birds</span><span className="stat-value">{fmt(data?.active_birds)}</span></div>
      </div>

      <h3 style={{ marginTop: '1.5rem' }}>Flocks</h3>
      {data?.flocks?.length ? (
        <div className="table-wrapper">
          <table className="report-table">
            <thead><tr><th>Flock</th><th>Farm</th><th>Status</th><th>Age</th><th>Live birds</th><th>Cost</th><th>Egg Revenue</th><th>Net</th></tr></thead>
            <tbody>
              {data.flocks.map(f => (
                <tr key={f.flock_id}>
                  <td><Link to={`/layer/flocks/${f.flock_id}`}>{f.flock_name}</Link></td>
                  <td>{f.farm_name}</td>
                  <td><span className={`wa-badge ${f.status === 'ACTIVE' ? 'wa-sent' : 'wa-disabled'}`}>{f.status}</span></td>
                  <td>{f.age_days}d</td>
                  <td>{fmt(f.live_birds)}</td>
                  <td>₹{fmt(f.total_cost)}</td>
                  <td className="text-ok">₹{fmt(f.egg_revenue)}</td>
                  <td className={f.net_position >= 0 ? 'text-ok' : 'text-danger'}>₹{fmt(f.net_position)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <p className="farm-meta">No flocks yet. <Link to="/layer/flocks">Add a flock →</Link></p>}
    </div>
  );
}
