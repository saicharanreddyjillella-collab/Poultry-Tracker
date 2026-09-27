import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { accountingAPI } from '../api/client';

const BIZ = { business: 'chicken_center' };

export default function ChickenLedgers() {
  const [parties, setParties] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState(null); // {kind:'party'|'account', id, name}
  const [ledger, setLedger] = useState(null);
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [loading, setLoading] = useState(true);
  const [ledgerLoading, setLedgerLoading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    Promise.all([accountingAPI.parties(BIZ), accountingAPI.accounts()]).then(([p, a]) => {
      setParties(p.data);
      // Skip party-control accounts (Debtors/Creditors) — those are covered by parties
      setAccounts(a.data.filter(x => !x.is_party_control));
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const fmt = (n) => n != null ? Number(n).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '0.00';

  const loadLedger = (sel) => {
    setSelected(sel); setLedger(null); setLedgerLoading(true);
    const params = {};
    if (from) params.from = from;
    if (to) params.to = to;
    const call = sel.kind === 'party'
      ? accountingAPI.partyStatement(sel.id, params)
      : accountingAPI.accountStatement(sel.id, { ...params, business: 'chicken_center' });
    call.then(r => { setLedger(r.data); setLedgerLoading(false); }).catch(() => setLedgerLoading(false));
  };

  useEffect(() => { if (selected) loadLedger(selected); }, [from, to]);

  const q = search.toLowerCase();
  const matchParties = parties.filter(p => p.name.toLowerCase().includes(q) || (p.phone || '').includes(search));
  const matchAccounts = accounts.filter(a => a.name.toLowerCase().includes(q) || a.code.toLowerCase().includes(q));

  if (loading) return <div className="loading">Loading…</div>;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <button className="back-link" onClick={() => navigate('/chicken')}>&larr; Chicken Center</button>
          <h1>Ledgers</h1>
        </div>
        {selected && <button className="btn btn-secondary" onClick={() => window.print()}>Print</button>}
      </div>

      <input className="search-input" placeholder="Search customer, supplier, or account…" value={search} onChange={e => setSearch(e.target.value)} style={{ marginBottom: '1rem' }} />

      {!selected && (
        <>
          {search && matchParties.length === 0 && matchAccounts.length === 0 && (
            <p className="farm-meta">No matches.</p>
          )}
          {matchParties.length > 0 && (
            <>
              <h3>Parties</h3>
              <div className="ledger-picklist">
                {matchParties.map(p => (
                  <button key={`p${p.id}`} className="ledger-pick" onClick={() => loadLedger({ kind: 'party', id: p.id, name: p.name })}>
                    <span>{p.name}</span>
                    <span className={p.balance >= 0 ? 'text-ok' : 'text-danger'}>
                      {p.balance >= 0 ? `₹${fmt(p.balance)}` : `₹${fmt(-p.balance)} Cr`}
                    </span>
                  </button>
                ))}
              </div>
            </>
          )}
          {matchAccounts.length > 0 && (
            <>
              <h3 style={{ marginTop: '1rem' }}>Accounts</h3>
              <div className="ledger-picklist">
                {matchAccounts.map(a => (
                  <button key={`a${a.id}`} className="ledger-pick" onClick={() => loadLedger({ kind: 'account', id: a.id, name: a.name })}>
                    <span>{a.name} <span className="farm-meta">({a.code})</span></span>
                    <span>₹{fmt(a.balance)}</span>
                  </button>
                ))}
              </div>
            </>
          )}
          {!search && <p className="farm-meta">Type a name to find a ledger.</p>}
        </>
      )}

      {selected && (
        <>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <h2 style={{ margin: 0 }}>{selected.name}</h2>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <label style={{ fontSize: '0.8rem' }}>From <input type="date" value={from} onChange={e => setFrom(e.target.value)} /></label>
              <label style={{ fontSize: '0.8rem' }}>To <input type="date" value={to} onChange={e => setTo(e.target.value)} /></label>
              <button className="btn btn-secondary" onClick={() => { setSelected(null); setLedger(null); setFrom(''); setTo(''); }}>Change</button>
            </div>
          </div>

          {ledgerLoading ? <div className="loading">Loading ledger…</div> : ledger ? (
            <>
              <p className="farm-meta" style={{ marginBottom: '0.75rem' }}>
                Closing balance:{' '}
                <strong className={ledger.closing_balance >= 0 ? 'text-ok' : 'text-danger'}>
                  ₹{fmt(Math.abs(ledger.closing_balance))}{ledger.closing_balance < 0 ? ' Cr' : ''}
                </strong>
              </p>
              {ledger.rows.length ? (
                <div className="table-wrapper">
                  <table className="report-table">
                    <thead><tr><th>Date</th><th>Type</th><th>Details</th><th>Debit</th><th>Credit</th><th>Balance</th></tr></thead>
                    <tbody>
                      {ledger.rows.map((r, i) => (
                        <tr key={i}>
                          <td>{r.date}</td><td>{r.type}</td>
                          <td>{r.party || r.narration}</td>
                          <td>{r.debit > 0 ? `₹${fmt(r.debit)}` : '—'}</td>
                          <td>{r.credit > 0 ? `₹${fmt(r.credit)}` : '—'}</td>
                          <td>₹{fmt(Math.abs(r.balance))}{r.balance < 0 ? ' Cr' : ''}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : <p className="farm-meta">No transactions in this period.</p>}
            </>
          ) : <p className="farm-meta">Could not load ledger.</p>}
        </>
      )}
    </div>
  );
}
