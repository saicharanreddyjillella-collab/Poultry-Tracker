import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { accountingAPI } from '../api/client';

const BIZ = 'chicken_center';
const TABS = ['P&L', 'Cash Book', 'Trial Balance'];

function monthStartISO() {
  const d = new Date(); d.setDate(1); return d.toISOString().slice(0, 10);
}
const todayISO = () => new Date().toISOString().slice(0, 10);

export default function ChickenReports() {
  const [tab, setTab] = useState('P&L');
  const [from, setFrom] = useState(monthStartISO());
  const [to, setTo] = useState(todayISO());
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const fmt = (n) => n != null ? Number(n).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '0.00';

  const load = () => {
    setLoading(true);
    const p = { business: BIZ, from, to };
    const call =
      tab === 'P&L' ? accountingAPI.pnl({ ...p, detailed: 1 }) :
      tab === 'Cash Book' ? accountingAPI.cashBook(p) :
      accountingAPI.trialBalance({ business: BIZ, upto: to });
    call.then(r => { setData(r.data); setLoading(false); }).catch(() => { setData(null); setLoading(false); });
  };
  useEffect(load, [tab, from, to]);

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <button className="back-link" onClick={() => navigate('/chicken')}>&larr; Chicken Center</button>
          <h1>Reports</h1>
        </div>
        <button className="btn btn-secondary" onClick={() => window.print()}>Print</button>
      </div>

      <div className="report-filters-bar">
        <div className="report-view-tabs">
          {TABS.map(t => (
            <button key={t} className={`report-tab ${tab === t ? 'report-tab-active' : ''}`} onClick={() => setTab(t)}>{t}</button>
          ))}
        </div>
        <div className="report-filter-controls">
          <label style={{ fontSize: '0.8rem' }}>From <input type="date" value={from} max={to} onChange={e => setFrom(e.target.value)} /></label>
          <label style={{ fontSize: '0.8rem' }}>To <input type="date" value={to} max={todayISO()} onChange={e => setTo(e.target.value)} /></label>
        </div>
      </div>

      {loading ? <div className="loading">Loading…</div> : !data ? <div className="empty-state"><p>No data.</p></div> : (
        <>
          {tab === 'P&L' && (
            <div className="bill-a4" style={{ maxWidth: 640 }}>
              <h3 className="bill-section-title">Income</h3>
              <table className="bill-t">
                <tbody>
                  {data.income_lines?.length ? data.income_lines.map((r, i) => (
                    <tr key={i}><td>{r.name}</td><td>₹{fmt(r.amount)}</td></tr>
                  )) : <tr><td>No income</td><td>₹0.00</td></tr>}
                  <tr className="bill-t-total"><td>Total Income</td><td>₹{fmt(data.income)}</td></tr>
                </tbody>
              </table>
              <h3 className="bill-section-title" style={{ marginTop: '1rem' }}>Expenses</h3>
              <table className="bill-t">
                <tbody>
                  {data.expense_lines?.length ? data.expense_lines.map((r, i) => (
                    <tr key={i}><td>{r.name}</td><td>₹{fmt(r.amount)}</td></tr>
                  )) : <tr><td>No expenses</td><td>₹0.00</td></tr>}
                  <tr className="bill-t-total"><td>Total Expenses</td><td>₹{fmt(data.expense)}</td></tr>
                </tbody>
              </table>
              <div className="bill-final-compact" style={{ marginTop: '1rem' }}>
                <div className="bill-final-line bill-final-net">
                  <span>Net Profit</span>
                  <span className={data.profit >= 0 ? '' : 'text-danger'}>₹{fmt(data.profit)}</span>
                </div>
              </div>
            </div>
          )}

          {tab === 'Cash Book' && (
            <>
              {Object.entries(data).map(([code, cb]) => (
                <div key={code} style={{ marginBottom: '1.5rem' }}>
                  <h3>{cb.account}</h3>
                  <div className="stats-grid">
                    <div className="stat-card"><span className="stat-label">Opening</span><span className="stat-value">₹{fmt(cb.opening)}</span></div>
                    <div className="stat-card"><span className="stat-label">Received</span><span className="stat-value text-ok">₹{fmt(cb.receipts)}</span></div>
                    <div className="stat-card"><span className="stat-label">Paid</span><span className="stat-value text-danger">₹{fmt(cb.payments)}</span></div>
                    <div className="stat-card"><span className="stat-label">Closing</span><span className="stat-value">₹{fmt(cb.closing)}</span></div>
                  </div>
                  {cb.rows.length > 0 && (
                    <div className="table-wrapper" style={{ marginTop: '0.5rem' }}>
                      <table className="report-table">
                        <thead><tr><th>Date</th><th>Type</th><th>Details</th><th>In</th><th>Out</th><th>Balance</th></tr></thead>
                        <tbody>
                          {cb.rows.map((r, i) => (
                            <tr key={i}>
                              <td>{r.date}</td><td>{r.type}</td>
                              <td>{r.party || r.narration}</td>
                              <td className="text-ok">{r.in > 0 ? `₹${fmt(r.in)}` : '—'}</td>
                              <td className="text-danger">{r.out > 0 ? `₹${fmt(r.out)}` : '—'}</td>
                              <td>₹{fmt(r.balance)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              ))}
            </>
          )}

          {tab === 'Trial Balance' && (
            <div className="table-wrapper">
              <table className="report-table">
                <thead><tr><th>Code</th><th>Account</th><th>Type</th><th>Debit</th><th>Credit</th></tr></thead>
                <tbody>
                  {data.rows?.map((r, i) => (
                    <tr key={i}>
                      <td>{r.code}</td><td>{r.name}</td><td>{r.type}</td>
                      <td>{r.debit > 0 ? `₹${fmt(r.debit)}` : '—'}</td>
                      <td>{r.credit > 0 ? `₹${fmt(r.credit)}` : '—'}</td>
                    </tr>
                  ))}
                  <tr className="bill-t-total">
                    <td colSpan={3}>Total</td>
                    <td>₹{fmt(data.total_debit)}</td>
                    <td>₹{fmt(data.total_credit)}</td>
                  </tr>
                </tbody>
              </table>
              <p className="farm-meta" style={{ marginTop: '0.5rem' }}>
                {data.balanced ? '✓ Balanced' : '⚠️ Not balanced — check entries'}
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
