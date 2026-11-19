import { useEffect, useState } from 'react';
import { feedCountAPI, getErrorMessage } from '../api/client';
import { todayISO } from '../utils/dates';
import { useFeatures } from '../utils/features';
import '../styles/insights.css';

const FEEDS = [['bpsc_bags', 'BPSC'], ['bsc_bags', 'BSC'], ['bfp_bags', 'BFP']];
const emptyForm = () => ({ date: todayISO(), bpsc_bags: '', bsc_bags: '', bfp_bags: '', notes: '' });

export function GapText({ gap }) {
  if (gap > 0) return <span className="gap-short">{gap} bags short</span>;
  if (gap < 0) return <span className="gap-excess">{-gap} bags extra</span>;
  return <span className="gap-ok">Matches</span>;
}

/** Physical feed-bag counts for one flock, compared with paper stock (feed leakage check). */
export default function BagCountSection(props) {
  const { isOn } = useFeatures();
  return isOn('feed_audit') ? <BagCounts {...props} /> : null;
}

function BagCounts({ flock, canEdit, isAdmin }) {
  const [counts, setCounts] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(null);

  const load = () => feedCountAPI.list(flock.id).then(r => setCounts(r.data)).catch(() => {});
  useEffect(() => { load(); }, [flock.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const active = flock.status === 'active';
  if (!active && counts.length === 0) return null;

  const save = async (e) => {
    e.preventDefault();
    setError('');
    try {
      const body = { flock: flock.id, date: form.date, notes: form.notes };
      for (const [k] of FEEDS) body[k] = parseInt(form[k], 10) || 0;
      const r = await feedCountAPI.create(body);
      setSaved(r.data);
      setOpen(false);
      setForm(emptyForm());
      load();
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };

  const remove = async (c) => {
    if (!window.confirm(`Remove the bag count of ${c.date}?`)) return;
    try { await feedCountAPI.remove(c.id); load(); } catch (err) { alert(getErrorMessage(err)); }
  };

  return (
    <section className="bag-counts" style={{ margin: '1rem 0 1.5rem' }}>
      <div className="page-header" style={{ marginBottom: '0.5rem' }}>
        <h2 style={{ margin: 0 }}>Feed Bag Counts</h2>
        {active && canEdit && (
          <button className="btn btn-secondary" onClick={() => { setOpen(!open); setSaved(null); setError(''); }}>
            + Bag Count
          </button>
        )}
      </div>
      <p className="muted" style={{ marginTop: 0 }}>
        Count the bags at the farm after the day's feeding is entered. The app compares your count with paper stock
        (feed received − feed recorded as eaten). Count at least once a week and before closing the flock.
      </p>

      {saved && (
        <div className={`alert-banner ${saved.gap_bags > 0 ? 'alert-banner-danger' : saved.gap_bags < 0 ? 'alert-banner-warning' : ''} count-result`}>
          Count saved. Paper stock {saved.book.total} bags, counted {saved.book.total - saved.gap_bags} → <GapText gap={saved.gap_bags} />.
          {saved.gap_bags !== 0 && ' If a daily entry is wrong, correct it; otherwise the admin will see this in the Feed Audit.'}
        </div>
      )}

      {open && (
        <form onSubmit={save} className="form-card" style={{ marginBottom: '1rem' }}>
          <h3>Record Bag Count</h3>
          {error && <div className="error-msg">{error}</div>}
          <div className="form-row">
            <div className="form-group">
              <label>Date *</label>
              <input type="date" value={form.date} required min={flock.placement_date} max={todayISO()}
                     onChange={e => setForm({ ...form, date: e.target.value })} />
            </div>
            {FEEDS.map(([k, label]) => (
              <div className="form-group" key={k}>
                <label>{label} bags</label>
                <input type="text" inputMode="numeric" pattern="[0-9]*" value={form[k]} placeholder="0"
                       onChange={e => setForm({ ...form, [k]: e.target.value })} />
              </div>
            ))}
          </div>
          <div className="form-group">
            <label>Notes</label>
            <input value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })}
                   placeholder="e.g. 2 torn bags, counted with farmer" />
          </div>
          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={() => setOpen(false)}>Cancel</button>
            <button type="submit" className="btn btn-primary">Save Count</button>
          </div>
        </form>
      )}

      {counts.length > 0 && (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr><th>Date</th><th>Counted (BPSC / BSC / BFP)</th><th>Paper</th><th>Difference</th><th>By</th>{isAdmin && <th></th>}</tr>
            </thead>
            <tbody>
              {counts.map(c => (
                <tr key={c.id}>
                  <td>{c.date}</td>
                  <td>{c.bpsc_bags} / {c.bsc_bags} / {c.bfp_bags}</td>
                  <td>{c.book.total}</td>
                  <td><GapText gap={c.gap_bags} /></td>
                  <td>{c.counted_by_name}</td>
                  {isAdmin && <td><button className="btn-action btn-action-cancel" onClick={() => remove(c)}>Remove</button></td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
