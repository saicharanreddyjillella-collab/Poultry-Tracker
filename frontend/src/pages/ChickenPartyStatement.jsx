import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { accountingAPI } from '../api/client';

export default function ChickenPartyStatement() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    accountingAPI.partyStatement(id).then(r => { setData(r.data); setLoading(false); }).catch(() => setLoading(false));
  }, [id]);

  const fmt = (n) => n ? Number(n).toLocaleString('en-IN', { maximumFractionDigits: 2 }) : '0';

  if (loading) return <div className="loading">Loading…</div>;
  if (!data) return <div className="empty-state"><p>Statement not found.</p></div>;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <button className="back-link" onClick={() => navigate('/chicken/parties')}>&larr; Parties</button>
          <h1>{data.party}</h1>
          <p className="farm-meta">
            Closing balance:{' '}
            <strong className={data.closing_balance >= 0 ? 'text-ok' : 'text-danger'}>
              {data.closing_balance >= 0 ? `₹${fmt(data.closing_balance)} (owes us)` : `₹${fmt(-data.closing_balance)} (we owe)`}
            </strong>
          </p>
        </div>
      </div>

      {data.rows.length ? (
        <div className="table-wrapper">
          <table className="report-table">
            <thead><tr><th>Date</th><th>Type</th><th>Details</th><th>Debit</th><th>Credit</th><th>Balance</th></tr></thead>
            <tbody>
              {data.rows.map((r, i) => (
                <tr key={i}>
                  <td>{r.date}</td>
                  <td>{r.type}</td>
                  <td>{r.narration}</td>
                  <td>{r.debit > 0 ? `₹${fmt(r.debit)}` : '—'}</td>
                  <td>{r.credit > 0 ? `₹${fmt(r.credit)}` : '—'}</td>
                  <td className={r.balance >= 0 ? '' : 'text-danger'}>₹{fmt(Math.abs(r.balance))}{r.balance < 0 ? ' Cr' : ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <p className="farm-meta">No transactions yet.</p>}
    </div>
  );
}
