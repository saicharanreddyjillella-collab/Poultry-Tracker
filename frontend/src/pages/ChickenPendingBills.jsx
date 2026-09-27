import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { chickenAPI } from '../api/client';

const TABS = ['Pending Bills', 'Ageing'];

export default function ChickenPendingBills() {
  const [tab, setTab] = useState('Pending Bills');
  const [bills, setBills] = useState(null);
  const [ageing, setAgeing] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    setLoading(true);
    const call = tab === 'Ageing' ? chickenAPI.ageing() : chickenAPI.pendingBills();
    call.then(r => { tab === 'Ageing' ? setAgeing(r.data) : setBills(r.data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [tab]);

  const fmt = (n) => Number(n).toLocaleString('en-IN', { maximumFractionDigits: 2 });

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <button className="back-link" onClick={() => navigate('/chicken')}>&larr; Chicken Center</button>
          <h1>Receivables</h1>
        </div>
        <button className="btn btn-secondary" onClick={() => window.print()}>Print</button>
      </div>

      <div className="report-view-tabs" style={{ marginBottom: '1.25rem' }}>
        {TABS.map(t => (
          <button key={t} className={`report-tab ${tab === t ? 'report-tab-active' : ''}`} onClick={() => setTab(t)}>{t}</button>
        ))}
      </div>

      {loading ? <div className="loading">Loading…</div> : tab === 'Pending Bills' ? (
        <>
          <div className="stat-card" style={{ maxWidth: 280, marginBottom: '1rem' }}>
            <span className="stat-label">Total Due</span>
            <span className="stat-value text-danger">₹{fmt(bills?.total_due)}</span>
          </div>
          {bills?.rows?.length ? (
            <div className="table-wrapper">
              <table className="report-table">
                <thead><tr><th>Date</th><th>Bill</th><th>Customer</th><th>Amount</th><th>Received</th><th>Due</th><th>Status</th></tr></thead>
                <tbody>
                  {bills.rows.map(b => (
                    <tr key={b.id}>
                      <td>{b.date}</td><td>#{b.id}</td>
                      <td><Link to={`/chicken/parties/${b.party_id}`}>{b.party_name}</Link></td>
                      <td>₹{fmt(b.amount)}</td><td>₹{fmt(b.amount_received)}</td>
                      <td className="text-danger">₹{fmt(b.amount_due)}</td>
                      <td><span className={`wa-badge ${b.status === 'PARTLY' ? 'wa-pending' : 'wa-failed'}`}>{b.status}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <p className="farm-meta">No pending bills — everything is settled. 🎉</p>}
        </>
      ) : (
        <>
          <div className="stat-card" style={{ maxWidth: 280, marginBottom: '1rem' }}>
            <span className="stat-label">Total Outstanding</span>
            <span className="stat-value text-danger">₹{fmt(ageing?.grand_total)}</span>
          </div>
          {ageing?.rows?.length ? (
            <div className="table-wrapper">
              <table className="report-table">
                <thead>
                  <tr><th>Customer</th><th>0-7 days</th><th>8-15</th><th>16-30</th><th>31+ days</th><th>Total</th><th>Oldest</th></tr>
                </thead>
                <tbody>
                  {ageing.rows.map(r => (
                    <tr key={r.party_id}>
                      <td><Link to={`/chicken/parties/${r.party_id}`}>{r.party_name}</Link></td>
                      <td>{Number(r['0-7']) > 0 ? `₹${fmt(r['0-7'])}` : '—'}</td>
                      <td>{Number(r['8-15']) > 0 ? `₹${fmt(r['8-15'])}` : '—'}</td>
                      <td>{Number(r['16-30']) > 0 ? `₹${fmt(r['16-30'])}` : '—'}</td>
                      <td className={Number(r['31+']) > 0 ? 'text-danger' : ''}>{Number(r['31+']) > 0 ? `₹${fmt(r['31+'])}` : '—'}</td>
                      <td><strong>₹{fmt(r.total)}</strong></td>
                      <td>{r.oldest_days}d</td>
                    </tr>
                  ))}
                  <tr className="bill-t-total">
                    <td>Total</td>
                    <td>₹{fmt(ageing.totals['0-7'])}</td>
                    <td>₹{fmt(ageing.totals['8-15'])}</td>
                    <td>₹{fmt(ageing.totals['16-30'])}</td>
                    <td>₹{fmt(ageing.totals['31+'])}</td>
                    <td>₹{fmt(ageing.grand_total)}</td>
                    <td></td>
                  </tr>
                </tbody>
              </table>
            </div>
          ) : <p className="farm-meta">Nothing outstanding. 🎉</p>}
        </>
      )}
    </div>
  );
}
