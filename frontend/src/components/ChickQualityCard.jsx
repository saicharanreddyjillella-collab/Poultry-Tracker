import { useEffect, useState } from 'react';
import { chickQualityAPI, hatcheryAPI, getErrorMessage } from '../api/client';

/** Where the chicks came from and how they arrived; editable while the flock is active. */
export default function ChickQualityCard({ flock, canEdit, onSaved }) {
  const [open, setOpen] = useState(false);
  const [hatcheries, setHatcheries] = useState([]);
  const [form, setForm] = useState({});
  const [error, setError] = useState('');

  useEffect(() => {
    if (open) hatcheryAPI.list().then(r => setHatcheries(r.data)).catch(() => {});
  }, [open]);

  const start = () => {
    setForm({ hatchery: flock.hatchery || '', doa_count: flock.doa_count ?? 0, chick_weight_g: flock.chick_weight_g ?? '' });
    setError('');
    setOpen(true);
  };
  const save = async (e) => {
    e.preventDefault();
    try {
      await chickQualityAPI.save(flock.id, {
        hatchery: form.hatchery || null,
        doa_count: parseInt(form.doa_count) || 0,
        chick_weight_g: form.chick_weight_g === '' ? null : form.chick_weight_g,
      });
      setOpen(false);
      onSaved();
    } catch (err) { setError(getErrorMessage(err)); }
  };

  const doaPct = flock.chick_count ? (flock.doa_count / flock.chick_count * 100).toFixed(2) : null;
  const choices = hatcheries.filter(h => h.active || h.id === flock.hatchery);

  return (
    <section className="chick-quality" style={{ margin: '1rem 0' }}>
      <div className="farm-stock-bar">
        <strong>Chicks:</strong>
        <span>Hatchery: {flock.hatchery_name || <span className="muted">not recorded</span>}</span>
        <span>Dead on arrival: {flock.doa_count || 0}{doaPct && flock.doa_count ? ` (${doaPct}%)` : ''}</span>
        <span>Avg chick weight: {flock.chick_weight_g ? `${flock.chick_weight_g} g` : <span className="muted">—</span>}</span>
        {canEdit && flock.status === 'active' && !open && (
          <button className="btn-action btn-action-edit" onClick={start}>Edit</button>
        )}
      </div>
      {open && (
        <form onSubmit={save} className="form-card" style={{ marginTop: '0.75rem' }}>
          <h3>Chick Details</h3>
          {error && <div className="error-msg">{error}</div>}
          <div className="form-row">
            <div className="form-group">
              <label>Hatchery</label>
              <select value={form.hatchery} onChange={e => setForm({ ...form, hatchery: e.target.value })}>
                <option value="">Not recorded</option>
                {choices.map(h => <option key={h.id} value={h.id}>{h.name}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>Dead on Arrival</label>
              <input type="text" inputMode="numeric" pattern="[0-9]*" value={form.doa_count} onChange={e => setForm({ ...form, doa_count: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Avg Chick Weight (g)</label>
              <input type="text" inputMode="decimal" value={form.chick_weight_g} onChange={e => setForm({ ...form, chick_weight_g: e.target.value })} />
            </div>
          </div>
          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={() => setOpen(false)}>Cancel</button>
            <button type="submit" className="btn btn-primary">Save</button>
          </div>
        </form>
      )}
    </section>
  );
}
