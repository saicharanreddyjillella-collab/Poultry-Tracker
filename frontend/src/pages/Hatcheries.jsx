import { Fragment, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { insightsAPI, hatcheryAPI, getErrorMessage } from '../api/client';
import '../styles/insights.css';

const pct = (v) => (v == null ? '—' : `${v}%`);
const VERDICT = { high: 'sev sev-high', medium: 'sev sev-medium', ok: 'sev sev-ok' };
const VERDICT_TEXT = { high: 'Above limit', medium: 'Worse than average', ok: 'OK' };

function HatcheryList({ onChange }) {
  const [rows, setRows] = useState([]);
  const [name, setName] = useState('');
  const [msg, setMsg] = useState('');
  const load = () => hatcheryAPI.list().then(r => setRows(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);
  const act = async (fn, ok) => {
    setMsg('');
    try { await fn(); setMsg(ok); load(); onChange(); } catch (err) { setMsg(getErrorMessage(err)); }
  };
  return (
    <section style={{ marginTop: '2rem' }}>
      <h2>Hatchery list</h2>
      <p className="muted">Supervisors pick from this list when they place a flock. A hatchery that has flocks can't be
        removed — mark it “not used” so it disappears from new flocks but stays in history.</p>
      {msg && <div className="alert-banner">{msg}</div>}
      <form className="loc-row" onSubmit={e => { e.preventDefault(); act(() => hatcheryAPI.create({ name }), `Added ${name}.`).then(() => setName('')); }}>
        <div className="form-group"><label>New hatchery</label>
          <input value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Sri Venkateswara Hatcheries" required /></div>
        <button type="submit" className="btn btn-primary">Add</button>
      </form>
      <div className="table-wrapper">
        <table>
          <thead><tr><th>Name</th><th>Status</th><th></th></tr></thead>
          <tbody>
            {rows.map(h => (
              <tr key={h.id}>
                <td>{h.name}</td>
                <td>{h.active ? 'In use' : <span className="muted">Not used</span>}</td>
                <td style={{ whiteSpace: 'nowrap' }}>
                  <button className="btn-action btn-action-edit" onClick={() => act(() => hatcheryAPI.update(h.id, { active: !h.active }), `${h.name} updated.`)}>
                    {h.active ? 'Mark not used' : 'Use again'}
                  </button>{' '}
                  <button className="btn-action btn-action-cancel" onClick={() => act(() => hatcheryAPI.remove(h.id), `Removed ${h.name}.`)}>Remove</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

/** Admin: chick quality compared across hatcheries. */
export default function Hatcheries() {
  const [days, setDays] = useState(180);
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [openRow, setOpenRow] = useState(null);
  const load = () => insightsAPI.hatcheries(days).then(r => { setData(r.data); setError(''); })
    .catch(err => setError(getErrorMessage(err)));
  useEffect(() => { load(); }, [days]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="page">
      <div className="page-header">
        <h1>Chick Quality by Hatchery</h1>
        <Link to="/insights" className="btn btn-secondary">← Insights</Link>
      </div>
      <p className="muted">How each hatchery's chicks did on your farms: first-week mortality (days 1–7 — mostly chick
        quality, not farm management), dead on arrival and chick weight. Use it when you complain to a hatchery or
        decide where to buy.</p>
      <div className="form-group" style={{ maxWidth: 220 }}>
        <label>Flocks placed in the last</label>
        <select value={days} onChange={e => setDays(parseInt(e.target.value))}>
          {[90, 180, 365, 730].map(d => <option key={d} value={d}>{d} days</option>)}
        </select>
      </div>
      {error && <div className="alert-banner alert-banner-danger">{error}</div>}
      {!data && !error && <p className="muted">Loading…</p>}
      {data && (data.hatcheries.length === 0 ? <div className="alert-banner">No flocks placed in this period.</div> : (
        <>
          <div className="stats-grid" style={{ marginBottom: '1rem' }}>
            <div className="stat-card"><span className="stat-label">First-week mortality, all</span><span className="stat-value">{pct(data.overall.week1_pct)}</span><small className="muted">limit {data.first_week_limit_pct}%</small></div>
            <div className="stat-card"><span className="stat-label">Dead on arrival, all</span><span className="stat-value">{pct(data.overall.doa_pct)}</span></div>
            <div className="stat-card"><span className="stat-label">Flocks</span><span className="stat-value">{data.overall.flocks_count}</span></div>
          </div>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr><th>Hatchery</th><th>Flocks</th><th>Chicks</th><th>1st-week mortality</th><th>Over limit</th>
                  <th>Dead on arrival</th><th>Avg chick wt</th><th>Final mortality</th><th>Verdict</th></tr>
              </thead>
              <tbody>
                {data.hatcheries.map(h => {
                  const key = h.hatchery_id ?? 'none';
                  return (
                    <Fragment key={key}>
                      <tr className="hatchery-row" onClick={() => setOpenRow(openRow === key ? null : key)} style={{ cursor: 'pointer' }}>
                        <td><strong>{h.name}</strong>{h.active === false && <small className="muted"> · not used</small>}<br /><small className="muted">{openRow === key ? '▾ hide flocks' : '▸ show flocks'}</small></td>
                        <td>{h.flocks_count}</td>
                        <td>{h.chicks.toLocaleString('en-IN')}</td>
                        <td><strong>{pct(h.week1_pct)}</strong>{h.week1_flocks < h.flocks_count && <small className="muted"><br />{h.week1_flocks} past week 1</small>}</td>
                        <td>{h.over_limit_flocks || '—'}</td>
                        <td>{h.doa} ({pct(h.doa_pct)})</td>
                        <td>{h.avg_chick_weight_g ? `${h.avg_chick_weight_g} g` : '—'}</td>
                        <td>{pct(h.final_mortality_pct)}</td>
                        <td>{h.verdict_level ? <span className={VERDICT[h.verdict_level]} title={h.verdict}>{VERDICT_TEXT[h.verdict_level]}</span> : <span className="muted">too early</span>}</td>
                      </tr>
                      {openRow === key && (
                        <tr><td colSpan={9} style={{ background: 'var(--bg)' }}>
                          <p style={{ margin: '0.25rem 0 0.5rem' }}>{h.verdict}</p>
                          <table>
                            <thead><tr><th>Farm</th><th>Placed</th><th>Chicks</th><th>1st week</th><th>DOA</th><th>Chick wt</th></tr></thead>
                            <tbody>
                              {h.flocks.map(f => (
                                <tr key={f.flock_id}>
                                  <td><Link to={`/flocks/${f.flock_id}`}>{f.farm_name}</Link></td>
                                  <td>{f.placement_date}</td>
                                  <td>{f.chicks.toLocaleString('en-IN')}</td>
                                  <td className={f.over_limit ? 'gap-short' : ''}>{f.week1_pct == null ? <span className="muted">in week 1</span> : `${f.week1_mortality} (${f.week1_pct}%)`}</td>
                                  <td>{f.doa}</td>
                                  <td>{f.chick_weight_g ? `${f.chick_weight_g} g` : '—'}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </td></tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      ))}
      <HatcheryList onChange={load} />
    </div>
  );
}
