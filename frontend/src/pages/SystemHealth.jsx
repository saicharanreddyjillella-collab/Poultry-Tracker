import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { featureAPI, getErrorMessage } from '../api/client';
import '../styles/insights.css';

const ICON = { ok: '✓', warn: '!', error: '✕', info: 'i' };
const TEXT = { ok: 'All good', warn: 'Needs a look', error: 'Needs action' };
const when = (iso) => (iso ? new Date(iso).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—');

/** Admin: is everything working? Backups, errors, missing entries, weather, features, who is active. */
export default function SystemHealth() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const load = () => featureAPI.health().then(r => { setData(r.data); setError(''); })
    .catch(err => setError(getErrorMessage(err)));
  useEffect(() => { load(); }, []);

  return (
    <div className="page">
      <div className="page-header">
        <h1>System Health</h1>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn btn-secondary" onClick={load}>Refresh</button>
          <Link to="/settings" className="btn btn-secondary">← Settings</Link>
        </div>
      </div>
      {error && <div className="alert-banner alert-banner-danger">{error}</div>}
      {!data && !error && <p className="muted">Loading…</p>}
      {data && (
        <>
          <div className={`health-overall health-${data.overall}`} role="status">
            {TEXT[data.overall]} · checked {when(data.as_of)} · {data.counts.farms} farms, {data.counts.active_flocks} active
            flocks, {data.counts.users} users
          </div>
          <div className="health-checks">
            {data.checks.map(c => (
              <div key={c.key} className={`health-check health-${c.status}`} data-check={c.key}>
                <span className="health-icon" aria-hidden="true">{ICON[c.status]}</span>
                <div><strong>{c.label}</strong><p>{c.detail}</p></div>
              </div>
            ))}
          </div>

          <h2>Recent errors</h2>
          {data.recent_errors.length === 0 ? <p className="muted">No errors recorded.</p> : (
            <div className="table-wrapper">
              <table>
                <thead><tr><th>When</th><th>Where</th><th>What</th></tr></thead>
                <tbody>
                  {data.recent_errors.map(e => (
                    <tr key={e.id}>
                      <td style={{ whiteSpace: 'nowrap' }}>{when(e.timestamp)}</td>
                      <td>{e.source === 'screen' ? 'Screen' : 'Server'}{e.path ? <><br /><small className="muted">{e.path}</small></> : null}</td>
                      <td style={{ wordBreak: 'break-word' }}>{e.message}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <h2 style={{ marginTop: '1.5rem' }}>Who is active</h2>
          <div className="table-wrapper">
            <table>
              <thead><tr><th>User</th><th>Role</th><th>Last sign-in</th><th>Last change</th><th>Changes (7 days)</th></tr></thead>
              <tbody>
                {data.users.map(u => (
                  <tr key={u.id}>
                    <td>{u.name}<br /><small className="muted">{u.username}</small></td>
                    <td>{u.role}</td>
                    <td>{when(u.last_login)}</td>
                    <td>{when(u.last_change)}</td>
                    <td>{u.changes_7d}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
