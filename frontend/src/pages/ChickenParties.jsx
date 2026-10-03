import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { accountingAPI, getErrorMessage } from '../api/client';

const BIZ = { business: 'chicken_center' };
const EMPTY = { name: '', phone: '', email: '', address: '', state: '', gst_number: '', pan: '', party_type: 'BOTH', opening_balance: '', opening_as_of: new Date().toISOString().slice(0,10) };

export default function ChickenParties() {
  const [parties, setParties] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const navigate = useNavigate();

  const load = () => {
    accountingAPI.parties(BIZ).then(r => { setParties(r.data); setLoading(false); }).catch(() => setLoading(false));
  };
  useEffect(load, []);

  const fmt = (n) => Number(n).toLocaleString('en-IN', { maximumFractionDigits: 2 });

  const openAdd = () => { setEditId(null); setForm(EMPTY); setShowForm(true); setError(''); };
  const openEdit = (p) => { setEditId(p.id); setForm({ name: p.name, phone: p.phone || '', email: p.email || '', address: p.address || '', state: p.state || '', gst_number: p.gst_number || '', pan: p.pan || '', party_type: p.party_type, opening_balance: '', opening_as_of: new Date().toISOString().slice(0,10) }); setShowForm(true); setError(''); };

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    try {
      const accRes = await accountingAPI.accounts();
      const wantCode = form.party_type === 'SUPPLIER' ? 'CREDITORS' : 'DEBTORS';
      const ctrl = accRes.data.find(a => a.code === wantCode);
      const payload = { name: form.name, phone: form.phone, email: form.email, address: form.address,
        state: form.state, gst_number: form.gst_number, pan: form.pan,
        party_type: form.party_type, control_account: ctrl.id, business: 'chicken_center' };
      if (!editId && form.opening_balance) { payload.opening_balance = form.opening_balance; payload.opening_as_of = form.opening_as_of; }
      if (editId) await accountingAPI.updateParty(editId, payload);
      else await accountingAPI.createParty(payload);
      setShowForm(false); setEditId(null); setForm(EMPTY);
      load();
    } catch (err) { setError(getErrorMessage(err)); }
  };

  const filtered = parties.filter(p =>
    p.name.toLowerCase().includes(search.toLowerCase()) ||
    (p.phone || '').includes(search));

  if (loading) return <div className="loading">Loading…</div>;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <button className="back-link" onClick={() => navigate('/chicken')}>&larr; Chicken Center</button>
          <h1>Parties</h1>
        </div>
        <button className="btn btn-primary" onClick={openAdd}>+ Add Party</button>
      </div>

      {error && <div className="error-msg">{error}</div>}

      {showForm && (
        <form onSubmit={submit} className="form-card" style={{ maxWidth: 520, marginBottom: '1.5rem' }}>
          <h3>{editId ? 'Edit Ledger' : 'Add Ledger'}</h3>
          <div className="form-row">
            <div className="form-group"><label>Name *</label><input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required /></div>
            <div className="form-group">
              <label>Type *</label>
              <select value={form.party_type} onChange={e => setForm({ ...form, party_type: e.target.value })}>
                <option value="BOTH">Both</option>
                <option value="CUSTOMER">Customer (shop)</option>
                <option value="SUPPLIER">Supplier</option>
              </select>
            </div>
          </div>
          <div className="form-row">
            <div className="form-group"><label>Phone (WhatsApp)</label><input value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} placeholder="10-digit mobile" /></div>
            <div className="form-group"><label>Email</label><input value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} /></div>
          </div>
          <div className="form-group"><label>Address</label><input value={form.address} onChange={e => setForm({ ...form, address: e.target.value })} /></div>
          <div className="form-row">
            <div className="form-group"><label>State</label><input value={form.state} onChange={e => setForm({ ...form, state: e.target.value })} /></div>
            <div className="form-group"><label>GST No.</label><input value={form.gst_number} onChange={e => setForm({ ...form, gst_number: e.target.value })} /></div>
            <div className="form-group"><label>PAN</label><input value={form.pan} onChange={e => setForm({ ...form, pan: e.target.value })} /></div>
          </div>
          {!editId && (
            <div className="form-row">
              <div className="form-group"><label>Opening balance (₹)</label><input type="text" inputMode="decimal" value={form.opening_balance} onChange={e => setForm({ ...form, opening_balance: e.target.value })} placeholder="+owes us / −we owe" /></div>
              <div className="form-group"><label>As of</label><input type="date" value={form.opening_as_of} max={new Date().toISOString().slice(0,10)} onChange={e => setForm({ ...form, opening_as_of: e.target.value })} /></div>
            </div>
          )}
          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={() => { setShowForm(false); setEditId(null); }}>Cancel</button>
            <button type="submit" className="btn btn-primary">{editId ? 'Save Changes' : 'Save'}</button>
          </div>
        </form>
      )}

      {parties.length > 0 && (
        <input className="search-input" placeholder="Search by name or phone…" value={search} onChange={e => setSearch(e.target.value)} style={{ marginBottom: '1rem' }} />
      )}

      {filtered.length ? (
        <div className="table-wrapper">
          <table className="report-table">
            <thead><tr><th>Name</th><th>Type</th><th>Phone</th><th>Balance</th><th></th></tr></thead>
            <tbody>
              {filtered.map(p => (
                <tr key={p.id}>
                  <td>{p.name}</td>
                  <td>{p.party_type}</td>
                  <td>{p.phone || '—'}</td>
                  <td className={p.balance >= 0 ? 'text-ok' : 'text-danger'}>
                    {p.balance >= 0 ? `₹${fmt(p.balance)}` : `₹${fmt(-p.balance)} (we owe)`}
                  </td>
                  <td style={{ whiteSpace: 'nowrap' }}>
                    <button className="btn-action" onClick={() => openEdit(p)} style={{ marginRight: '0.4rem' }}>Edit</button>
                    <Link to={`/chicken/parties/${p.id}`} className="back-link">Statement →</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <p className="farm-meta">{parties.length ? 'No matches.' : 'No parties yet. Add your first customer or supplier.'}</p>}
    </div>
  );
}
