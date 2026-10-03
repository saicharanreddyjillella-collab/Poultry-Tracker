import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { inventoryAPI, accountingAPI, layerAPI, getErrorMessage } from '../api/client';

const BIZ = { business: 'layer' };
const CASH_ACCS = [['CASH', 'Cash'], ['BANK', 'Bank'], ['UPI', 'UPI']];

export default function LayerMasters() {
  const [tab, setTab] = useState('Items');
  const [editItemId, setEditItemId] = useState(null);
  const [editPartyId, setEditPartyId] = useState(null);
  const [ok, setOk] = useState('');
  const today = new Date().toISOString().slice(0, 10);
  const [opening, setOpening] = useState({ mode: 'party', as_of: today, account_code: 'CASH' });
  const [items, setItems] = useState([]);
  const [units, setUnits] = useState([]);
  const [groups, setGroups] = useState([]);
  const [showGroup, setShowGroup] = useState(false);
  const [groupForm, setGroupForm] = useState({ name: '', under: '' });
  const [parties, setParties] = useState([]);
  const [showItem, setShowItem] = useState(false);
  const [showParty, setShowParty] = useState(false);
  const [itemForm, setItemForm] = useState({ name: '', base_unit: '', stock_group: '' });
  const [partyForm, setPartyForm] = useState({ name: '', phone: '', address: '', party_type: 'SUPPLIER' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const load = () => {
    Promise.all([inventoryAPI.items(BIZ), inventoryAPI.units(), accountingAPI.parties(BIZ), inventoryAPI.stockGroups(BIZ)])
      .then(([i, u, p, g]) => { setItems(i.data); setUnits(u.data); setParties(p.data); setGroups(g.data); setLoading(false); })
      .catch(() => setLoading(false));
  };
  useEffect(load, []);

  const fmt = (n) => Number(n).toLocaleString('en-IN', { maximumFractionDigits: 2 });

  const submitItem = async (e) => {
    e.preventDefault(); setError('');
    try {
      const payload = { name: itemForm.name, base_unit: itemForm.base_unit, stock_group: itemForm.stock_group || undefined, business: 'layer' };
      if (editItemId) await inventoryAPI.updateItem(editItemId, payload);
      else await inventoryAPI.createItem(payload);
      setShowItem(false); setEditItemId(null); setItemForm({ name: '', base_unit: '', stock_group: '' }); load();
    } catch (err) { setError(getErrorMessage(err)); }
  };

  const editItem = (it) => { setEditItemId(it.id); setItemForm({ name: it.name, base_unit: it.base_unit, stock_group: it.stock_group || '' }); setShowItem(true); setError(''); };

  const submitGroup = async (e) => {
    e.preventDefault(); setError('');
    try {
      await inventoryAPI.createStockGroup({ name: groupForm.name, under: groupForm.under || undefined, business: 'layer' });
      setShowGroup(false); setGroupForm({ name: '', under: '' }); load();
    } catch (err) { setError(getErrorMessage(err)); }
  };

  const submitParty = async (e) => {
    e.preventDefault(); setError('');
    try {
      const accRes = await accountingAPI.accounts();
      const wantCode = partyForm.party_type === 'SUPPLIER' ? 'CREDITORS' : 'DEBTORS';
      const ctrl = accRes.data.find(a => a.code === wantCode);
      const payload = { ...partyForm, control_account: ctrl.id, business: 'layer' };
      if (editPartyId) await accountingAPI.updateParty(editPartyId, payload);
      else await accountingAPI.createParty(payload);
      setShowParty(false); setEditPartyId(null); setPartyForm({ name: '', phone: '', address: '', party_type: 'SUPPLIER' }); load();
    } catch (err) { setError(getErrorMessage(err)); }
  };

  const editParty = (p) => { setEditPartyId(p.id); setPartyForm({ name: p.name, phone: p.phone || '', address: p.address || '', party_type: p.party_type }); setShowParty(true); setError(''); };

  const submitOpening = async (e) => {
    e.preventDefault(); setError(''); setOk('');
    try {
      if (opening.mode === 'party') await layerAPI.openingParty({ party: opening.party, amount: opening.amount, as_of: opening.as_of });
      else await layerAPI.openingCash({ account_code: opening.account_code, amount: opening.amount, as_of: opening.as_of });
      setOk('Opening balance recorded.'); setOpening({ mode: opening.mode, as_of: opening.as_of, account_code: 'CASH' }); load();
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
        {['Stock Items', 'Stock Groups', 'Vendors & Traders', 'Opening Balances'].map(t => (
          <button key={t} className={`report-tab ${tab === t ? 'report-tab-active' : ''}`} onClick={() => { setTab(t); setError(''); setOk(''); }}>{t}</button>
        ))}
      </div>

      {error && <div className="error-msg">{error}</div>}
      {ok && <div className="alert-banner alert-banner-success">{ok}</div>}

      {tab === 'Opening Balances' && (
        <form onSubmit={submitOpening} className="form-card" style={{ maxWidth: 520 }}>
          <h3>Record Opening Balance</h3>
          <p className="farm-meta" style={{ marginBottom: '0.75rem' }}>What was owed, and starting cash, when you began. +ve = owes us / cash in hand; −ve = we owe.</p>
          <div className="form-group">
            <label>Type</label>
            <select value={opening.mode} onChange={e => setOpening({ ...opening, mode: e.target.value })}>
              <option value="party">Vendor / Trader</option>
              <option value="cash">Cash / Bank</option>
            </select>
          </div>
          <div className="form-group"><label>As of date *</label><input type="date" value={opening.as_of} max={today} onChange={e => setOpening({ ...opening, as_of: e.target.value })} required /></div>
          {opening.mode === 'party' ? (
            <div className="form-group">
              <label>Party *</label>
              <select value={opening.party || ''} onChange={e => setOpening({ ...opening, party: e.target.value })} required>
                <option value="">Select…</option>
                {parties.map(p => <option key={p.id} value={p.id}>{p.name} ({p.party_type})</option>)}
              </select>
            </div>
          ) : (
            <div className="form-group">
              <label>Account *</label>
              <select value={opening.account_code} onChange={e => setOpening({ ...opening, account_code: e.target.value })}>
                {CASH_ACCS.map(([c, l]) => <option key={c} value={c}>{l}</option>)}
              </select>
            </div>
          )}
          <div className="form-group"><label>Amount (₹) *</label><input type="text" inputMode="decimal" value={opening.amount || ''} onChange={e => setOpening({ ...opening, amount: e.target.value })} required placeholder="+owes us / −we owe" /></div>
          <div className="form-actions"><button type="submit" className="btn btn-primary">Record</button></div>
        </form>
      )}

      {tab === 'Stock Items' && (
        <>
          <button className="btn btn-primary" onClick={() => { setEditItemId(null); setItemForm({ name: "", base_unit: "", stock_group: "" }); setShowItem(!showItem); }} style={{ marginBottom: '1rem' }}>+ Stock Item</button>
          {showItem && (
            <form onSubmit={submitItem} className="form-card" style={{ maxWidth: 520, marginBottom: '1.5rem' }}>
              <h3>{editItemId ? "Edit Stock Item" : "Add Stock Item"}</h3>
              <div className="form-group"><label>Name *</label><input value={itemForm.name} onChange={e => setItemForm({ ...itemForm, name: e.target.value })} required placeholder="e.g. Maize, Layer Feed, Table Eggs" /></div>
              <div className="form-row">
                <div className="form-group">
                  <label>Stock group *</label>
                  <select value={itemForm.stock_group} onChange={e => setItemForm({ ...itemForm, stock_group: e.target.value })} required>
                    <option value="">Select group…</option>
                    {groups.map(g => <option key={g.id} value={g.id}>{g.path}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label>Unit *</label>
                  <select value={itemForm.base_unit} onChange={e => setItemForm({ ...itemForm, base_unit: e.target.value })} required>
                    <option value="">Select…</option>
                    {units.map(u => <option key={u.id} value={u.id}>{u.symbol}</option>)}
                  </select>
                </div>
              </div>
              <div className="form-actions">
                <button type="button" className="btn btn-secondary" onClick={() => setShowItem(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary">{editItemId ? "Save Changes" : "Save Stock Item"}</button>
              </div>
            </form>
          )}
          {items.length ? (
            <div className="table-wrapper">
              <table className="report-table">
                <thead><tr><th>Name</th><th>Group</th><th>Unit</th><th>Stock</th><th></th></tr></thead>
                <tbody>
                  {items.map(it => (
                    <tr key={it.id}><td>{it.name}</td><td className="farm-meta">{it.stock_group_path || '—'}</td><td>{it.base_unit_symbol}</td><td>{fmt(it.stock_on_hand)} {it.base_unit_symbol}</td><td><button className="btn-action" onClick={() => editItem(it)}>Edit</button></td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <p className="farm-meta">No stock items yet. Create groups first, then add items (maize, feed, eggs…).</p>}
        </>
      )}

      {tab === 'Stock Groups' && (
        <>
          <button className="btn btn-primary" onClick={() => setShowGroup(!showGroup)} style={{ marginBottom: '1rem' }}>+ Stock Group</button>
          {showGroup && (
            <form onSubmit={submitGroup} className="form-card" style={{ maxWidth: 520, marginBottom: '1.5rem' }}>
              <h3>Add Stock Group</h3>
              <div className="form-group"><label>Name *</label><input value={groupForm.name} onChange={e => setGroupForm({ ...groupForm, name: e.target.value })} required placeholder="e.g. Raw Materials" /></div>
              <div className="form-group">
                <label>Under group</label>
                <select value={groupForm.under} onChange={e => setGroupForm({ ...groupForm, under: e.target.value })}>
                  <option value="">Primary (default)</option>
                  {groups.map(g => <option key={g.id} value={g.id}>{g.path}</option>)}
                </select>
              </div>
              <div className="form-actions">
                <button type="button" className="btn btn-secondary" onClick={() => setShowGroup(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary">Save Group</button>
              </div>
            </form>
          )}
          <div className="table-wrapper" style={{ maxWidth: 520 }}>
            <table className="report-table">
              <thead><tr><th>Group</th><th>Items</th></tr></thead>
              <tbody>
                {groups.map(g => (
                  <tr key={g.id}><td>{g.path}{g.is_primary ? ' (default)' : ''}</td><td>{items.filter(i => i.stock_group === g.id).length}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {tab === 'Vendors & Traders' && (
        <>
          <button className="btn btn-primary" onClick={() => { setEditPartyId(null); setPartyForm({ name: "", phone: "", address: "", party_type: "SUPPLIER" }); setShowParty(!showParty); }} style={{ marginBottom: '1rem' }}>+ Party</button>
          {showParty && (
            <form onSubmit={submitParty} className="form-card" style={{ maxWidth: 520, marginBottom: '1.5rem' }}>
              <h3>{editPartyId ? "Edit Party" : "Add Party"}</h3>
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
                <button type="submit" className="btn btn-primary">{editPartyId ? "Save Changes" : "Save Party"}</button>
              </div>
            </form>
          )}
          {parties.length ? (
            <div className="table-wrapper">
              <table className="report-table">
                <thead><tr><th>Name</th><th>Type</th><th>Phone</th><th>Balance</th><th></th></tr></thead>
                <tbody>
                  {parties.map(p => (
                    <tr key={p.id}><td>{p.name}</td><td>{p.party_type}</td><td>{p.phone || '—'}</td>
                      <td className={p.balance >= 0 ? 'text-ok' : 'text-danger'}>{p.balance >= 0 ? `₹${fmt(p.balance)}` : `₹${fmt(-p.balance)} (we owe)`}</td><td><button className="btn-action" onClick={() => editParty(p)}>Edit</button></td></tr>
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
