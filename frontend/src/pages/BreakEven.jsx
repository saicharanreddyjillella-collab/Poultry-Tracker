import { useState, useEffect } from 'react';
import { reportAPI } from '../api/client';

export default function BreakEven() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    reportAPI.breakEven()
      .then(r => setData(r.data))
      .catch(() => setError('Could not load the break-even projection.'))
      .finally(() => setLoading(false));
  }, []);

  const fmt = (n) => (n == null ? '—' : Number(n).toLocaleString('en-IN'));

  return (
    <div className="page">
      <div className="page-header"><h1>Break-even Projection</h1></div>
      <p className="muted">
        Projected production cost and break-even selling price for each live flock, run to day {data?.finish_age ?? 42} at
        current feed rate (₹{data ? fmt(data.feed_rate_per_kg) : '—'}/kg). A guide to what a new placement would break even at.
      </p>

      {error && <div className="alert-banner alert-banner-danger">{error}</div>}
      {loading ? <p className="muted">Loading…</p> : data && (
        <>
          <div className="stats-grid stats-grid-wide">
            <div className="stat-card stat-info"><span className="stat-label">Blended Break-even (all live)</span><span className="stat-value">₹{fmt(data.overall.blended_break_even_per_kg)}<small>/kg</small></span></div>
            <div className="stat-card"><span className="stat-label">Avg of Flocks</span><span className="stat-value">₹{fmt(data.avg_break_even_per_kg)}<small>/kg</small></span></div>
            <div className="stat-card"><span className="stat-label">Active Flocks</span><span className="stat-value">{data.active_flocks}</span></div>
            <div className="stat-card"><span className="stat-label">Feed Rate</span><span className="stat-value">₹{fmt(data.rates.feed_cost_per_kg)}<small>/kg</small></span></div>
          </div>
          <div className="stats-grid stats-grid-wide" style={{ marginTop: '0.75rem' }}>
            <div className="stat-card"><span className="stat-label">Total Projected Cost</span><span className="stat-value">₹{fmt(data.overall.total_cost)}</span></div>
            <div className="stat-card"><span className="stat-label">Total Projected Weight</span><span className="stat-value">{fmt(data.overall.total_projected_weight_kg)}<small> kg</small></span></div>
            <div className="stat-card"><span className="stat-label">Total Feed to Finish</span><span className="stat-value">{fmt(data.overall.total_feed_to_finish_bags)}<small> bags</small></span></div>
            <div className="stat-card"><span className="stat-label">Projected Birds</span><span className="stat-value">{fmt(data.overall.total_projected_birds)}</span></div>
          </div>

          {data.flocks.length === 0 ? <p className="muted">No active flocks to project.</p> : (
            <div className="table-wrapper">
              <table>
                <thead>
                  <tr>
                    <th>Farm</th><th>Age</th><th>Chicks</th><th>Proj. Live</th>
                    <th>Feed (bags)</th><th>Proj. Wt (kg)</th><th>Total Cost</th>
                    <th>Cost/kg</th><th>Break-even ₹/kg</th>
                  </tr>
                </thead>
                <tbody>
                  {data.flocks.map(f => (
                    <tr key={f.flock_id}>
                      <td>{f.farm_code} — {f.farm_name}</td>
                      <td>{f.age_days}d</td>
                      <td>{fmt(f.chicks_placed)}</td>
                      <td>{fmt(f.projected_live_at_finish)}</td>
                      <td>{fmt(f.feed_consumed_bags)} → {fmt(f.feed_to_finish_bags)}</td>
                      <td>{fmt(f.projected_weight_kg)}</td>
                      <td>₹{fmt(f.total_cost)}</td>
                      <td>₹{fmt(f.cost_per_kg)}</td>
                      <td><strong>₹{fmt(f.break_even_price_per_kg)}</strong></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
