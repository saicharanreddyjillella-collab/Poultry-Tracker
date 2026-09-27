import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { chickenAPI } from '../api/client';

function monthStartISO() { const d = new Date(); d.setDate(1); return d.toISOString().slice(0, 10); }
const todayISO = () => new Date().toISOString().slice(0, 10);

export default function ChickenSalesSummary() {
  const [tab, setTab] = useState('By Customer');
  const [from, setFrom] = useState(monthStartISO());
  const [to, setTo] = useState(todayISO());
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    setLoading(true);
    chickenAPI.salesSummary({ from, to }).then(r => { setData(r.data); setLoading(false); }).catch(() => setLoading(false));
  }, [from, to]);

  const fmt = (n) => Number(n).toLocaleString('en-IN', { maximumFractionDigits: 2 });

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <button className="back-link" onClick={() => navigate('/chicken')}>&larr; Chicken Center</button>
          <h1>Sales Summary</h1>
        </div>
        <button className="btn btn-secondary" onClick={() => window.print()}>Print</button>
      </div>

      <div className="report-filters-bar">
        <div className="report-view-tabs">
          {['By Customer', 'By Item'].map(t => (
            <button key={t} className={`report-tab ${tab === t ? 'report-tab-active' : ''}`} onClick={() => setTab(t)}>{t}</button>
          ))}
        </div>
        <div className="report-filter-controls">
          <label style={{ fontSize: '0.8rem' }}>From <input type="date" value={from} max={to} onChange={e => setFrom(e.target.value)} /></label>
          <label style={{ fontSize: '0.8rem' }}>To <input type="date" value={to} max={todayISO()} onChange={e => setTo(e.target.value)} /></label>
        </div>
      </div>

      {loading ? <div className="loading">Loading…</div> : (
        <>
          <div className="stats-grid" style={{ marginBottom: '1rem' }}>
            <div className="stat-card"><span className="stat-label">Total Sales</span><span className="stat-value">₹{fmt(data?.grand_amount)}</span></div>
            <div className="stat-card"><span className="stat-label">Total Weight</span><span className="stat-value">{fmt(data?.grand_weight)} kg</span></div>
          </div>

          {(tab === 'By Customer' ? data?.by_customer : data?.by_item)?.length ? (
            <div className="table-wrapper">
              <table className="report-table">
                <thead><tr><th>{tab === 'By Customer' ? 'Customer' : 'Item'}</th><th>Bills</th><th>Weight</th><th>Amount</th></tr></thead>
                <tbody>
                  {(tab === 'By Customer' ? data.by_customer : data.by_item).map((r, i) => (
                    <tr key={i}>
                      <td>{r.name}</td>
                      <td>{r.bills}</td>
                      <td>{fmt(r.weight)} kg</td>
                      <td>₹{fmt(r.amount)}</td>
                    </tr>
                  ))}
                  <tr className="bill-t-total">
                    <td>Total</td>
                    <td></td>
                    <td>{fmt(data.grand_weight)} kg</td>
                    <td>₹{fmt(data.grand_amount)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          ) : <p className="farm-meta">No sales in this period.</p>}
        </>
      )}
    </div>
  );
}
