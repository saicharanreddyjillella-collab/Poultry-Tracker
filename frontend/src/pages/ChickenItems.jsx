import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { inventoryAPI, getErrorMessage } from '../api/client';

const BIZ = { business: 'chicken_center' };

export default function ChickenItems() {
  const [items, setItems] = useState([]);
  const [units, setUnits] = useState([]);
  const [showItem, setShowItem] = useState(false);
  const [editItemId, setEditItemId] = useState(null);
  const [showUnit, setShowUnit] = useState(false);
  const [itemForm, setItemForm] = useState({ name: '', kind: 'TRADING', base_unit: '', rate_basis: 'PER_KG' });
  const [unitForm, setUnitForm] = useState({ name: '', symbol: '', base_unit: '', factor_to_base: '1' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const load = () => {
    Promise.all([inventoryAPI.items(BIZ), inventoryAPI.units()]).then(([i, u]) => {
      setItems(i.data); setUnits(u.data); setLoading(false);
    }).catch(() => setLoading(false));
  };
  useEffect(load, []);

  const fmt = (n) => Number(n).toLocaleString('en-IN', { maximumFractionDigits: 2 });

  const submitItem = async (e) => {
    e.preventDefault(); setError('');
    try {
      if (editItemId) await inventoryAPI.updateItem(editItemId, { ...itemForm, business: 'chicken_center' });
      else await inventoryAPI.createItem({ ...itemForm, business: 'chicken_center' });
      setShowItem(false); setEditItemId(null); setItemForm({ name: '', kind: 'TRADING', base_unit: '', rate_basis: 'PER_KG' });
      load();
    } catch (err) { setError(getErrorMessage(err)); }
  };

  const openEditItem = (it) => {
    setEditItemId(it.id);
    setItemForm({ name: it.name, kind: it.kind, base_unit: it.base_unit, rate_basis: it.rate_basis });
    setShowItem(true); setShowUnit(false); setError('');
  };

  const submitUnit = async (e) => {
    e.preventDefault(); setError('');
    try {
      const payload = { name: unitForm.name, symbol: unitForm.symbol,
        factor_to_base: unitForm.factor_to_base || 1 };
      if (unitForm.base_unit) payload.base_unit = unitForm.base_unit;
      await inventoryAPI.createUnit(payload);
      setShowUnit(false); setUnitForm({ name: '', symbol: '', base_unit: '', factor_to_base: '1' });
      load();
    } catch (err) { setError(getErrorMessage(err)); }
  };

  if (loading) return <div className="loading">Loading…</div>;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <button className="back-link" onClick={() => navigate('/chicken')}>&larr; Chicken Center</button>
          <h1>Items &amp; Units</h1>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn btn-primary" onClick={() => { setEditItemId(null); setItemForm({ name: "", kind: "TRADING", base_unit: "", rate_basis: "PER_KG" }); setShowItem(!showItem); setShowUnit(false); }}>+ Item</button>
          <button className="btn btn-secondary" onClick={() => { setShowUnit(!showUnit); setShowItem(false); }}>+ Unit</button>
        </div>
      </div>

      {error && <div className="error-msg">{error}</div>}

      {showUnit && (
        <form onSubmit={submitUnit} className="form-card" style={{ maxWidth: 520, marginBottom: '1.5rem' }}>
          <h3>Add Unit</h3>
          <div className="form-row">
            <div className="form-group"><label>Name *</label><input value={unitForm.name} onChange={e => setUnitForm({ ...unitForm, name: e.target.value })} required placeholder="e.g. Bag" /></div>
            <div className="form-group"><label>Symbol *</label><input value={unitForm.symbol} onChange={e => setUnitForm({ ...unitForm, symbol: e.target.value })} required placeholder="e.g. bag" /></div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Converts to (base unit)</label>
              <select value={unitForm.base_unit} onChange={e => setUnitForm({ ...unitForm, base_unit: e.target.value })}>
                <option value="">None (this is a base)</option>
                {units.map(u => <option key={u.id} value={u.id}>{u.symbol}</option>)}
              </select>
            </div>
            <div className="form-group"><label>1 unit = ? base</label><input type="text" inputMode="decimal" value={unitForm.factor_to_base} onChange={e => setUnitForm({ ...unitForm, factor_to_base: e.target.value })} placeholder="e.g. 50" /></div>
          </div>
          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={() => setShowUnit(false)}>Cancel</button>
            <button type="submit" className="btn btn-primary">Save Unit</button>
          </div>
        </form>
      )}

      {showItem && (
        <form onSubmit={submitItem} className="form-card" style={{ maxWidth: 520, marginBottom: '1.5rem' }}>
          <h3>{editItemId ? "Edit Item" : "Add Item"}</h3>
          <div className="form-group"><label>Name *</label><input value={itemForm.name} onChange={e => setItemForm({ ...itemForm, name: e.target.value })} required placeholder="e.g. Broiler" /></div>
          <div className="form-row">
            <div className="form-group">
              <label>Kind *</label>
              <select value={itemForm.kind} onChange={e => setItemForm({ ...itemForm, kind: e.target.value })}>
                <option value="TRADING">Trading good</option>
                <option value="RAW">Raw material</option>
                <option value="FINISHED">Finished good</option>
              </select>
            </div>
            <div className="form-group">
              <label>Base unit *</label>
              <select value={itemForm.base_unit} onChange={e => setItemForm({ ...itemForm, base_unit: e.target.value })} required>
                <option value="">Select…</option>
                {units.map(u => <option key={u.id} value={u.id}>{u.symbol}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>Rate basis *</label>
              <select value={itemForm.rate_basis} onChange={e => setItemForm({ ...itemForm, rate_basis: e.target.value })}>
                <option value="PER_KG">Per kg</option>
                <option value="PER_UNIT">Per unit</option>
              </select>
            </div>
          </div>
          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={() => setShowItem(false)}>Cancel</button>
            <button type="submit" className="btn btn-primary">{editItemId ? "Save Changes" : "Save Item"}</button>
          </div>
        </form>
      )}

      <h3>Items</h3>
      {items.length ? (
        <div className="table-wrapper">
          <table className="report-table">
            <thead><tr><th>Name</th><th>Kind</th><th>Unit</th><th>Rate basis</th><th>Stock</th><th></th></tr></thead>
            <tbody>
              {items.map(it => (
                <tr key={it.id}>
                  <td>{it.name}</td><td>{it.kind}</td><td>{it.base_unit_symbol}</td>
                  <td>{it.rate_basis === 'PER_KG' ? 'Per kg' : 'Per unit'}</td>
                  <td className={Number(it.stock_on_hand) < 0 ? 'text-danger' : ''}>{fmt(it.stock_on_hand)} {it.base_unit_symbol}</td>
                  <td><button className="btn-action" onClick={() => openEditItem(it)}>Edit</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <p className="farm-meta">No items yet. Add one (e.g. Broiler, base unit kg).</p>}

      <h3 style={{ marginTop: '1.5rem' }}>Units</h3>
      <div className="table-wrapper">
        <table className="report-table">
          <thead><tr><th>Name</th><th>Symbol</th><th>Converts to</th><th>Factor</th></tr></thead>
          <tbody>
            {units.map(u => (
              <tr key={u.id}>
                <td>{u.name}</td><td>{u.symbol}</td>
                <td>{u.base_unit_symbol || '—'}</td>
                <td>{u.base_unit_symbol ? `1 ${u.symbol} = ${fmt(u.factor_to_base)} ${u.base_unit_symbol}` : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
