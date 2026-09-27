import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { chickenAPI, getErrorMessage } from '../api/client';
import ConfirmModal from '../components/ConfirmModal';

const TABS = [
  { key: 'sale', label: 'Sales', fetch: () => chickenAPI.sales() },
  { key: 'purchase', label: 'Purchases', fetch: () => chickenAPI.purchases() },
  { key: 'collection', label: 'Collections', fetch: () => chickenAPI.collections() },
  { key: 'payment', label: 'Payments', fetch: () => chickenAPI.payments() },
  { key: 'expense', label: 'Expenses', fetch: () => chickenAPI.expenses() },
  { key: 'shrinkage', label: 'Shrinkage', fetch: () => chickenAPI.shrinkage() },
];

export default function ChickenTransactions() {
  const [tabKey, setTabKey] = useState('sale');
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

  const doReverse = (id) => {
    setConfirm({
      open: true,
      title: `Reverse ${tab.label.slice(0, -1)}`,
      message: 'This posts an equal-and-opposite entry — money and stock are undone, and the record is kept in history marked as reversed. To correct a value, reverse then enter it again. Continue?',
      danger: true,
      onConfirm: async () => {
        setConfirm({ open: false });
        try {
          await chickenAPI.reverse(tabKey, id);
          load();
        } catch (e) { setError(getErrorMessage(e)); }
      },
    });
  };

  const cols = {
    sale: ['Date', 'Customer', 'Weight', 'Rate', 'Amount', 'WA'],
    purchase: ['Date', 'Supplier', 'Weight', 'Rate', 'Amount'],
    collection: ['Date', 'Customer', 'Amount', 'Mode'],
    payment: ['Date', 'Supplier', 'Amount', 'Mode'],
    expense: ['Date', 'Head', 'Amount', 'Mode'],
    shrinkage: ['Date', 'Item', 'Weight', 'Value'],
  }[tabKey];

  const renderCells = (r) => {
    switch (tabKey) {
      case 'sale': return <><td>{r.date}</td><td>{r.party_name}</td><td>{fmt(r.weight_kg)} kg</td><td>₹{fmt(r.rate_per_kg)}</td><td>₹{fmt(r.amount)}</td><td><span className={`wa-badge wa-${r.whatsapp_status}`}>{r.whatsapp_status}</span></td></>;
      case 'purchase': return <><td>{r.date}</td><td>{r.party_name}</td><td>{fmt(r.weight_kg)} kg</td><td>₹{fmt(r.rate_per_kg)}</td><td>₹{fmt(r.amount)}</td></>;
      case 'collection': return <><td>{r.date}</td><td>{r.party_name}</td><td>₹{fmt(r.amount)}</td><td>{r.mode}</td></>;
      case 'payment': return <><td>{r.date}</td><td>{r.party_name}</td><td>₹{fmt(r.amount)}</td><td>{r.mode}</td></>;
      case 'expense': return <><td>{r.date}</td><td>{r.account_code}</td><td>₹{fmt(r.amount)}</td><td>{r.mode}</td></>;
      case 'shrinkage': return <><td>{r.date}</td><td>{r.item_name}</td><td>{fmt(r.weight_kg)} kg</td><td>₹{fmt(r.value)}</td></>;
      default: return null;
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <button className="back-link" onClick={() => navigate('/chicken')}>&larr; Chicken Center</button>
          <h1>Transactions</h1>
        </div>
        <button className="btn btn-primary" onClick={() => navigate('/chicken/new')}>+ New Entry</button>
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
                    {r.is_reversed
                      ? <span className="wa-badge wa-failed">reversed</span>
                      : <button className="btn-action btn-action-cancel" onClick={() => doReverse(r.id)}>Reverse</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmModal
        open={confirm.open}
        title={confirm.title}
        message={confirm.message}
        danger={confirm.danger}
        confirmText="Yes, reverse"
        onConfirm={confirm.onConfirm}
        onCancel={() => setConfirm({ open: false })}
      />
    </div>
  );
}
