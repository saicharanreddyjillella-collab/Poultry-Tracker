import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { chickenAPI } from '../api/client';

export default function ChickenDaybook() {
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    setLoading(true);
    chickenAPI.daybook({ date }).then(r => { setData(r.data); setLoading(false); }).catch(() => setLoading(false));
  }, [date]);

  const fmt = (n) => Number(n).toLocaleString('en-IN', { maximumFractionDigits: 2 });

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <button className="back-link" onClick={() => navigate('/chicken')}>&larr; Chicken Center</button>
          <h1>Daybook</h1>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <input type="date" value={date} max={new Date().toISOString().slice(0, 10)} onChange={e => setDate(e.target.value)} />
          <button className="btn btn-secondary" onClick={() => window.print()}>Print</button>
        </div>
      </div>

      {loading ? <div className="loading">Loading…</div> : (
        <>
          <div className="stat-card" style={{ maxWidth: 280, marginBottom: '1rem' }}>
            <span className="stat-label">Total activity</span>
            <span className="stat-value">₹{fmt(data?.total)}</span>
          </div>
          {data?.rows?.length ? (
            <div className="table-wrapper">
              <table className="report-table">
                <thead><tr><th>#</th><th>Type</th><th>Party</th><th>Details</th><th>Amount</th></tr></thead>
                <tbody>
                  {data.rows.map(r => (
                    <tr key={r.id}>
                      <td>{r.id}</td>
                      <td><span className="wa-badge wa-disabled">{r.type}</span></td>
                      <td>{r.party || '—'}</td>
                      <td>{r.narration}</td>
                      <td>₹{fmt(r.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <p className="farm-meta">Nothing recorded on this date.</p>}
        </>
      )}
    </div>
  );
}
