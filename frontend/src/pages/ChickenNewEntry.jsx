import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { accountingAPI, inventoryAPI, chickenAPI, getErrorMessage } from '../api/client';

const BIZ = { business: 'chicken_center' };
const TABS = ['Sale', 'Purchase', 'Collection', 'Payment', 'Expense', 'Shrinkage'];
const MODES = ['CASH', 'UPI', 'BANK'];
const EXPENSE_HEADS = ['FUEL', 'WOOD', 'COVERS', 'FOOD', 'STATIONERY', 'TRANSPORT', 'LABOUR', 'ICE', 'RENT', 'ELECTRICITY', 'MISC'];

export default function ChickenNewEntry() {
  const [tab, setTab] = useState('Sale');
  const [parties, setParties] = useState([]);
  const [items, setItems] = useState([]);
  const [error, setError] = useState('');
  const [ok, setOk] = useState('');
  const [saving, setSaving] = useState(false);
  const navigate = useNavigate();

  const today = new Date().toISOString().slice(0, 10);
  const [form, setForm] = useState({ date: today, mode: 'CASH', account_code: 'FUEL' });
  const [pendingBills, setPendingBills] = useState(null);
  const [multiMode, setMultiMode] = useState(false);
  const [saleLines, setSaleLines] = useState([{ item: '', weight_kg: '', rate_per_kg: '' }]);

  useEffect(() => {
    accountingAPI.parties(BIZ).then(r => setParties(r.data)).catch(() => {});
    inventoryAPI.items(BIZ).then(r => setItems(r.data)).catch(() => {});
  }, []);

  // Load pending bills for the chosen customer on the Collection tab.
  useEffect(() => {
    if (tab === 'Collection' && form.party) {
      chickenAPI.pendingBills({ party: form.party }).then(r => setPendingBills(r.data)).catch(() => setPendingBills(null));
    } else {
      setPendingBills(null);
    }
  }, [tab, form.party]);

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));
  const reset = () => setForm({ date: today, mode: 'CASH', account_code: 'FUEL' });

  const customers = parties.filter(p => p.party_type === 'CUSTOMER' || p.party_type === 'BOTH');
  const suppliers = parties.filter(p => p.party_type === 'SUPPLIER' || p.party_type === 'BOTH');

  const amountPreview = form.weight_kg && form.rate_per_kg
    ? (Number(form.weight_kg) * Number(form.rate_per_kg)).toLocaleString('en-IN', { maximumFractionDigits: 2 })
    : null;

  const submit = async (e) => {
    e.preventDefault();
    setError(''); setOk(''); setSaving(true);
    try {
      let res;
      if (tab === 'Sale' && multiMode) {
        const lines = saleLines.filter(l => l.item && l.weight_kg && l.rate_per_kg);
        if (!lines.length) { setError('Add at least one complete line.'); setSaving(false); return; }
        res = await chickenAPI.createSale({ party: form.party, date: form.date, note: form.note || '', lines });
      }
      else if (tab === 'Sale') res = await chickenAPI.createSale({ party: form.party, item: form.item, date: form.date, weight_kg: form.weight_kg, rate_per_kg: form.rate_per_kg, note: form.note || '' });
      else if (tab === 'Purchase') res = await chickenAPI.createPurchase({ party: form.party, item: form.item, date: form.date, weight_kg: form.weight_kg, rate_per_kg: form.rate_per_kg, note: form.note || '' });
      else if (tab === 'Collection') res = await chickenAPI.createCollection({ party: form.party, date: form.date, amount: form.amount, mode: form.mode, note: form.note || '' });
      else if (tab === 'Payment') res = await chickenAPI.createPayment({ party: form.party, date: form.date, amount: form.amount, mode: form.mode, note: form.note || '' });
      else if (tab === 'Expense') res = await chickenAPI.createExpense({ date: form.date, account_code: form.account_code, amount: form.amount, mode: form.mode, note: form.note || '' });
      else if (tab === 'Shrinkage') res = await chickenAPI.createShrinkage({ item: form.item, date: form.date, weight_kg: form.weight_kg, value: form.value || 0, reason: form.note || '' });

      let msg = `${tab} saved.`;
      if ((tab === 'Sale' || tab === 'Collection') && res?.data?.whatsapp_status) {
        msg += ` WhatsApp: ${res.data.whatsapp_status}.`;
      }
      setOk(msg);
      reset();
      setSaleLines([{ item: '', weight_kg: '', rate_per_kg: '' }]);
    } catch (err) {
      setError(getErrorMessage(err));
    }
    setSaving(false);
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <button className="back-link" onClick={() => navigate('/chicken')}>&larr; Chicken Center</button>
          <h1>New Entry</h1>
        </div>
      </div>

      <div className="report-view-tabs" style={{ marginBottom: '1.25rem', flexWrap: 'wrap' }}>
        {TABS.map(t => (
          <button key={t} className={`report-tab ${tab === t ? 'report-tab-active' : ''}`}
            onClick={() => { setTab(t); setError(''); setOk(''); }}>{t}</button>
        ))}
      </div>

      {error && <div className="error-msg">{error}</div>}
      {ok && <div className="alert-banner alert-banner-success">{ok}</div>}

      <form onSubmit={submit} className="form-card" style={{ maxWidth: 560 }}>
        <div className="form-group">
          <label>Date *</label>
          <input type="date" value={form.date} max={today} onChange={e => set('date', e.target.value)} required />
        </div>

        {/* Party (sale/purchase/collection/payment) */}
        {['Sale', 'Collection'].includes(tab) && (
          <div className="form-group">
            <label>Customer *</label>
            <select value={form.party || ''} onChange={e => set('party', e.target.value)} required>
              <option value="">Select customer…</option>
              {customers.map(p => <option key={p.id} value={p.id}>{p.name}{p.phone ? ` (${p.phone})` : ''}</option>)}
            </select>
          </div>
        )}
        {['Purchase', 'Payment'].includes(tab) && (
          <div className="form-group">
            <label>Supplier *</label>
            <select value={form.party || ''} onChange={e => set('party', e.target.value)} required>
              <option value="">Select supplier…</option>
              {suppliers.map(p => <option key={p.id} value={p.id}>{p.name}{p.phone ? ` (${p.phone})` : ''}</option>)}
            </select>
          </div>
        )}

        {/* Multi-item toggle (Sale only) */}
        {tab === 'Sale' && (
          <label className="toggle-label" style={{ marginBottom: '0.5rem' }}>
            <input type="checkbox" checked={multiMode} onChange={e => setMultiMode(e.target.checked)} /> Multiple items on one bill
          </label>
        )}

        {/* Multi-item line editor */}
        {tab === 'Sale' && multiMode && (
          <div className="pending-panel">
            {saleLines.map((ln, i) => (
              <div className="form-row" key={i} style={{ alignItems: 'flex-end' }}>
                <div className="form-group" style={{ flex: 2 }}>
                  <label>Item</label>
                  <select value={ln.item} onChange={e => { const c = [...saleLines]; c[i] = { ...c[i], item: e.target.value }; setSaleLines(c); }}>
                    <option value="">Select…</option>
                    {items.map(it => <option key={it.id} value={it.id}>{it.name}</option>)}
                  </select>
                </div>
                <div className="form-group"><label>kg</label><input type="text" inputMode="decimal" value={ln.weight_kg} onChange={e => { const c = [...saleLines]; c[i] = { ...c[i], weight_kg: e.target.value }; setSaleLines(c); }} /></div>
                <div className="form-group"><label>₹/kg</label><input type="text" inputMode="decimal" value={ln.rate_per_kg} onChange={e => { const c = [...saleLines]; c[i] = { ...c[i], rate_per_kg: e.target.value }; setSaleLines(c); }} /></div>
                <div className="form-group" style={{ flex: '0 0 auto' }}>
                  <label>&nbsp;</label>
                  <button type="button" className="btn-action btn-action-cancel" onClick={() => setSaleLines(saleLines.length > 1 ? saleLines.filter((_, j) => j !== i) : saleLines)}>✕</button>
                </div>
              </div>
            ))}
            <button type="button" className="btn btn-secondary" onClick={() => setSaleLines([...saleLines, { item: '', weight_kg: '', rate_per_kg: '' }])} style={{ marginTop: '0.4rem' }}>+ Add line</button>
            <p className="farm-meta" style={{ marginTop: '0.5rem' }}>
              Bill total: <strong>₹{saleLines.reduce((t, l) => t + (Number(l.weight_kg || 0) * Number(l.rate_per_kg || 0)), 0).toLocaleString('en-IN')}</strong>
            </p>
          </div>
        )}

        {/* Item (single-item sale / purchase / shrinkage) */}
        {(['Purchase', 'Shrinkage'].includes(tab) || (tab === 'Sale' && !multiMode)) && (
          <div className="form-group">
            <label>Item *</label>
            <select value={form.item || ''} onChange={e => set('item', e.target.value)} required>
              <option value="">Select item…</option>
              {items.map(it => <option key={it.id} value={it.id}>{it.name} ({it.base_unit_symbol})</option>)}
            </select>
          </div>
        )}

        {/* Weight + rate (single-item sale / purchase) */}
        {(tab === 'Purchase' || (tab === 'Sale' && !multiMode)) && (
          <div className="form-row">
            <div className="form-group">
              <label>Weight (kg) *</label>
              <input type="text" inputMode="decimal" value={form.weight_kg || ''} onChange={e => set('weight_kg', e.target.value)} required />
            </div>
            <div className="form-group">
              <label>Rate (₹/kg) *</label>
              <input type="text" inputMode="decimal" value={form.rate_per_kg || ''} onChange={e => set('rate_per_kg', e.target.value)} required />
            </div>
          </div>
        )}
        {(tab === 'Purchase' || (tab === 'Sale' && !multiMode)) && amountPreview && (
          <p className="farm-meta">Amount: <strong>₹{amountPreview}</strong></p>
        )}

        {/* Shrinkage weight + value */}
        {tab === 'Shrinkage' && (
          <div className="form-row">
            <div className="form-group">
              <label>Weight lost (kg) *</label>
              <input type="text" inputMode="decimal" value={form.weight_kg || ''} onChange={e => set('weight_kg', e.target.value)} required />
            </div>
            <div className="form-group">
              <label>Value (₹, optional)</label>
              <input type="text" inputMode="decimal" value={form.value || ''} onChange={e => set('value', e.target.value)} placeholder="Loss to book" />
            </div>
          </div>
        )}

        {/* Amount (collection/payment/expense) */}
        {['Collection', 'Payment', 'Expense'].includes(tab) && (
          <div className="form-group">
            <label>Amount (₹) *</label>
            <input type="text" inputMode="decimal" value={form.amount || ''} onChange={e => set('amount', e.target.value)} required />
          </div>
        )}

        {/* Pending bills + allocation preview (Collection) */}
        {tab === 'Collection' && form.party && pendingBills && (
          <div className="pending-panel">
            <div className="pending-head">
              <strong>Pending bills</strong>
              <span>Total due: ₹{Number(pendingBills.total_due).toLocaleString('en-IN')}</span>
            </div>
            {pendingBills.rows.length === 0 ? (
              <p className="farm-meta">No pending bills — this receipt will be held as advance.</p>
            ) : (
              <table className="bill-t">
                <thead><tr><th>Date</th><th>Bill</th><th>Due</th><th>This receipt</th></tr></thead>
                <tbody>
                  {(() => {
                    let remaining = Number(form.amount || 0);
                    return pendingBills.rows.map(b => {
                      const due = Number(b.amount_due);
                      const applied = Math.max(0, Math.min(due, remaining));
                      remaining -= applied;
                      return (
                        <tr key={b.id}>
                          <td>{b.date}</td>
                          <td>#{b.id} (₹{Number(b.amount).toLocaleString('en-IN')})</td>
                          <td>₹{due.toLocaleString('en-IN')}</td>
                          <td className={applied > 0 ? 'text-ok' : ''}>
                            {applied > 0 ? `₹${applied.toLocaleString('en-IN')}${applied >= due ? ' ✓ paid' : ' (partial)'}` : '—'}
                          </td>
                        </tr>
                      );
                    });
                  })()}
                </tbody>
              </table>
            )}
            {Number(form.amount || 0) > Number(pendingBills.total_due) && (
              <p className="farm-meta">Advance held: ₹{(Number(form.amount) - Number(pendingBills.total_due)).toLocaleString('en-IN')}</p>
            )}
          </div>
        )}

        {/* Expense head */}
        {tab === 'Expense' && (
          <div className="form-group">
            <label>Expense head *</label>
            <select value={form.account_code} onChange={e => set('account_code', e.target.value)} required>
              {EXPENSE_HEADS.map(h => <option key={h} value={h}>{h}</option>)}
            </select>
          </div>
        )}

        {/* Mode (collection/payment/expense) */}
        {['Collection', 'Payment', 'Expense'].includes(tab) && (
          <div className="form-group">
            <label>Mode *</label>
            <select value={form.mode} onChange={e => set('mode', e.target.value)} required>
              {MODES.map(m => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
        )}

        <div className="form-group">
          <label>{tab === 'Shrinkage' ? 'Reason' : 'Note'}</label>
          <input value={form.note || ''} onChange={e => set('note', e.target.value)} />
        </div>

        <div className="form-actions">
          <button type="button" className="btn btn-secondary" onClick={() => navigate('/chicken')}>Done</button>
          <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? 'Saving…' : `Save ${tab}`}</button>
        </div>
      </form>
    </div>
  );
}
