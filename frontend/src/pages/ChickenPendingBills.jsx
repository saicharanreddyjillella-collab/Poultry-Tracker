import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { chickenAPI } from '../api/client';

export default function ChickenPendingBills() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    chickenAPI.pendingBills().then(r => { setData(r.data); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  const fmt = (n) => Number(n).toLocaleString('en-IN', { maximumFractionDigits: 2 });

  if (loading) return <div className="loading">Loading…</div>;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <button className="back-link" onClick={() => navigate('/chicken')}>&larr; Chicken Center</button>
          <h1>Pending Bills</h1>
        </div>
      </div>

      <div className="stat-card" style={{ maxWidth: 280, marginBottom: '1rem' }}>
        <span className="stat-label">Total Due</span>
        <span className="stat-value text-danger">₹{fmt(data?.total_due)}</span>
      </div>

      {data?.rows?.length ? (
        <div className="table-wrapper">
          <table className="report-table">
            <thead><tr><th>Date</th><th>Bill</th><th>Customer</th><th>Amount</th><th>Received</th><th>Due</th><th>Status</th></tr></thead>
            <tbody>
              {data.rows.map(b => (
                <tr key={b.id}>
                  <td>{b.date}</td>
                  <td>#{b.id}</td>
                  <td><Link to={`/chicken/parties/${b.party_id}`}>{b.party_name}</Link></td>
                  <td>₹{fmt(b.amount)}</td>
                  <td>₹{fmt(b.amount_received)}</td>
                  <td className="text-danger">₹{fmt(b.amount_due)}</td>
                  <td><span className={`wa-badge ${b.status === 'PARTLY' ? 'wa-pending' : 'wa-failed'}`}>{b.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <p className="farm-meta">No pending bills — everything is settled. 🎉</p>}
    </div>
  );
}
