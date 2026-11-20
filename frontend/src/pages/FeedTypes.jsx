import { useState } from 'react';
import { Link } from 'react-router-dom';
import { feedTypeAPI, getErrorMessage } from '../api/client';
import FeedBadge from '../components/FeedBadge';
import { Chip, Panel } from '../components/ui';
import useFeedTypes from '../utils/useFeedTypes';

const blank = { code: '', name: '', colour: '#0F766E', per_bird_kg: '' };

/** Admin: the feeds the mill makes. Records keep each type's permanent key, so renaming
 *  (e.g. BFP → BFP1) never breaks history; retired types stay on old records. */
export default function FeedTypes() {
  const { types, reload } = useFeedTypes();
  const [edit, setEdit] = useState(null);          // {id?, code, name, colour, per_bird_kg}
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);

  const act = async (fn, done) => {
    setBusy(true); setError(''); setMsg('');
    try { await fn(); await reload(); if (done) setMsg(done); return true; }
    catch (err) {
      const d = err.response?.data;
      setError(d && typeof d === 'object' ? Object.values(d).flat().join(' ') : getErrorMessage(err));
      return false;
    } finally { setBusy(false); }
  };

  const save = async (e) => {
    e.preventDefault();
    const data = { code: edit.code, name: edit.name, colour: edit.colour,
      per_bird_kg: edit.per_bird_kg === '' ? null : edit.per_bird_kg };
    const ok = await act(() => (edit.id ? feedTypeAPI.update(edit.id, data) : feedTypeAPI.create(data)),
      `Saved ${edit.code.toUpperCase()}.`);
    if (ok) setEdit(null);
  };

  const move = (i, dir) => {
    if (!types[i + dir]) return;
    const order = [...types];
    [order[i], order[i + dir]] = [order[i + dir], order[i]];
    act(() => Promise.all(order.map((t, n) => (t.sort_order === n + 1 ? null : feedTypeAPI.update(t.id, { sort_order: n + 1 })))));
  };

  const set = (k) => (e) => setEdit({ ...edit, [k]: e.target.value });

  return (
    <div className="page">
      <nav className="crumbs" aria-label="Breadcrumb"><Link to="/settings">Settings</Link><span aria-hidden="true">/</span><span>Feed types</span></nav>
      <div className="page-header">
        <div>
          <h1>Feed Types</h1>
          <p className="farm-meta">The feeds you make, in the order birds get them. Every order, transfer, rate, daily
            entry and bag count uses this list. Renaming keeps all past records; a type that has been used can be
            retired (kept on old records, no longer offered) but not deleted.</p>
        </div>
        {!edit && <button className="btn btn-primary" onClick={() => { setEdit({ ...blank }); setMsg(''); }}>+ Add feed type</button>}
      </div>
      {error && <div className="alert-banner alert-banner-danger" role="alert">{error}</div>}
      {msg && <div className="alert-banner alert-banner-success" role="status">{msg}</div>}

      {edit && (
        <form className="panel rate-form" onSubmit={save} aria-label="Feed type">
          <div className="panel-head"><h2>{edit.id ? `Edit ${edit.original}` : 'New feed type'}</h2></div>
          <div className="panel-body">
            <div className="rate-grid">
              <div className="form-group"><label htmlFor="ft-code">Code *</label>
                <input id="ft-code" required maxLength={20} value={edit.code} onChange={set('code')} placeholder="e.g. BFP2" /></div>
              <div className="form-group"><label htmlFor="ft-name">Name</label>
                <input id="ft-name" value={edit.name} onChange={set('name')} placeholder="e.g. Finisher Pellet 2" /></div>
              <div className="form-group"><label htmlFor="ft-kg">Kg per bird</label>
                <input id="ft-kg" type="number" step="0.001" min="0" value={edit.per_bird_kg ?? ''} onChange={set('per_bird_kg')} placeholder="blank = the rest" /></div>
              <div className="form-group"><label htmlFor="ft-colour">Colour</label>
                <input id="ft-colour" type="color" value={edit.colour} onChange={set('colour')} /></div>
            </div>
            <p className="form-hint">Kg per bird: how much of this feed a bird gets before moving to the next one. It sets
              the feed a flock is on now, the feed schedule and the forecast. Leave it blank on the last feed.</p>
            <div className="form-actions">
              <button type="submit" className="btn btn-primary" disabled={busy}>Save</button>
              <button type="button" className="btn btn-secondary" onClick={() => setEdit(null)}>Cancel</button>
            </div>
          </div>
        </form>
      )}

      <Panel label="Feed type list">
        <div className="table-wrapper">
          <table className="data-table cards-on-phone">
            <thead><tr><th>Order</th><th>Feed</th><th>Name</th><th className="r">Kg per bird</th><th>Status</th><th></th></tr></thead>
            <tbody>
              {types.map((t, i) => (
                <tr key={t.id}>
                  <td className="cell-main">
                    <span className="order-btns">
                      <button type="button" className="btn-action" aria-label={`Move ${t.code} up`} disabled={busy || i === 0} onClick={() => move(i, -1)}>↑</button>
                      <button type="button" className="btn-action" aria-label={`Move ${t.code} down`} disabled={busy || i === types.length - 1} onClick={() => move(i, 1)}>↓</button>
                    </span> {i + 1}
                  </td>
                  <td data-label="Feed"><FeedBadge type={t.key} />{t.key !== t.code && <span className="cell-sub">was {t.key}</span>}</td>
                  <td data-label="Name">{t.name || <span className="muted">—</span>}</td>
                  <td data-label="Kg per bird" className="r num">{t.per_bird_kg != null ? Number(t.per_bird_kg) : <span className="muted">the rest</span>}</td>
                  <td data-label="Status">{t.active ? <Chip tone="ok">In use</Chip> : <Chip>Retired</Chip>}</td>
                  <td className="row-actions">
                    <button className="btn btn-secondary btn-sm" disabled={busy}
                            onClick={() => { setEdit({ id: t.id, original: t.code, code: t.code, name: t.name, colour: t.colour, per_bird_kg: t.per_bird_kg ?? '' }); setMsg(''); }}>Edit</button>
                    <button className="btn btn-secondary btn-sm" disabled={busy}
                            onClick={() => act(() => feedTypeAPI.update(t.id, { active: !t.active }), `${t.code} ${t.active ? 'retired' : 'back in use'}.`)}>
                      {t.active ? 'Retire' : 'Use again'}</button>
                    {!t.in_use && <button className="btn btn-danger btn-sm" disabled={busy}
                            onClick={() => act(() => feedTypeAPI.remove(t.id), `Deleted ${t.code}.`)}>Delete</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
