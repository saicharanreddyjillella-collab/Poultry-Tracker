import { useState, useEffect } from 'react';
import { reportAPI } from '../api/client';

export default function FeedForecast() {
  const [data, setData] = useState(null);
  const [weeks, setWeeks] = useState(4);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = (w) => {
    setLoading(true); setError('');
    reportAPI.feedForecast(w)
      .then(r => setData(r.data))
      .catch(() => setError('Could not load the feed forecast.'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(weeks); /* eslint-disable-next-line */ }, [weeks]);

  const fmt = (n) => Number(n).toLocaleString('en-IN');

  return (
    <div className="page">
      <div className="page-header">
        <h1>Feed Requirement Forecast</h1>
        <div className="form-group" style={{ margin: 0 }}>
          <label>Horizon</label>
          <select value={weeks} onChange={e => setWeeks(parseInt(e.target.value))}>
            {[2, 4, 6, 8, 12].map(w => <option key={w} value={w}>{w} weeks</option>)}
          </select>
        </div>
      </div>
      <p className="muted">Projected feed demand across active flocks, by week and phase. Based on standard intake and mortality curves — a planning estimate, not a commitment.</p>

      {error && <div className="alert-banner alert-banner-danger">{error}</div>}
      {loading ? <p className="muted">Loading…</p> : data && (
        <>
          <div className="stats-grid stats-grid-wide" style={{ marginBottom: '1rem' }}>
            <div className="stat-card"><span className="stat-label">Active Flocks</span><span className="stat-value">{data.active_flocks}</span></div>
            <div className="stat-card stat-info"><span className="stat-label">Total Feed ({data.weeks}w)</span><span className="stat-value">{fmt(data.totals.total_bags)} bags<br/><small>{fmt(data.totals.total_kg)} kg</small></span></div>
            <div className="stat-card"><span className="stat-label">BPSC / BSC / BFP (bags)</span><span className="stat-value" style={{ fontSize: '1rem' }}>{fmt(data.totals.bpsc_bags)} / {fmt(data.totals.bsc_bags)} / {fmt(data.totals.bfp_bags)}</span></div>
          </div>

          <h2>By week</h2>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr><th>Week</th><th>Dates</th><th>BPSC</th><th>BSC</th><th>BFP</th><th>Total (bags)</th></tr>
              </thead>
              <tbody>
                {data.weekly.map(w => (
                  <tr key={w.week}>
                    <td>W{w.week}</td>
                    <td>{w.start} → {w.end}</td>
                    <td>{fmt(w.bpsc_bags)}</td>
                    <td>{fmt(w.bsc_bags)}</td>
                    <td>{fmt(w.bfp_bags)}</td>
                    <td><strong>{fmt(w.total_bags)}</strong></td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="bill-t-total">
                  <td colSpan={2}>Total</td>
                  <td>{fmt(data.totals.bpsc_bags)}</td>
                  <td>{fmt(data.totals.bsc_bags)}</td>
                  <td>{fmt(data.totals.bfp_bags)}</td>
                  <td><strong>{fmt(data.totals.total_bags)}</strong></td>
                </tr>
              </tfoot>
            </table>
          </div>

          {data.per_flock.length > 0 && (
            <>
              <h2 style={{ marginTop: '1.5rem' }}>By flock</h2>
              <div className="table-wrapper">
                <table>
                  <thead>
                    <tr><th>Farm</th><th>Live Birds</th><th>Forecast (bags)</th><th>kg</th></tr>
                  </thead>
                  <tbody>
                    {data.per_flock.map(f => (
                      <tr key={f.flock_id}>
                        <td>{f.farm_code} — {f.farm_name}</td>
                        <td>{fmt(f.live_birds)}</td>
                        <td>{fmt(f.forecast_bags)}</td>
                        <td>{fmt(f.forecast_kg)}</td>
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
