import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { layerAPI, getErrorMessage } from '../api/client';

export default function LayerFlockDetail() {
  const { id } = useParams();
  const [summary, setSummary] = useState(null);
  const [costs, setCosts] = useState([]);
  const [entries, setEntries] = useState([]);
  const [showDaily, setShowDaily] = useState(false);
  const [daily, setDaily] = useState({ date: new Date().toISOString().slice(0, 10), eggs: '', broken: '', feed_kg: '', mortality: '', culls: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const [prod, setProd] = useState(null);
  const load = () => {
    Promise.all([layerAPI.flockSummary(id), layerAPI.flockCosts(id), layerAPI.dailyEntries({ flock: id }), layerAPI.flockProduction(id)])
      .then(([s, c, e, p]) => { setSummary(s.data); setCosts(c.data); setEntries(e.data); setProd(p.data); setLoading(false); })
      .catch(() => setLoading(false));
  };
  useEffect(load, [id]);

  const fmt = (n) => n != null ? Number(n).toLocaleString('en-IN', { maximumFractionDigits: 2 }) : '0';

  const submitDaily = async (e) => {
    e.preventDefault(); setError('');
    try {
      await layerAPI.createDailyEntry({
        flock: id, date: daily.date,
        eggs: parseInt(daily.eggs) || 0, broken: parseInt(daily.broken) || 0,
        feed_kg: parseFloat(daily.feed_kg) || 0,
        mortality: parseInt(daily.mortality) || 0, culls: parseInt(daily.culls) || 0,
      });
      setShowDaily(false);
      setDaily({ date: new Date().toISOString().slice(0, 10), eggs: '', broken: '', feed_kg: '', mortality: '', culls: '' });
      load();
    } catch (err) { setError(getErrorMessage(err)); }
  };

  if (loading) return <div className="loading">Loading…</div>;
  if (!summary) return <div className="empty-state"><p>Flock not found.</p></div>;

  const s = summary;
  const profit = s.net_position >= 0;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <button className="back-link" onClick={() => navigate('/layer/flocks')}>&larr; Flocks</button>
          <h1>{s.flock_name}</h1>
          <p className="farm-meta">{s.farm_name} · Placed {s.placement_date} · Day {s.age_days} · {fmt(s.bird_count)} birds</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowDaily(!showDaily)}>+ Daily Entry</button>
      </div>

      {error && <div className="error-msg">{error}</div>}

      {/* Headline: cost vs output */}
      <div className="stats-grid stats-grid-wide">
        <div className="stat-card"><span className="stat-label">Total Cost</span><span className="stat-value">₹{fmt(s.total_cost)}</span></div>
        <div className="stat-card"><span className="stat-label">Egg Revenue</span><span className="stat-value text-ok">₹{fmt(s.egg_revenue)}</span></div>
        <div className="stat-card"><span className="stat-label">Net Position</span><span className={`stat-value ${profit ? 'text-ok' : 'text-danger'}`}>₹{fmt(s.net_position)}</span></div>
        <div className="stat-card"><span className="stat-label">Live Birds</span><span className="stat-value">{fmt(s.live_birds)}</span></div>
      </div>
      <div className="stats-grid" style={{ marginTop: '0.75rem' }}>
        <div className="stat-card"><span className="stat-label">Total Eggs</span><span className="stat-value">{fmt(s.total_eggs)}</span></div>
        <div className="stat-card"><span className="stat-label">Eggs Sold</span><span className="stat-value">{fmt(s.eggs_sold)}</span></div>
        <div className="stat-card"><span className="stat-label">Egg Stock</span><span className="stat-value">{fmt(s.egg_stock)}</span></div>
        <div className="stat-card"><span className="stat-label">Cost / Egg</span><span className="stat-value">{s.cost_per_egg != null ? `₹${fmt(s.cost_per_egg)}` : '—'}</span></div>
      </div>

      {showDaily && (
        <form onSubmit={submitDaily} className="form-card" style={{ maxWidth: 560, marginTop: '1.25rem' }}>
          <h3>Daily Entry</h3>
          <div className="form-group"><label>Date *</label><input type="date" value={daily.date} max={new Date().toISOString().slice(0, 10)} onChange={e => setDaily({ ...daily, date: e.target.value })} required /></div>
          <div className="form-row">
            <div className="form-group"><label>Eggs laid</label><input type="text" inputMode="numeric" value={daily.eggs} onChange={e => setDaily({ ...daily, eggs: e.target.value })} /></div>
            <div className="form-group"><label>Broken</label><input type="text" inputMode="numeric" value={daily.broken} onChange={e => setDaily({ ...daily, broken: e.target.value })} /></div>
            <div className="form-group"><label>Feed (kg)</label><input type="text" inputMode="decimal" value={daily.feed_kg} onChange={e => setDaily({ ...daily, feed_kg: e.target.value })} /></div>
          </div>
          <div className="form-row">
            <div className="form-group"><label>Mortality</label><input type="text" inputMode="numeric" value={daily.mortality} onChange={e => setDaily({ ...daily, mortality: e.target.value })} /></div>
            <div className="form-group"><label>Culls</label><input type="text" inputMode="numeric" value={daily.culls} onChange={e => setDaily({ ...daily, culls: e.target.value })} /></div>
          </div>
          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={() => setShowDaily(false)}>Cancel</button>
            <button type="submit" className="btn btn-primary">Save Entry</button>
          </div>
        </form>
      )}

      {/* Cost breakdown */}
      <h3 style={{ marginTop: '1.5rem' }}>Cost Breakdown</h3>
      {s.cost_lines?.length ? (
        <div className="table-wrapper" style={{ maxWidth: 420 }}>
          <table className="report-table">
            <thead><tr><th>Category</th><th>Amount</th></tr></thead>
            <tbody>
              {s.cost_lines.map((l, i) => <tr key={i}><td>{l.category}</td><td>₹{fmt(l.amount)}</td></tr>)}
              <tr className="bill-t-total"><td>Total</td><td>₹{fmt(s.total_cost)}</td></tr>
            </tbody>
          </table>
        </div>
      ) : <p className="farm-meta">No costs charged yet.</p>}

      {/* Production analytics */}
      <h3 style={{ marginTop: '1.5rem' }}>Production</h3>
      {prod && prod.rows.length ? (
        <>
          <div className="stats-grid" style={{ marginBottom: '0.75rem' }}>
            <div className="stat-card"><span className="stat-label">Avg Laying %</span><span className="stat-value">{prod.avg_laying_pct}%</span></div>
            <div className="stat-card"><span className="stat-label">Peak Laying %</span><span className="stat-value">{prod.peak_laying_pct}%</span></div>
            <div className="stat-card"><span className="stat-label">Feed / Egg</span><span className="stat-value">{prod.feed_per_egg_g != null ? `${prod.feed_per_egg_g} g` : '—'}</span></div>
            <div className="stat-card"><span className="stat-label">Total Feed</span><span className="stat-value">{fmt(prod.total_feed_kg)} kg</span></div>
          </div>
          <div className="table-wrapper">
            <table className="report-table">
              <thead><tr><th>Date</th><th>Day</th><th>Eggs</th><th>Laying %</th><th>Feed/egg</th><th>Broken</th><th>Feed kg</th><th>Mort.</th><th>Culls</th><th>Live</th><th>Cum. eggs</th></tr></thead>
              <tbody>
                {prod.rows.slice().reverse().map((r, i) => (
                  <tr key={i}>
                    <td>{r.date}</td><td>{r.day}</td><td>{r.eggs}</td>
                    <td>{r.laying_pct}%</td>
                    <td>{r.feed_per_egg_g != null ? `${r.feed_per_egg_g} g` : '—'}</td>
                    <td>{r.broken}</td><td>{fmt(r.feed_kg)}</td><td>{r.mortality}</td><td>{r.culls}</td>
                    <td>{r.live_birds}</td><td>{r.cumulative_eggs}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : <p className="farm-meta">No daily entries yet. Add one to track laying % and feed efficiency.</p>}
    </div>
  );
}
