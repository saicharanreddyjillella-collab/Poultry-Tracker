import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { layerAPI, accountingAPI, inventoryAPI, getErrorMessage } from '../api/client';

const BIZ = { business: 'layer' };
const TABS = ['Purchase', 'Feed → Flock', 'Apply', 'Egg Sale', 'Collection', 'Payment', 'Expense'];
const MODES = ['CASH', 'UPI', 'BANK'];
const EXPENSE_HEADS = ['LABOUR', 'ELECTRICITY', 'FUEL', 'TRANSPORT', 'RENT', 'MISC'];
const PURCHASE_KINDS = [['RAW', 'Raw Material'], ['PREMIX', 'Premix'], ['MEDICINE', 'Medicine'], ['VACCINE', 'Vaccine'], ['CHICK', 'Chicks']];
const APPLY_KINDS = [['MEDICINE', 'Medicine'], ['VACCINE', 'Vaccine'], ['PREMIX', 'Premix']];

export default function LayerNewEntry() {
  const [tab, setTab] = useState('Purchase');
  const [vendors, setVendors] = useState([]);
  const [traders, setTraders] = useState([]);
  const [items, setItems] = useState([]);
  const [units, setUnits] = useState([]);
  const [flocks, setFlocks] = useState([]);
  const [error, setError] = useState('');
  const [ok, setOk] = useState('');
  const [saving, setSaving] = useState(false);
  const navigate = useNavigate();

  const today = new Date().toISOString().slice(0, 10);
  const [form, setForm] = useState({ date: today, mode: 'CASH', account_code: 'LABOUR', kind: 'RAW', split_across_flocks: true });

  useEffect(() => {
    accountingAPI.parties(BIZ).then(r => {
      setVendors(r.data.filter(p => p.party_type === 'SUPPLIER' || p.party_type === 'BOTH'));
      setTraders(r.data.filter(p => p.party_type === 'CUSTOMER' || p.party_type === 'BOTH'));
    }).catch(() => {});
    inventoryAPI.items(BIZ).then(r => setItems(r.data)).catch(() => {});
    inventoryAPI.units().then(r => setUnits(r.data)).catch(() => {});
    layerAPI.flocks({ status: 'ACTIVE' }).then(r => setFlocks(r.data)).catch(() => {});
  }, []);

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));
  const reset = () => setForm({ date: form.date, mode: 'CASH', account_code: 'LABOUR', kind: form.kind, split_across_flocks: true });

  const feedItems = items.filter(i => i.kind === 'FINISHED');

  const submit = async (e) => {
    e.preventDefault(); setError(''); setOk(''); setSaving(true);
    try {
      let res;
      if (tab === 'Purchase') {
        const body = { vendor: form.vendor, kind: form.kind, date: form.date, qty: form.qty, rate: form.rate, note: form.note || '' };
        if (form.kind === 'CHICK') body.flock = form.flock;
        else { body.item = form.item; body.unit = form.unit; }
        res = await layerAPI.createPurchase(body);
      } else if (tab === 'Feed → Flock') {
        res = await layerAPI.sendFeedToFlock({ flock: form.flock, feed_item: form.feed_item, date: form.date, qty_kg: form.qty_kg, cost_per_kg: form.cost_per_kg || undefined, note: form.note || '' });
      } else if (tab === 'Apply') {
        res = await layerAPI.createApplication({ flock: form.flock, kind: form.apply_kind || 'MEDICINE', date: form.date, amount: form.amount, item: form.item || undefined, qty: form.qty || 0, note: form.note || '' });
      } else if (tab === 'Egg Sale') {
        res = await layerAPI.createEggSale({ party: form.party, flock: form.flock, date: form.date, trays: form.trays, rate_per_tray: form.rate_per_tray, note: form.note || '' });
      } else if (tab === 'Collection') {
        res = await layerAPI.createCollection({ party: form.party, date: form.date, amount: form.amount, mode: form.mode, note: form.note || '' });
      } else if (tab === 'Payment') {
        res = await layerAPI.createPayment({ party: form.party, date: form.date, amount: form.amount, mode: form.mode, note: form.note || '' });
      } else if (tab === 'Expense') {
        res = await layerAPI.createExpense({ date: form.date, account_code: form.account_code, amount: form.amount, mode: form.mode, split_across_flocks: form.split_across_flocks, flock: form.split_across_flocks ? undefined : form.flock, note: form.note || '' });
      }
      let msg = `${tab} saved.`;
      if ((tab === 'Egg Sale' || tab === 'Collection') && res?.data?.whatsapp_status) msg += ` WhatsApp: ${res.data.whatsapp_status}.`;
      setOk(msg); reset();
    } catch (err) { setError(getErrorMessage(err)); }
    setSaving(false);
  };

  const flockSelect = (required = true) => (
    <div className="form-group">
      <label>Flock {required ? '*' : ''}</label>
      <select value={form.flock || ''} onChange={e => set('flock', e.target.value)} required={required}>
        <option value="">Select flock…</option>
        {flocks.map(f => <option key={f.id} value={f.id}>{f.name} ({f.farm_code}, {f.live_birds} birds)</option>)}
      </select>
    </div>
  );

  const itemSelect = (kinds) => (
    <div className="form-group">
      <label>Item</label>
      <select value={form.item || ''} onChange={e => set('item', e.target.value)}>
        <option value="">Select item…</option>
        {items.filter(i => !kinds || kinds.includes(i.kind)).map(it => <option key={it.id} value={it.id}>{it.name} ({it.base_unit_symbol})</option>)}
      </select>
    </div>
  );

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <button className="back-link" onClick={() => navigate('/layer')}>&larr; Layer Farm</button>
          <h1>New Entry</h1>
        </div>
      </div>

      <div className="report-view-tabs" style={{ marginBottom: '1.25rem', flexWrap: 'wrap' }}>
        {TABS.map(t => (
          <button key={t} className={`report-tab ${tab === t ? 'report-tab-active' : ''}`} onClick={() => { setTab(t); setError(''); setOk(''); }}>{t}</button>
        ))}
      </div>

      {error && <div className="error-msg">{error}</div>}
      {ok && <div className="alert-banner alert-banner-success">{ok}</div>}

      <form onSubmit={submit} className="form-card" style={{ maxWidth: 600 }}>
        <div className="form-group"><label>Date *</label><input type="date" value={form.date} max={today} onChange={e => set('date', e.target.value)} required /></div>

        {/* PURCHASE */}
        {tab === 'Purchase' && (
          <>
            <div className="form-group">
              <label>Vendor *</label>
              <select value={form.vendor || ''} onChange={e => set('vendor', e.target.value)} required>
                <option value="">Select vendor…</option>
                {vendors.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>Kind *</label>
              <select value={form.kind} onChange={e => set('kind', e.target.value)}>
                {PURCHASE_KINDS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
              </select>
            </div>
            {form.kind === 'CHICK' ? flockSelect() : (
              <div className="form-row">
                {itemSelect(['RAW'])}
                <div className="form-group">
                  <label>Unit</label>
                  <select value={form.unit || ''} onChange={e => set('unit', e.target.value)}>
                    <option value="">Select…</option>
                    {units.map(u => <option key={u.id} value={u.id}>{u.symbol}</option>)}
                  </select>
                </div>
              </div>
            )}
            <div className="form-row">
              <div className="form-group"><label>{form.kind === 'CHICK' ? 'Birds' : 'Qty'} *</label><input type="text" inputMode="decimal" value={form.qty || ''} onChange={e => set('qty', e.target.value)} required /></div>
              <div className="form-group"><label>Rate *</label><input type="text" inputMode="decimal" value={form.rate || ''} onChange={e => set('rate', e.target.value)} required /></div>
            </div>
          </>
        )}

        {/* FEED -> FLOCK */}
        {tab === 'Feed → Flock' && (
          <>
            {flockSelect()}
            <div className="form-group">
              <label>Feed item *</label>
              <select value={form.feed_item || ''} onChange={e => set('feed_item', e.target.value)} required>
                <option value="">Select feed…</option>
                {feedItems.map(i => <option key={i.id} value={i.id}>{i.name}</option>)}
              </select>
            </div>
            <div className="form-row">
              <div className="form-group"><label>Quantity (kg) *</label><input type="text" inputMode="decimal" value={form.qty_kg || ''} onChange={e => set('qty_kg', e.target.value)} required /></div>
              <div className="form-group"><label>Cost/kg (blank = batch avg)</label><input type="text" inputMode="decimal" value={form.cost_per_kg || ''} onChange={e => set('cost_per_kg', e.target.value)} /></div>
            </div>
          </>
        )}

        {/* APPLY */}
        {tab === 'Apply' && (
          <>
            {flockSelect()}
            <div className="form-group">
              <label>Kind *</label>
              <select value={form.apply_kind || 'MEDICINE'} onChange={e => set('apply_kind', e.target.value)}>
                {APPLY_KINDS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
              </select>
            </div>
            {itemSelect(null)}
            <div className="form-row">
              <div className="form-group"><label>Qty (optional)</label><input type="text" inputMode="decimal" value={form.qty || ''} onChange={e => set('qty', e.target.value)} /></div>
              <div className="form-group"><label>Amount (₹) *</label><input type="text" inputMode="decimal" value={form.amount || ''} onChange={e => set('amount', e.target.value)} required /></div>
            </div>
          </>
        )}

        {/* EGG SALE */}
        {tab === 'Egg Sale' && (
          <>
            <div className="form-group">
              <label>Trader *</label>
              <select value={form.party || ''} onChange={e => set('party', e.target.value)} required>
                <option value="">Select trader…</option>
                {traders.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </div>
            {flockSelect()}
            <div className="form-row">
              <div className="form-group"><label>Trays (30 eggs) *</label><input type="text" inputMode="decimal" value={form.trays || ''} onChange={e => set('trays', e.target.value)} required /></div>
              <div className="form-group"><label>Rate / tray *</label><input type="text" inputMode="decimal" value={form.rate_per_tray || ''} onChange={e => set('rate_per_tray', e.target.value)} required /></div>
            </div>
            {form.trays && form.rate_per_tray && <p className="farm-meta">Amount: <strong>₹{(Number(form.trays) * Number(form.rate_per_tray)).toLocaleString('en-IN')}</strong></p>}
          </>
        )}

        {/* COLLECTION / PAYMENT */}
        {(tab === 'Collection' || tab === 'Payment') && (
          <>
            <div className="form-group">
              <label>{tab === 'Collection' ? 'Trader' : 'Vendor'} *</label>
              <select value={form.party || ''} onChange={e => set('party', e.target.value)} required>
                <option value="">Select…</option>
                {(tab === 'Collection' ? traders : vendors).map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
            <div className="form-group"><label>Amount (₹) *</label><input type="text" inputMode="decimal" value={form.amount || ''} onChange={e => set('amount', e.target.value)} required /></div>
            <div className="form-group"><label>Mode *</label><select value={form.mode} onChange={e => set('mode', e.target.value)}>{MODES.map(m => <option key={m} value={m}>{m}</option>)}</select></div>
          </>
        )}

        {/* EXPENSE */}
        {tab === 'Expense' && (
          <>
            <div className="form-group"><label>Expense head *</label><select value={form.account_code} onChange={e => set('account_code', e.target.value)}>{EXPENSE_HEADS.map(h => <option key={h} value={h}>{h}</option>)}</select></div>
            <div className="form-group"><label>Amount (₹) *</label><input type="text" inputMode="decimal" value={form.amount || ''} onChange={e => set('amount', e.target.value)} required /></div>
            <div className="form-group"><label>Mode *</label><select value={form.mode} onChange={e => set('mode', e.target.value)}>{MODES.map(m => <option key={m} value={m}>{m}</option>)}</select></div>
            <label className="toggle-label"><input type="checkbox" checked={form.split_across_flocks} onChange={e => set('split_across_flocks', e.target.checked)} /> Split across active flocks</label>
            {!form.split_across_flocks && flockSelect()}
          </>
        )}

        <div className="form-group"><label>Note</label><input value={form.note || ''} onChange={e => set('note', e.target.value)} /></div>
        <div className="form-actions">
          <button type="button" className="btn btn-secondary" onClick={() => navigate('/layer')}>Done</button>
          <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? 'Saving…' : `Save ${tab}`}</button>
        </div>
      </form>
    </div>
  );
}
