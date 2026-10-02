import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { layerAPI, inventoryAPI, getErrorMessage } from '../api/client';

const BIZ = { business: 'layer' };

export default function LayerFeedMill() {
  const [batches, setBatches] = useState([]);
  const [items, setItems] = useState([]);
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ date: new Date().toISOString().slice(0, 10), feed_item: '', output_kg: '', overhead: '' });
  const [inputs, setInputs] = useState([{ item: '', qty_kg: '', cost: '' }]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const load = () => {
    Promise.all([layerAPI.feedBatches(), inventoryAPI.items(BIZ)]).then(([b, it]) => {
      setBatches(b.data); setItems(it.data); setLoading(false);
    }).catch(() => setLoading(false));
  };
  useEffect(load, []);

  const fmt = (n) => Number(n).toLocaleString('en-IN', { maximumFractionDigits: 2 });
  const rawItems = items.filter(i => i.kind === 'RAW');
  const feedItems = items.filter(i => i.kind === 'FINISHED');

  const matCost = inputs.reduce((t, i) => t + (Number(i.cost) || 0), 0);
  const totalCost = matCost + (Number(form.overhead) || 0);
  const perKg = Number(form.output_kg) > 0 ? (totalCost / Number(form.output_kg)) : 0;

  const submit = async (e) => {
    e.preventDefault(); setError('');
    const validInputs = inputs.filter(i => i.item && i.qty_kg && i.cost);
    if (!validInputs.length) { setError('Add at least one material.'); return; }
    try {
      await layerAPI.createFeedBatch({
        date: form.date, feed_item: form.feed_item, output_kg: form.output_kg,
        overhead: form.overhead || 0,
        inputs: validInputs.map(i => ({ item: i.item, qty_kg: i.qty_kg, cost: i.cost })),
      });
      setShow(false);
      setForm({ date: new Date().toISOString().slice(0, 10), feed_item: '', output_kg: '', overhead: '' });
      setInputs([{ item: '', qty_kg: '', cost: '' }]);
      load();
    } catch (err) { setError(getErrorMessage(err)); }
  };

  if (loading) return <div className="loading">Loading…</div>;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <button className="back-link" onClick={() => navigate('/layer')}>&larr; Layer Farm</button>
          <h1>Feed Mill</h1>
          <p className="farm-meta">Convert raw materials into feed — batch cost carries to flocks</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShow(!show)}>+ New Batch</button>
      </div>

      {error && <div className="error-msg">{error}</div>}

      {show && (
        <form onSubmit={submit} className="form-card" style={{ maxWidth: 640, marginBottom: '1.5rem' }}>
          <h3>Production Batch</h3>
          <div className="form-row">
            <div className="form-group"><label>Date *</label><input type="date" value={form.date} max={new Date().toISOString().slice(0, 10)} onChange={e => setForm({ ...form, date: e.target.value })} required /></div>
            <div className="form-group">
              <label>Feed produced *</label>
              <select value={form.feed_item} onChange={e => setForm({ ...form, feed_item: e.target.value })} required>
                <option value="">Select feed item…</option>
                {feedItems.map(i => <option key={i.id} value={i.id}>{i.name}</option>)}
              </select>
            </div>
            <div className="form-group"><label>Output (kg) *</label><input type="text" inputMode="decimal" value={form.output_kg} onChange={e => setForm({ ...form, output_kg: e.target.value })} required /></div>
          </div>

          <label className="bill-flag-title">Materials consumed</label>
          <div className="pending-panel">
            {inputs.map((ln, i) => (
              <div className="form-row" key={i} style={{ alignItems: 'flex-end' }}>
                <div className="form-group" style={{ flex: 2 }}>
                  <label>Material</label>
                  <select value={ln.item} onChange={e => { const c = [...inputs]; c[i] = { ...c[i], item: e.target.value }; setInputs(c); }}>
                    <option value="">Select…</option>
                    {rawItems.map(it => <option key={it.id} value={it.id}>{it.name}</option>)}
                  </select>
                </div>
                <div className="form-group"><label>kg</label><input type="text" inputMode="decimal" value={ln.qty_kg} onChange={e => { const c = [...inputs]; c[i] = { ...c[i], qty_kg: e.target.value }; setInputs(c); }} /></div>
                <div className="form-group"><label>Cost ₹</label><input type="text" inputMode="decimal" value={ln.cost} onChange={e => { const c = [...inputs]; c[i] = { ...c[i], cost: e.target.value }; setInputs(c); }} /></div>
                <div className="form-group" style={{ flex: '0 0 auto' }}>
                  <label>&nbsp;</label>
                  <button type="button" className="btn-action btn-action-cancel" onClick={() => setInputs(inputs.length > 1 ? inputs.filter((_, j) => j !== i) : inputs)}>✕</button>
                </div>
              </div>
            ))}
            <button type="button" className="btn btn-secondary" onClick={() => setInputs([...inputs, { item: '', qty_kg: '', cost: '' }])} style={{ marginTop: '0.4rem' }}>+ Add material</button>
          </div>

          <div className="form-group" style={{ marginTop: '0.75rem' }}>
            <label>Overhead / milling cost (₹)</label>
            <input type="text" inputMode="decimal" value={form.overhead} onChange={e => setForm({ ...form, overhead: e.target.value })} placeholder="optional" />
          </div>

          <p className="farm-meta">
            Materials ₹{fmt(matCost)} + Overhead ₹{fmt(Number(form.overhead) || 0)} = <strong>₹{fmt(totalCost)}</strong>
            {Number(form.output_kg) > 0 && <> → <strong>₹{fmt(perKg)}/kg</strong></>}
          </p>

          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={() => setShow(false)}>Cancel</button>
            <button type="submit" className="btn btn-primary">Save Batch</button>
          </div>
        </form>
      )}

      {batches.length ? (
        <div className="table-wrapper">
          <table className="report-table">
            <thead><tr><th>Date</th><th>Feed</th><th>Output</th><th>Materials</th><th>Overhead</th><th>Total</th><th>Cost/kg</th></tr></thead>
            <tbody>
              {batches.map(b => (
                <tr key={b.id} className={b.is_reversed ? 'row-reversed' : ''}>
                  <td>{b.date}</td><td>{b.feed_name}</td><td>{fmt(b.output_kg)} kg</td>
                  <td>₹{fmt(b.materials_cost)}</td><td>₹{fmt(b.overhead_cost)}</td>
                  <td>₹{fmt(b.total_cost)}</td><td><strong>₹{fmt(b.cost_per_kg)}</strong></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <p className="farm-meta">No feed batches yet. Create items (raw materials + a finished feed) under Items first.</p>}
    </div>
  );
}
