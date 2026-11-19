import { useEffect, useState } from 'react';
import { featureAPI, getErrorMessage } from '../api/client';
import { setFeatureLocally } from '../utils/features';
import '../styles/insights.css';

const when = (iso) => iso ? new Date(iso).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '';

/** Admin settings. Features: switch optional features on or off for everyone. */
export default function Settings() {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState('');

  useEffect(() => {
    featureAPI.list().then(r => setRows(r.data)).catch(err => setError(getErrorMessage(err)));
  }, []);

  const toggle = async (f) => {
    setBusy(f.key); setError('');
    try {
      const r = await featureAPI.set(f.key, !f.enabled);
      setRows(rows.map(x => (x.key === f.key ? r.data : x)));
      setFeatureLocally(f.key, r.data.enabled);
    } catch (err) { setError(getErrorMessage(err)); }
    setBusy('');
  };

  return (
    <div className="page">
      <h1>Settings</h1>
      <h2>Features</h2>
      <p className="muted">Switch optional features on or off for everyone. Turning one off hides its screens; data
        already saved is kept and comes back when you turn it on again.</p>
      {error && <div className="alert-banner alert-banner-danger">{error}</div>}
      {!rows && !error && <p className="muted">Loading…</p>}
      {rows && (
        <div className="feature-list">
          {rows.map(f => (
            <div key={f.key} className="feature-row" data-feature={f.key}>
              <div className="feature-text">
                <h3>{f.name} <span className={`sev ${f.enabled ? 'sev-ok' : 'sev-low'}`}>{f.enabled ? 'On' : 'Off'}</span></h3>
                <p>{f.description}</p>
                <p className="muted"><strong>When off:</strong> {f.when_off}</p>
                {f.updated_by && <small className="muted">Last changed by {f.updated_by}, {when(f.updated_at)}</small>}
              </div>
              <label className="switch" title={f.enabled ? 'Turn off' : 'Turn on'}>
                <input type="checkbox" role="switch" aria-label={f.name} checked={f.enabled}
                       disabled={busy === f.key} onChange={() => toggle(f)} />
                <span className="switch-slider" />
              </label>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
