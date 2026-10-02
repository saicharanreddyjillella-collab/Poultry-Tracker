import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { inventoryAPI, accountingAPI, getErrorMessage } from '../api/client';

const BIZ = { business: 'layer' };

export default function LayerMasters() {
  const [tab, setTab] = useState('Items');
  const [items, setItems] = useState([]);
  const [units, setUnits] = useState([]);
  const [parties, setParties] = useState([]);
  const [showItem, setShowItem] = useState(false);
  const [showParty, setShowParty] = useState(false);
  const [itemForm, setItemForm] = useState({ name: '', kind: 'RAW', base_unit: '', rate_basis: 'PER_KG' });
  const [partyForm, setPartyForm] = useState({ name: '', phone: '', address: '', party_type: 'SUPPLIER' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const load = () => {
    Promise.all([inventoryAPI.items(BIZ), inventoryAPI.units(), accountingAPI.parties(BIZ)])
      .then(([i, u, p]) => { setItems(i.data); setUnits(u.data); setParties(p.data); setLoading(false); })
      .catch(() => setLoading(false));
  };
  useEffect(load, []);

  const fmt = (n) => Number(n).toLocaleString('en-IN', { maximumFractionDigits: 2 });

  const submitItem = async (e) => {
    e.preventDefault(); setError('');
    try {
      await inventoryAPI.createItem({ ...itemForm, business: 'layer' });
      setShowItem(false); setItemForm({ name: '', kind: 'RAW', base_unit: '', rate_basis: 'PER_KG' }); load();
    } catch (err) { setError(getErrorMessage(err)); }
  };

  const submitParty = async (e) => {
    e.preventDefault(); setError('');
    try {
      const accRes = await accountingAPI.accounts();
      const wantCode = partyForm.party_type === 'SUPPLIER' ? 'CREDITORS' : 'DEBTORS';
      const ctrl = accRes.data.find(a => a.code === wantCode);
      await accountingAPI.createParty({ ...partyForm, control_account: ctrl.id, business: 'layer' });
      setShowParty(false); setPartyForm({ name: '', phone: '', address: '', party_type: 'SUPPLIER' }); load();
    } catch (err) { setError(getErrorMessage(err)); }
  };

  if (loading) return <div className="loading">Loading…</div>;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <button className="back-link" onClick={() => navigate('/layer')}>&larr; Layer Farm</button>
          <h1>Masters</h1>
        </div>
      </div>

      <div className="report-view-tabs" style={{ marginBottom: '1.25rem' }}>
        {['Items', 'Vendors & Traders'].map(t => (
          <button key={t} className={`report-tab ${tab === t ? 'report-tab-active' : ''}`} onClick={() => { setTab(t); setError(''); }}>{t}</button>
        ))}
      </div>

      {error && <div className="error-msg">{error}</div>}

      {tab === 'Items' && (
        <>
          <button className="btn btn-primary" onClick={() => setShowItem(!showItem)} style={{ marginBottom: '1rem' }}>+ Item</button>
          {showItem && (
            <form onSubmit={submitItem} className="form-card" style={{ maxWidth: 520, marginBottom: '1.5rem' }}>
              <h3>Add Item</h3>
              <div className="form-group"><label>Name *</label><input value={itemForm.name} onChange={e => setItemForm({ ...itemForm, name: e.target.value })} required placeholder="e.g. Maize / Layer Feed" /></div>
              <div className="form-row">
                <div className="form-group">
                  <label>Kind *</label>
                  <select value={itemForm.kind} onChange={e => setItemForm({ ...itemForm, kind: e.target.value })}>
                    <option value="RAW">Raw material</option>
                    <option value="FINISHED">Finished feed</option>
                    <option value="TRADING">Trading good</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Base unit *</label>
                  <select value={itemForm.base_unit} onChange={e => setItemForm({ ...itemForm, base_unit: e.target.value })} required>
                    <option value="">Select…</option>
                    {units.map(u => <option key={u.id} value={u.id}>{u.symbol}</option>)}
                  </select>
                </div>
              </div>
              <div className="form-actions">
                <button type="button" className="btn btn-secondary" onClick={() => setShowItem(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary">Save Item</button>
              </div>
            </form>
          )}
          {items.length ? (
            <div className="table-wrapper">
              <table className="report-table">
                <thead><tr><th>Name</th><th>Kind</th><th>Unit</th><th>Stock</th></tr></thead>
                <tbody>
                  {items.map(it => (
                    <tr key={it.id}><td>{it.name}</td><td>{it.kind}</td><td>{it.base_unit_symbol}</td><td>{fmt(it.stock_on_hand)} {it.base_unit_symbol}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <p className="farm-meta">No items. Add raw materials (maize, soya…) and a finished feed.</p>}
        </>
      )}

      {tab === 'Vendors & Traders' && (
        <>
          <button className="btn btn-primary" onClick={() => setShowParty(!showParty)} style={{ marginBottom: '1rem' }}>+ Party</button>
          {showParty && (
            <form onSubmit={submitParty} className="form-card" style={{ maxWidth: 520, marginBottom: '1.5rem' }}>
              <h3>Add Party</h3>
              <div className="form-group">
                <label>Type *</label>
                <select value={partyForm.party_type} onChange={e => setPartyForm({ ...partyForm, party_type: e.target.value })}>
                  <option value="SUPPLIER">Vendor (supplier)</option>
                  <option value="CUSTOMER">Trader (egg buyer)</option>
                  <option value="BOTH">Both</option>
                </select>
              </div>
              <div className="form-group"><label>Name *</label><input value={partyForm.name} onChange={e => setPartyForm({ ...partyForm, name: e.target.value })} required /></div>
              <div className="form-group"><label>Phone (WhatsApp)</label><input value={partyForm.phone} onChange={e => setPartyForm({ ...partyForm, phone: e.target.value })} /></div>
              <div className="form-group"><label>Address</label><input value={partyForm.address} onChange={e => setPartyForm({ ...partyForm, address: e.target.value })} /></div>
              <div className="form-actions">
                <button type="button" className="btn btn-secondary" onClick={() => setShowParty(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary">Save Party</button>
              </div>
            </form>
          )}
          {parties.length ? (
            <div className="table-wrapper">
              <table className="report-table">
                <thead><tr><th>Name</th><th>Type</th><th>Phone</th><th>Balance</th></tr></thead>
                <tbody>
                  {parties.map(p => (
                    <tr key={p.id}><td>{p.name}</td><td>{p.party_type}</td><td>{p.phone || '—'}</td>
                      <td className={p.balance >= 0 ? 'text-ok' : 'text-danger'}>{p.balance >= 0 ? `₹${fmt(p.balance)}` : `₹${fmt(-p.balance)} (we owe)`}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <p className="farm-meta">No vendors/traders yet.</p>}
        </>
      )}
    </div>
  );
}
