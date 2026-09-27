import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { accountingAPI, getErrorMessage } from '../api/client';

const BIZ = { business: 'chicken_center' };

export default function ChickenParties() {
  const [parties, setParties] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: '', phone: '', address: '', party_type: 'CUSTOMER' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const load = () => {
    accountingAPI.parties(BIZ).then(r => { setParties(r.data); setLoading(false); }).catch(() => setLoading(false));
  };
  useEffect(load, []);

  const fmt = (n) => Number(n).toLocaleString('en-IN', { maximumFractionDigits: 2 });

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    try {
      // control account: customers -> DEBTORS, suppliers -> CREDITORS
      const accRes = await accountingAPI.accounts();
      const wantCode = form.party_type === 'SUPPLIER' ? 'CREDITORS' : 'DEBTORS';
      const ctrl = accRes.data.find(a => a.code === wantCode);
      await accountingAPI.createParty({
        name: form.name, phone: form.phone, address: form.address,
        party_type: form.party_type, control_account: ctrl.id, business: 'chicken_center',
      });
      setShowForm(false);
      setForm({ name: '', phone: '', address: '', party_type: 'CUSTOMER' });
      load();
    } catch (err) { setError(getErrorMessage(err)); }
  };

  if (loading) return <div className="loading">Loading…</div>;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <button className="back-link" onClick={() => navigate('/chicken')}>&larr; Chicken Center</button>
          <h1>Parties</h1>
        </div>
        <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>+ Add Party</button>
      </div>

      {error && <div className="error-msg">{error}</div>}

      {showForm && (
        <form onSubmit={submit} className="form-card" style={{ maxWidth: 520, marginBottom: '1.5rem' }}>
          <h3>Add Party</h3>
          <div className="form-group">
            <label>Type *</label>
            <select value={form.party_type} onChange={e => setForm({ ...form, party_type: e.target.value })}>
              <option value="CUSTOMER">Customer (shop)</option>
              <option value="SUPPLIER">Supplier</option>
              <option value="BOTH">Both</option>
            </select>
          </div>
          <div className="form-group"><label>Name *</label><input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required /></div>
          <div className="form-group"><label>Phone (for WhatsApp)</label><input value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} placeholder="10-digit mobile" /></div>
          <div className="form-group"><label>Address</label><input value={form.address} onChange={e => setForm({ ...form, address: e.target.value })} /></div>
          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={() => setShowForm(false)}>Cancel</button>
            <button type="submit" className="btn btn-primary">Save</button>
          </div>
        </form>
      )}

      {parties.length ? (
        <div className="table-wrapper">
          <table className="report-table">
            <thead><tr><th>Name</th><th>Type</th><th>Phone</th><th>Balance</th><th></th></tr></thead>
            <tbody>
              {parties.map(p => (
                <tr key={p.id}>
                  <td>{p.name}</td>
                  <td>{p.party_type}</td>
                  <td>{p.phone || '—'}</td>
                  <td className={p.balance >= 0 ? 'text-ok' : 'text-danger'}>
                    {p.balance >= 0 ? `₹${fmt(p.balance)}` : `₹${fmt(-p.balance)} (we owe)`}
                  </td>
                  <td><Link to={`/chicken/parties/${p.id}`} className="back-link">Statement →</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <p className="farm-meta">No parties yet. Add your first customer or supplier.</p>}
    </div>
  );
}
