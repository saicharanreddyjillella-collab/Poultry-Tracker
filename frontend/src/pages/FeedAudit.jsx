import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { insightsAPI, getErrorMessage } from '../api/client';
import { GapText } from '../components/BagCountSection';
import '../styles/insights.css';

const rupees = (n) => `₹${Number(n || 0).toLocaleString('en-IN')}`;

/** Admin: where feed may be leaking — bag counts vs paper, feeding vs the age standard. */
export default function FeedAudit() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [region, setRegion] = useState('');
  const [problemsOnly, setProblemsOnly] = useState(true);

  useEffect(() => {
    insightsAPI.feedAudit().then(r => setData(r.data)).catch(err => setError(getErrorMessage(err)));
  }, []);

  const regions = useMemo(() => [...new Set((data?.rows || []).map(r => r.region).filter(Boolean))].sort(), [data]);
  const rows = (data?.rows || []).filter(r =>
    (!region || r.region === region) && (!problemsOnly || r.severity === 'high' || r.severity === 'medium'));

  return (
    <div className="page">
      <div className="page-header">
        <h1>Feed Audit</h1>
        <Link to="/insights" className="btn btn-secondary">← Insights</Link>
      </div>
      <p className="muted">
        Where feed may be leaving the farm: supervisors' bag counts against paper stock, feed recorded against the
        age standard, and feed left over when a flock closed. Covers active flocks and flocks closed in the last 45 days.
      </p>
      {error && <div className="alert-banner alert-banner-danger">{error}</div>}
      {!data && !error && <p className="muted">Loading…</p>}
      {data && (
        <>
          <div className="stats-grid stats-grid-wide" style={{ marginBottom: '1rem' }}>
            <div className="stat-card"><span className="stat-label">Flocks checked</span><span className="stat-value">{data.summary.flocks_checked}</span></div>
            <div className={`stat-card ${data.summary.flagged ? 'stat-alert' : ''}`}><span className="stat-label">Need a look</span><span className="stat-value">{data.summary.flagged}</span></div>
            <div className="stat-card"><span className="stat-label">Serious</span><span className="stat-value">{data.summary.high}</span></div>
            <div className="stat-card stat-info"><span className="stat-label">Feed value at risk</span><span className="stat-value">{rupees(data.summary.value_at_risk)}</span><small className="muted">at {rupees(data.feed_cost_per_kg)}/kg</small></div>
            <div className="stat-card"><span className="stat-label">Bag counts due</span><span className="stat-value">{data.summary.counts_due}</span></div>
          </div>

          <div className="form-row" style={{ alignItems: 'flex-end', marginBottom: '0.75rem' }}>
            <div className="form-group" style={{ margin: 0 }}>
              <label>Region</label>
              <select value={region} onChange={e => setRegion(e.target.value)}>
                <option value="">All regions</option>
                {regions.map(r => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
            <label style={{ display: 'flex', gap: '0.4rem', alignItems: 'center', margin: 0 }}>
              <input type="checkbox" checked={problemsOnly} onChange={e => setProblemsOnly(e.target.checked)} />
              Problems only
            </label>
          </div>

          {rows.length === 0 ? (
            <div className="alert-banner">{problemsOnly ? 'No feed problems found.' : 'No flocks to show.'}</div>
          ) : (
            <div className="table-wrapper">
              <table>
                <thead>
                  <tr><th>Farm</th><th>Region</th><th>Age</th><th>Last count</th><th>What we found</th><th>At risk</th></tr>
                </thead>
                <tbody>
                  {rows.map(r => (
                    <tr key={r.flock_id}>
                      <td>
                        <Link to={`/flocks/${r.flock_id}`}>{r.farm_name}</Link>
                        <br /><small className="muted">{r.farm_code}{r.status === 'closed' ? ' · closed' : ''}</small>
                      </td>
                      <td>{r.region}</td>
                      <td>{r.age_days}d</td>
                      <td>{r.last_count ? <>{r.last_count.date}<br /><GapText gap={r.last_count.gap_bags} /></> : <span className="muted">none</span>}</td>
                      <td>
                        {r.flags.length === 0 ? <span className="sev sev-ok">OK</span> : (
                          <ul className="flag-list">
                            {r.flags.map(f => (
                              <li key={f.code}><span className={`sev sev-${f.severity}`}>{f.severity}</span>{f.message}</li>
                            ))}
                          </ul>
                        )}
                      </td>
                      <td>{r.value_at_risk ? rupees(r.value_at_risk) : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <h2 style={{ marginTop: '1.5rem' }}>How the checks work</h2>
          <ul className="muted" style={{ lineHeight: 1.6 }}>
            <li><strong>Bags short</strong> — the supervisor's count is below paper stock (received − recorded as eaten) by 2+ bags and 2%+ of feed received.</li>
            <li><strong>Bags extra</strong> — more bags at the farm than paper says: feeding was recorded that didn't happen.</li>
            <li><strong>Above standard</strong> — recorded feed is over 10% above the Cobb standard for the birds' age and numbers, while birds are under 95% of standard weight (or not weighed).</li>
            <li><strong>Left at close</strong> — paper still showed feed when the flock closed and it was never moved to another flock.</li>
            <li><strong>Count due</strong> — no bag count in the last 7 days (flocks 7+ days old).</li>
          </ul>
        </>
      )}
    </div>
  );
}
