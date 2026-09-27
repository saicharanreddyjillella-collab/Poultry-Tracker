import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { accountingAPI } from '../api/client';

const BIZ = { business: 'chicken_center' };

export default function ChickenOutstanding() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    accountingAPI.outstanding(BIZ).then(r => { setData(r.data); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  const fmt = (n) => Number(n).toLocaleString('en-IN', { maximumFractionDigits: 2 });

  if (loading) return <div className="loading">Loading…</div>;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <button className="back-link" onClick={() => navigate('/chicken')}>&larr; Chicken Center</button>
          <h1>Outstanding</h1>
        </div>
      </div>

      <div className="stats-grid">
        <div className="stat-card"><span className="stat-label">Total Receivable</span><span className="stat-value text-ok">₹{fmt(data?.total_receivable)}</span></div>
        <div className="stat-card"><span className="stat-label">Total Payable</span><span className="stat-value text-danger">₹{fmt(data?.total_payable)}</span></div>
      </div>

      {data?.rows?.length ? (
        <div className="table-wrapper" style={{ marginTop: '1rem' }}>
          <table className="report-table">
            <thead><tr><th>Party</th><th>Type</th><th>Phone</th><th>Balance</th></tr></thead>
            <tbody>
              {data.rows.map(r => (
                <tr key={r.party_id}>
                  <td><Link to={`/chicken/parties/${r.party_id}`}>{r.name}</Link></td>
                  <td>{r.party_type}</td>
                  <td>{r.phone || '—'}</td>
                  <td className={r.balance >= 0 ? 'text-ok' : 'text-danger'}>
                    {r.balance >= 0 ? `₹${fmt(r.balance)} (owes us)` : `₹${fmt(-r.balance)} (we owe)`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <p className="farm-meta">Nothing outstanding — all settled.</p>}
    </div>
  );
}
