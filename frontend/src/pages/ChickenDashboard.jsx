import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { accountingAPI, inventoryAPI, chickenAPI, getErrorMessage } from '../api/client';

const BIZ = { business: 'chicken_center' };

export default function ChickenDashboard() {
  const [outstanding, setOutstanding] = useState(null);
  const [stock, setStock] = useState([]);
  const [pnl, setPnl] = useState(null);
  const [recentSales, setRecentSales] = useState([]);
  const [loading, setLoading] = useState(true);

  const monthStart = new Date();
  monthStart.setDate(1);
  const from = monthStart.toISOString().slice(0, 10);
  const to = new Date().toISOString().slice(0, 10);

  useEffect(() => {
    Promise.all([
      accountingAPI.outstanding(BIZ),
      inventoryAPI.stockOnHand(BIZ),
      accountingAPI.pnl({ ...BIZ, from, to }),
      chickenAPI.sales(),
    ]).then(([o, s, p, sales]) => {
      setOutstanding(o.data);
      setStock(s.data.rows);
      setPnl(p.data);
      setRecentSales(sales.data.slice(0, 5));
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const fmt = (n) => n != null ? Number(n).toLocaleString('en-IN', { maximumFractionDigits: 2 }) : '—';

  if (loading) return <div className="loading">Loading…</div>;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Chicken Center</h1>
          <p className="farm-meta">Live-bird trading — money &amp; stock</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <Link to="/chicken/new" className="btn btn-primary">+ New Entry</Link>
          <Link to="/chicken/parties" className="btn btn-secondary">Parties</Link>
          <Link to="/chicken/items" className="btn btn-secondary">Items</Link>
        </div>
      </div>

      {/* Summary cards */}
      <div className="stats-grid stats-grid-wide">
        <div className="stat-card">
          <span className="stat-label">Receivable (owed to us)</span>
          <span className="stat-value text-ok">₹{fmt(outstanding?.total_receivable)}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Payable (we owe)</span>
          <span className="stat-value text-danger">₹{fmt(outstanding?.total_payable)}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">This month profit</span>
          <span className={`stat-value ${pnl?.profit >= 0 ? 'text-ok' : 'text-danger'}`}>₹{fmt(pnl?.profit)}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Stock on hand</span>
          <span className="stat-value">{stock.reduce((a, r) => a + Number(r.stock), 0).toLocaleString('en-IN')} kg</span>
        </div>
      </div>

      {/* This month P&L */}
      <h3 style={{ marginTop: '1.5rem' }}>This Month</h3>
      <div className="stats-grid">
        <div className="stat-card"><span className="stat-label">Income</span><span className="stat-value">₹{fmt(pnl?.income)}</span></div>
        <div className="stat-card"><span className="stat-label">Expenses</span><span className="stat-value">₹{fmt(pnl?.expense)}</span></div>
        <div className="stat-card"><span className="stat-label">Net Profit</span><span className={`stat-value ${pnl?.profit >= 0 ? 'text-ok' : 'text-danger'}`}>₹{fmt(pnl?.profit)}</span></div>
      </div>

      {/* Outstanding parties */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1.5rem' }}>
        <h3>Outstanding</h3>
        <Link to="/chicken/outstanding" className="back-link">View all →</Link>
      </div>
      {outstanding?.rows?.length ? (
        <div className="table-wrapper">
          <table className="report-table">
            <thead><tr><th>Party</th><th>Type</th><th>Balance</th></tr></thead>
            <tbody>
              {outstanding.rows.slice(0, 6).map(r => (
                <tr key={r.party_id}>
                  <td><Link to={`/chicken/parties/${r.party_id}`}>{r.name}</Link></td>
                  <td>{r.party_type}</td>
                  <td className={r.balance >= 0 ? 'text-ok' : 'text-danger'}>
                    {r.balance >= 0 ? '₹' + fmt(r.balance) + ' (owes us)' : '₹' + fmt(-r.balance) + ' (we owe)'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <p className="farm-meta">No outstanding balances.</p>}

      {/* Stock */}
      <h3 style={{ marginTop: '1.5rem' }}>Stock on Hand</h3>
      {stock.length ? (
        <div className="table-wrapper">
          <table className="report-table">
            <thead><tr><th>Item</th><th>Kind</th><th>Stock</th></tr></thead>
            <tbody>
              {stock.map(r => (
                <tr key={r.item_id}>
                  <td>{r.name}</td><td>{r.kind}</td>
                  <td className={Number(r.stock) < 0 ? 'text-danger' : ''}>{fmt(r.stock)} {r.unit}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <p className="farm-meta">No items yet. <Link to="/chicken/items">Add an item →</Link></p>}

      {/* Recent sales */}
      <h3 style={{ marginTop: '1.5rem' }}>Recent Sales</h3>
      {recentSales.length ? (
        <div className="table-wrapper">
          <table className="report-table">
            <thead><tr><th>Date</th><th>Customer</th><th>Weight</th><th>Rate</th><th>Amount</th><th>WhatsApp</th></tr></thead>
            <tbody>
              {recentSales.map(s => (
                <tr key={s.id}>
                  <td>{s.date}</td><td>{s.party_name}</td>
                  <td>{fmt(s.weight_kg)} kg</td><td>₹{fmt(s.rate_per_kg)}</td>
                  <td>₹{fmt(s.amount)}</td>
                  <td><span className={`wa-badge wa-${s.whatsapp_status}`}>{s.whatsapp_status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <p className="farm-meta">No sales yet.</p>}
    </div>
  );
}
