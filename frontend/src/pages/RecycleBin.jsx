import { useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { trashAPI, getErrorMessage } from '../api/client';
import { useAuth } from '../context/AuthContext';
import ConfirmModal from '../components/ConfirmModal';

// E14 — admin Recycle Bin: everything deleted (farms, flocks, entries, sales,
// medications, feed orders/transfers, documents), one row per delete action.
const plural = (word, n) => {
  const w = word.toLowerCase();
  if (n === 1) return w;
  return w.endsWith('y') ? `${w.slice(0, -1)}ies` : `${w}s`;
};

export default function RecycleBin() {
  const { isAdmin } = useAuth();
  const [rows, setRows] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(null);
  const [pending, setPending] = useState(null);

  const load = () => trashAPI.list()
    .then(res => setRows(res.data))
    .catch(err => { setError(getErrorMessage(err)); setRows([]); });

  useEffect(() => { if (isAdmin) load(); }, [isAdmin]);

  if (!isAdmin) return <Navigate to="/" replace />;

  const restore = async (row) => {
    setPending(null);
    setBusy(row.batch);
    setError('');
    setNotice('');
    try {
      const res = await trashAPI.restore(row.batch);
      setNotice(`Restored ${row.summary}${res.data.restored > 1 ? ` (${res.data.restored} records)` : ''}.`);
      load();
    } catch (err) {
      setError(getErrorMessage(err));
    }
    setBusy(null);
  };

  const fmt = (iso) => new Date(iso).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' });

  return (
    <div className="page">
      <h1>Recycle Bin</h1>
      <p style={{ color: '#666', marginTop: '-0.5rem' }}>
        Deleted records are kept here and can be restored. Bills and records under a billed flock
        can never be deleted.
      </p>
      {notice && <div className="alert-banner alert-banner-success" role="status">{notice}</div>}
      {error && <div className="error-msg" role="alert">{error}</div>}
      {rows === null && <div className="loading">Loading…</div>}
      {rows && rows.length === 0 && <div className="empty-state"><p>Nothing has been deleted.</p></div>}
      {rows && rows.length > 0 && (
        <div className="table-wrapper">
          <table className="report-table">
            <thead>
              <tr><th>Deleted</th><th>What</th><th>Also removed with it</th><th>By</th><th></th></tr>
            </thead>
            <tbody>
              {rows.map(row => (
                <tr key={row.batch}>
                  <td>{fmt(row.deleted_at)}</td>
                  <td>{row.summary}</td>
                  <td>
                    {Object.keys(row.also_removed).length === 0 ? '—'
                      : Object.entries(row.also_removed).map(([k, n]) => `${n} ${plural(k, n)}`).join(', ')}
                  </td>
                  <td>{row.deleted_by || '—'}</td>
                  <td>
                    <button className="btn btn-secondary" disabled={busy !== null} onClick={() => setPending(row)}>
                      {busy === row.batch ? 'Restoring…' : 'Restore'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <ConfirmModal
        open={pending !== null}
        title="Restore?"
        message={pending ? `Restore ${pending.summary}${pending.items_total > 1 ? ` and ${pending.items_total - 1} related record(s)` : ''}?` : ''}
        confirmText="Restore"
        onConfirm={() => restore(pending)}
        onCancel={() => setPending(null)}
      />
    </div>
  );
}
