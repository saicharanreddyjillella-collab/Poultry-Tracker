import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { accountingAPI, chickenAPI, getErrorMessage } from '../api/client';

const BIZ = { business: 'chicken_center' };
const CASH_ACCS = [['CASH', 'Cash'], ['BANK', 'Bank'], ['UPI', 'UPI']];

export default function ChickenOpening() {
  const [tab, setTab] = useState('Party');
  const [parties, setParties] = useState([]);
  const [error, setError] = useState('');
  const [ok, setOk] = useState('');
  const [saving, setSaving] = useState(false);
  const navigate = useNavigate();

  const today = new Date().toISOString().slice(0, 10);
  const [form, setForm] = useState({ as_of: today, account_code: 'CASH' });

  useEffect(() => {
    accountingAPI.parties(BIZ).then(r => setParties(r.data)).catch(() => {});
  }, []);

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const submit = async (e) => {
    e.preventDefault(); setError(''); setOk(''); setSaving(true);
    try {
      if (tab === 'Party') {
        await chickenAPI.openingParty({ party: form.party, amount: form.amount, as_of: form.as_of });
        setOk('Party opening balance recorded.');
      } else {
        await chickenAPI.openingCash({ account_code: form.account_code, amount: form.amount, as_of: form.as_of });
        setOk('Cash/bank opening balance recorded.');
      }
      setForm({ as_of: form.as_of, account_code: form.account_code });
    } catch (err) { setError(getErrorMessage(err)); }
    setSaving(false);
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <button className="back-link" onClick={() => navigate('/chicken')}>&larr; Chicken Center</button>
          <h1>Opening Balances</h1>
        </div>
      </div>

      <p className="farm-meta" style={{ marginBottom: '1rem', maxWidth: 560 }}>
        Enter what each customer/supplier owed, and your starting cash/bank, when
        you began using this app. Use a positive amount if a customer owes you (or
        you have cash); use a negative amount if you owe a supplier.
      </p>

      <div className="report-view-tabs" style={{ marginBottom: '1.25rem' }}>
        {['Party', 'Cash / Bank'].map(t => (
          <button key={t} className={`report-tab ${tab === t ? 'report-tab-active' : ''}`} onClick={() => { setTab(t); setError(''); setOk(''); }}>{t}</button>
        ))}
      </div>

      {error && <div className="error-msg">{error}</div>}
      {ok && <div className="alert-banner alert-banner-success">{ok}</div>}

      <form onSubmit={submit} className="form-card" style={{ maxWidth: 520 }}>
        <div className="form-group">
          <label>As of date *</label>
          <input type="date" value={form.as_of} max={today} onChange={e => set('as_of', e.target.value)} required />
        </div>

        {tab === 'Party' ? (
          <div className="form-group">
            <label>Party *</label>
            <select value={form.party || ''} onChange={e => set('party', e.target.value)} required>
              <option value="">Select party…</option>
              {parties.map(p => <option key={p.id} value={p.id}>{p.name} ({p.party_type})</option>)}
            </select>
          </div>
        ) : (
          <div className="form-group">
            <label>Account *</label>
            <select value={form.account_code} onChange={e => set('account_code', e.target.value)} required>
              {CASH_ACCS.map(([code, label]) => <option key={code} value={code}>{label}</option>)}
            </select>
          </div>
        )}

        <div className="form-group">
          <label>Amount (₹) *</label>
          <input type="text" inputMode="decimal" value={form.amount || ''} onChange={e => set('amount', e.target.value)} required placeholder={tab === 'Party' ? '+ owes us, − we owe' : 'starting balance'} />
        </div>

        <div className="form-actions">
          <button type="button" className="btn btn-secondary" onClick={() => navigate('/chicken')}>Done</button>
          <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? 'Saving…' : 'Record Opening'}</button>
        </div>
      </form>
    </div>
  );
}
