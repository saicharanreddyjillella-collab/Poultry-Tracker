import { Fragment, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { insightsAPI, getErrorMessage } from '../api/client';
import FeatureOff from '../components/FeatureOff';
import { useFeatures } from '../utils/features';
import '../styles/insights.css';

const n = (v) => Number(v || 0).toLocaleString('en-IN');
const scoreClass = (s) => (s >= 67 ? 'sev-ok' : s >= 34 ? 'sev-medium' : 'sev-high');

export default function GrowerRanking() {
  const { loaded, isOn } = useFeatures();
  if (loaded && !isOn('placement_planner')) return <FeatureOff name="Who Gets the Next Chicks" />;
  return <GrowerRankingPage />;
}

/** Admin: growers ranked on settled flocks, and a plan for placing the next chicks. */
function GrowerRankingPage() {
  const [form, setForm] = useState({ chicks: '', rest_days: '14', region: '' });
  const [query, setQuery] = useState({ rest_days: 14 });
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [open, setOpen] = useState(null);

  useEffect(() => {
    insightsAPI.growerRanking(query).then(r => { setData(r.data); setError(''); })
      .catch(err => setError(getErrorMessage(err)));
  }, [query]);

  const submit = (e) => {
    e.preventDefault();
    const q = { rest_days: form.rest_days || 14 };
    if (form.chicks) q.chicks = form.chicks;
    if (form.region) q.region = form.region;
    setQuery(q);
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1>Who Gets the Next Chicks</h1>
        <Link to="/insights" className="btn btn-secondary">← Insights</Link>
      </div>
      <p className="muted">Growers ranked on their last {data?.max_cycles ?? 4} settled flocks (2 years): feed efficiency
        45%, mortality 35%, consistency 20% — each compared with your other growers, so 100 is the best. Enter the chicks
        you have to see which free farms should get them.</p>

      <form className="loc-row form-card" onSubmit={submit} style={{ marginBottom: '1rem' }}>
        <div className="form-group"><label>Chicks available</label>
          <input value={form.chicks} inputMode="numeric" placeholder="e.g. 30000" onChange={e => setForm({ ...form, chicks: e.target.value })} /></div>
        <div className="form-group"><label>Rest days after a flock</label>
          <input value={form.rest_days} inputMode="numeric" onChange={e => setForm({ ...form, rest_days: e.target.value })} /></div>
        <div className="form-group"><label>Region</label>
          <select value={form.region} onChange={e => setForm({ ...form, region: e.target.value })}>
            <option value="">All regions</option>
            {(data?.regions || []).map(r => <option key={r} value={r}>{r}</option>)}
          </select></div>
        <button type="submit" className="btn btn-primary">Plan</button>
      </form>

      {error && <div className="alert-banner alert-banner-danger">{error}</div>}
      {!data && !error && <p className="muted">Loading…</p>}
      {data && (
        <>
          {data.plan && (
            <section className="placement-plan" style={{ marginBottom: '1.5rem' }}>
              <h2>Placement plan</h2>
              {data.plan.rows.length === 0 ? (
                <div className="alert-banner alert-banner-warning">No free farm can take these chicks
                  (farms need no running flock, {data.rest_days}+ rest days, and a capacity the chicks fill within ±5%).</div>
              ) : (
                <>
                  <div className="table-wrapper">
                    <table>
                      <thead><tr><th>#</th><th>Farm</th><th>Region</th><th>Score</th><th>Capacity</th><th>Chicks</th></tr></thead>
                      <tbody>
                        {data.plan.rows.map((p, i) => (
                          <tr key={p.farm_id}>
                            <td>{i + 1}</td>
                            <td><Link to={`/farms/${p.farm_id}`}>{p.farm_name}</Link></td>
                            <td>{p.region}</td>
                            <td>{p.score == null ? <span className="muted">new</span> : p.score}</td>
                            <td>{n(p.capacity)}</td>
                            <td><strong>{n(p.chicks)}</strong></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="plan-total">Placed {n(data.plan.allocated)} chicks{data.plan.left_over ? <> · <strong>{n(data.plan.left_over)} left over</strong> (no free farm they fit)</> : ''}.</p>
                </>
              )}
            </section>
          )}

          <h2>Ranking</h2>
          {data.growers.length === 0 ? <div className="alert-banner">No settled flocks in the last 2 years yet.</div> : (
            <div className="table-wrapper">
              <table>
                <thead><tr><th>#</th><th>Farm</th><th>Score</th><th>FCR</th><th>Mortality</th><th>FCR spread</th><th>Cycles</th><th>Next chicks?</th></tr></thead>
                <tbody>
                  {data.growers.map(g => (
                    <Fragment key={g.farm_id}>
                      <tr className="grower-row" style={{ cursor: 'pointer' }} onClick={() => setOpen(open === g.farm_id ? null : g.farm_id)}>
                        <td>{g.rank}</td>
                        <td><strong>{g.farm_name}</strong><br /><small className="muted">{g.owner_name} · {g.region} · {open === g.farm_id ? '▾ hide' : '▸ cycles'}</small></td>
                        <td><span className={`sev ${scoreClass(g.score)}`}>{g.score}</span></td>
                        <td>{g.avg_fcr}</td>
                        <td>{g.avg_mortality_pct}%</td>
                        <td>{g.fcr_spread ?? '—'}</td>
                        <td>{g.cycle_count}</td>
                        <td>{g.available ? <span className="gap-ok">Free</span> : <small className="muted">{g.availability}</small>}</td>
                      </tr>
                      {open === g.farm_id && (
                        <tr><td colSpan={8} style={{ background: 'var(--bg)' }}>
                          <p style={{ margin: '0.25rem 0' }}>Score parts (vs your other growers): feed efficiency {g.parts.fcr},
                            mortality {g.parts.mortality}, consistency {g.parts.consistency}.</p>
                          <table>
                            <thead><tr><th>Settled</th><th>Placed</th><th>FCR</th><th>Mortality</th><th>Avg weight</th><th>Age</th></tr></thead>
                            <tbody>
                              {g.cycles.map(c => (
                                <tr key={c.flock_id}><td>{c.closed}</td><td>{c.placement_date}</td><td>{c.fcr}</td>
                                  <td>{c.mortality_pct}%</td><td>{c.avg_weight_kg ? `${c.avg_weight_kg} kg` : '—'}</td><td>{c.age_days}d</td></tr>
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

          {data.new_growers.length > 0 && (
            <>
              <h2 style={{ marginTop: '1.5rem' }}>New growers (no settled flock yet)</h2>
              <div className="table-wrapper">
                <table>
                  <thead><tr><th>Farm</th><th>Region</th><th>Capacity</th><th>Next chicks?</th></tr></thead>
                  <tbody>
                    {data.new_growers.map(g => (
                      <tr key={g.farm_id}><td>{g.farm_name}</td><td>{g.region}</td><td>{n(g.capacity)}</td>
                        <td>{g.available ? <span className="gap-ok">Free</span> : <small className="muted">{g.availability}</small>}</td></tr>
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
