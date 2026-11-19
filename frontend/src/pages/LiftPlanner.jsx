import { Fragment, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { insightsAPI, marketRateAPI, getErrorMessage } from '../api/client';
import { todayISO } from '../utils/dates';
import FeatureOff from '../components/FeatureOff';
import { useFeatures } from '../utils/features';
import '../styles/insights.css';

const rs = (n) => `₹${Math.round(Number(n || 0)).toLocaleString('en-IN')}`;
const signed = (n) => (n > 0 ? `+${rs(n)}` : n < 0 ? `−${rs(-n)}` : '₹0');

function MarketRates({ onSaved, highlight }) {
  const [rows, setRows] = useState([]);
  const [form, setForm] = useState({ date: todayISO(), rate_per_kg: '', notes: '' });
  const [msg, setMsg] = useState('');
  const load = () => marketRateAPI.list().then(r => setRows(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);
  const save = async (e) => {
    e.preventDefault();
    setMsg('');
    try {
      await marketRateAPI.save(form);
      setMsg(`Saved ₹${form.rate_per_kg}/kg for ${form.date}.`);
      setForm({ ...form, rate_per_kg: '', notes: '' });
      load(); onSaved();
    } catch (err) { setMsg(getErrorMessage(err)); }
  };
  return (
    <section className={highlight ? 'form-card' : ''} style={{ marginTop: highlight ? '0.5rem' : '2rem' }}>
      <h2>Market rate</h2>
      <p className="muted">The day's live-bird rate (₹/kg) — association rate or a trader's quote. Saving a date that
        already has a rate corrects it.</p>
      {msg && <div className="alert-banner">{msg}</div>}
      <form className="loc-row" onSubmit={save}>
        <div className="form-group"><label>Date</label>
          <input type="date" value={form.date} max={todayISO()} required onChange={e => setForm({ ...form, date: e.target.value })} /></div>
        <div className="form-group"><label>Rate ₹/kg</label>
          <input value={form.rate_per_kg} inputMode="decimal" required placeholder="e.g. 108" onChange={e => setForm({ ...form, rate_per_kg: e.target.value })} /></div>
        <div className="form-group"><label>Source (optional)</label>
          <input value={form.notes} placeholder="e.g. Association rate" onChange={e => setForm({ ...form, notes: e.target.value })} /></div>
        <button type="submit" className="btn btn-primary">Save Rate</button>
      </form>
      {rows.length > 0 && (
        <p className="muted" style={{ marginTop: '0.5rem' }}>
          Recent: {rows.slice(0, 10).map(r => `${r.date.slice(5)} ₹${Number(r.rate_per_kg)}`).join(' · ')}
        </p>
      )}
    </section>
  );
}

/** Admin: for each flock old enough to lift — sell now, or hold and gain? */
export default function LiftPlanner() {
  const { loaded, isOn } = useFeatures();
  if (loaded && !isOn('lift_planner')) return <FeatureOff name="Best Day to Lift" />;
  return <LiftPlannerPage />;
}

function LiftPlannerPage() {
  const [trend, setTrend] = useState(true);
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [open, setOpen] = useState(null);
  const load = () => insightsAPI.liftPlanner(trend).then(r => { setData(r.data); setError(''); })
    .catch(err => setError(getErrorMessage(err)));
  useEffect(() => { load(); }, [trend]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="page">
      <div className="page-header">
        <h1>Best Day to Lift</h1>
        <Link to="/insights" className="btn btn-secondary">← Insights</Link>
      </div>
      <p className="muted">For each flock aged {data?.min_age ?? 28}+ days: the value of lifting today versus each of the
        next {data?.horizon_days ?? 10} days — birds left × projected weight × (market price − grower charge per kg),
        minus the feed they eat meanwhile. Weight follows the flock's own growth against the Cobb standard; deaths
        follow its last 7 days.</p>
      {error && <div className="alert-banner alert-banner-danger">{error}</div>}
      {!data && !error && <p className="muted">Loading…</p>}
      {data?.needs_rate && (
        <>
          <div className="alert-banner alert-banner-warning">{data.error}</div>
          <MarketRates onSaved={load} highlight />
        </>
      )}
      {data && !data.needs_rate && (
        <>
          <div className="stats-grid stats-grid-wide" style={{ marginBottom: '1rem' }}>
            <div className="stat-card stat-info"><span className="stat-label">Price used</span>
              <span className="stat-value">₹{data.price.per_kg}/kg</span><small className="muted">{data.price.source}</small></div>
            <div className="stat-card"><span className="stat-label">Lift now</span><span className="stat-value">{data.summary.lift_now}</span></div>
            <div className="stat-card"><span className="stat-label">Better to hold</span><span className="stat-value">{data.summary.hold}</span></div>
            <div className="stat-card"><span className="stat-label">Extra value by waiting</span><span className="stat-value">{rs(data.summary.total_gain)}</span></div>
          </div>
          <div className="loc-row" style={{ borderBottom: 0 }}>
            <label style={{ display: 'flex', gap: '0.4rem', alignItems: 'center', margin: 0 }}>
              <input type="checkbox" checked={trend} onChange={e => setTrend(e.target.checked)} />
              Follow the recent price trend
            </label>
            <small className="muted">
              Recent change {data.price.recent_trend_per_day >= 0 ? '+' : ''}₹{data.price.recent_trend_per_day}/kg a day;
              assumed {data.price.assumed_change_per_day >= 0 ? '+' : ''}₹{data.price.assumed_change_per_day}/day
              (half of it, capped). Feed ₹{data.costs.feed_per_kg}/kg · grower ₹{data.costs.grower_charge_per_kg}/kg.
            </small>
          </div>

          {data.flocks.length === 0 ? <div className="alert-banner">No active flock is {data.min_age}+ days old yet.</div> : (
            <div className="table-wrapper">
              <table>
                <thead><tr><th>Farm</th><th>Age</th><th>Live birds</th><th>Weight now</th><th>Best day</th><th>Gain vs today</th><th>Advice</th></tr></thead>
                <tbody>
                  {data.flocks.map(f => (
                    <Fragment key={f.flock_id}>
                      <tr className="lift-row" style={{ cursor: 'pointer' }} onClick={() => setOpen(open === f.flock_id ? null : f.flock_id)}>
                        <td><Link to={`/flocks/${f.flock_id}`} onClick={e => e.stopPropagation()}>{f.farm_name}</Link><br />
                          <small className="muted">{open === f.flock_id ? '▾ hide days' : '▸ day by day'}</small></td>
                        <td>{f.age_today}d</td>
                        <td>{f.live_birds.toLocaleString('en-IN')}</td>
                        <td>{f.weight_today_kg} kg<br /><small className="muted">{f.weight_source}</small></td>
                        <td>{f.best_in_days === 0 ? <span className="sev sev-high">Now</span> : <>{f.best_date}<br /><small className="muted">day {f.best_age} · in {f.best_in_days} d</small></>}</td>
                        <td>{signed(f.gain_vs_today)}</td>
                        <td style={{ maxWidth: 280 }}>{f.advice}</td>
                      </tr>
                      {open === f.flock_id && (
                        <tr><td colSpan={7} style={{ background: 'var(--bg)' }}>
                          <table>
                            <thead><tr><th>Date</th><th>Age</th><th>Birds</th><th>Weight</th><th>Price</th><th>Feed from today</th><th>vs today</th></tr></thead>
                            <tbody>
                              {f.days.map(d => (
                                <tr key={d.date} style={d.date === f.best_date ? { fontWeight: 700 } : undefined}>
                                  <td>{d.date}</td><td>{d.age}</td><td>{d.birds.toLocaleString('en-IN')}</td>
                                  <td>{d.weight_kg} kg</td><td>₹{d.price}</td><td>{rs(d.feed_cost)}</td><td>{signed(d.gain_vs_today)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </td></tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="muted" style={{ marginTop: '0.75rem' }}>An estimate to support the decision — catching crews,
            trader demand and disease risk still matter.</p>
          <MarketRates onSaved={load} />
        </>
      )}
    </div>
  );
}
