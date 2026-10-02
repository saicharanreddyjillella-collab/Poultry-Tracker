import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { layerAPI, getErrorMessage } from '../api/client';
import ConfirmModal from '../components/ConfirmModal';

const TABS = [
  { key: 'purchase', label: 'Purchases', fetch: () => layerAPI.purchases() },
  { key: 'feed-batch', label: 'Feed Batches', fetch: () => layerAPI.feedBatches() },
  { key: 'feed-to-flock', label: 'Feed→Flock', fetch: () => layerAPI.feedToFlock() },
  { key: 'application', label: 'Applications', fetch: () => layerAPI.applications() },
  { key: 'egg-sale', label: 'Egg Sales', fetch: () => layerAPI.eggSales() },
  { key: 'collection', label: 'Collections', fetch: () => layerAPI.collections() },
  { key: 'payment', label: 'Payments', fetch: () => layerAPI.payments() },
  { key: 'expense', label: 'Expenses', fetch: () => layerAPI.expenses() },
];

export default function LayerTransactions() {
  const [tabKey, setTabKey] = useState('purchase');
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [confirm, setConfirm] = useState({ open: false });
  const navigate = useNavigate();

  const tab = TABS.find(t => t.key === tabKey);
  const fmt = (n) => n != null ? Number(n).toLocaleString('en-IN', { maximumFractionDigits: 2 }) : '—';

  const load = () => {
    setLoading(true); setError('');
    tab.fetch().then(r => { setRows(r.data); setLoading(false); }).catch(e => { setError(getErrorMessage(e)); setLoading(false); });
  };
  useEffect(load, [tabKey]);

  const reversible = !['feed-batch'].includes(tabKey) || true; // all have vouchers

  const doReverse = (id) => {
    setConfirm({
      open: true, danger: true, title: `Reverse ${tab.label.slice(0, -1)}`,
      message: 'This posts an equal-and-opposite entry — money, stock and flock cost are undone, and the record is kept marked reversed. Continue?',
      onConfirm: async () => {
        setConfirm({ open: false });
        try { await layerAPI.reverse(tabKey, id); load(); }
        catch (e) { setError(getErrorMessage(e)); }
      },
    });
  };

  const cols = {
    purchase: ['Date', 'Vendor', 'Kind', 'Item', 'Qty', 'Rate', 'Amount'],
    'feed-batch': ['Date', 'Feed', 'Output', 'Total', 'Cost/kg'],
    'feed-to-flock': ['Date', 'Flock', 'Feed', 'Qty', '₹/kg', 'Amount'],
    application: ['Date', 'Flock', 'Kind', 'Amount'],
    'egg-sale': ['Date', 'Trader', 'Flock', 'Trays', 'Rate', 'Amount', 'Status'],
    collection: ['Date', 'Trader', 'Amount', 'Mode'],
    payment: ['Date', 'Vendor', 'Amount', 'Mode'],
    expense: ['Date', 'Head', 'Amount', 'Mode'],
  }[tabKey];

  const renderCells = (r) => {
    switch (tabKey) {
      case 'purchase': return <><td>{r.date}</td><td>{r.vendor_name}</td><td>{r.kind}</td><td>{r.item_name || '—'}</td><td>{fmt(r.qty)}</td><td>₹{fmt(r.rate)}</td><td>₹{fmt(r.amount)}</td></>;
      case 'feed-batch': return <><td>{r.date}</td><td>{r.feed_name}</td><td>{fmt(r.output_kg)} kg</td><td>₹{fmt(r.total_cost)}</td><td>₹{fmt(r.cost_per_kg)}</td></>;
      case 'feed-to-flock': return <><td>{r.date}</td><td>{r.flock_name}</td><td>{r.feed_name}</td><td>{fmt(r.qty_kg)} kg</td><td>₹{fmt(r.cost_per_kg)}</td><td>₹{fmt(r.amount)}</td></>;
      case 'application': return <><td>{r.date}</td><td>{r.flock_name}</td><td>{r.kind}</td><td>₹{fmt(r.amount)}</td></>;
      case 'egg-sale': return <><td>{r.date}</td><td>{r.party_name}</td><td>{r.flock_name}</td><td>{fmt(r.trays)}</td><td>₹{fmt(r.rate_per_tray)}</td><td>₹{fmt(r.amount)}</td><td><span className={`wa-badge ${r.status === 'PAID' ? 'wa-sent' : r.status === 'PARTLY' ? 'wa-pending' : 'wa-failed'}`}>{r.status}</span></td></>;
      case 'collection': return <><td>{r.date}</td><td>{r.party_name}</td><td>₹{fmt(r.amount)}</td><td>{r.mode}</td></>;
      case 'payment': return <><td>{r.date}</td><td>{r.party_name}</td><td>₹{fmt(r.amount)}</td><td>{r.mode}</td></>;
      case 'expense': return <><td>{r.date}</td><td>{r.account_code}</td><td>₹{fmt(r.amount)}</td><td>{r.mode}</td></>;
      default: return null;
    }
  };

  const canReverse = (r) => r.is_reversed !== undefined ? !r.is_reversed : true;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <button className="back-link" onClick={() => navigate('/layer')}>&larr; Layer Farm</button>
          <h1>Transactions</h1>
        </div>
        <button className="btn btn-primary" onClick={() => navigate('/layer/new')}>+ New Entry</button>
      </div>

      <div className="report-view-tabs" style={{ marginBottom: '1.25rem', flexWrap: 'wrap' }}>
        {TABS.map(t => (
          <button key={t.key} className={`report-tab ${tabKey === t.key ? 'report-tab-active' : ''}`} onClick={() => setTabKey(t.key)}>{t.label}</button>
        ))}
      </div>

      {error && <div className="error-msg">{error}</div>}

      {loading ? <div className="loading">Loading…</div> : rows.length === 0 ? (
        <p className="farm-meta">No {tab.label.toLowerCase()} yet.</p>
      ) : (
        <div className="table-wrapper">
          <table className="report-table">
            <thead><tr>{cols.map(c => <th key={c}>{c}</th>)}<th></th></tr></thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.id} className={r.is_reversed ? 'row-reversed' : ''}>
                  {renderCells(r)}
                  <td>
                    {canReverse(r)
                      ? <button className="btn-action btn-action-cancel" onClick={() => doReverse(r.id)}>Reverse</button>
                      : <span className="wa-badge wa-failed">reversed</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmModal open={confirm.open} title={confirm.title} message={confirm.message} danger confirmText="Yes, reverse" onConfirm={confirm.onConfirm} onCancel={() => setConfirm({ open: false })} />
    </div>
  );
}
