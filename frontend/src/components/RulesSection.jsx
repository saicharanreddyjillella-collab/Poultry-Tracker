import { useEffect, useState } from 'react';
import { rulesAPI, getErrorMessage } from '../api/client';

/** Settings → Rules: admin-set numbers such as the edit window. */
export default function RulesSection() {
  const [rules, setRules] = useState([]);
  const [values, setValues] = useState({});
  const [msg, setMsg] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    rulesAPI.list().then(r => {
      setRules(r.data);
      setValues(Object.fromEntries(r.data.map(x => [x.key, x.value])));
    }).catch(err => setError(getErrorMessage(err)));
  }, []);

  const save = async (e) => {
    e.preventDefault(); setMsg(''); setError('');
    try {
      const r = await rulesAPI.save(values);
      setRules(r.data);
      setMsg('Saved.');
    } catch (err) {
      const d = err.response?.data;
      setError(d && typeof d === 'object' ? Object.values(d).join(' ') : getErrorMessage(err));
    }
  };

  if (!rules.length && !error) return null;
  return (
    <form className="settings-link-card rules-card" onSubmit={save} aria-label="Rules">
      <div style={{ flex: 1 }}>
        <h2>Rules</h2>
        {rules.map(r => (
          <div className="form-group rule-row" key={r.key}>
            <label htmlFor={`rule-${r.key}`}>{r.name}</label>
            <input id={`rule-${r.key}`} type="number" min={r.min} max={r.max} step="1" value={values[r.key] ?? ''}
                   onChange={e => setValues({ ...values, [r.key]: e.target.value })} />
            <p className="form-hint">{r.description}</p>
          </div>
        ))}
        {error && <p className="error-msg" role="alert">{error}</p>}
        {msg && <p className="tone-ok" role="status">{msg}</p>}
      </div>
      <button type="submit" className="btn btn-primary">Save rules</button>
    </form>
  );
}
