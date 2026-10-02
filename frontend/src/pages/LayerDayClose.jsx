import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { accountingAPI, getErrorMessage } from '../api/client';
import { useAuth } from '../context/AuthContext';
import ConfirmModal from '../components/ConfirmModal';

const BIZ = 'layer';

export default function LayerDayClose() {
  const [closedThrough, setClosedThrough] = useState(null);
  const [pickDate, setPickDate] = useState(new Date().toISOString().slice(0, 10));
  const [error, setError] = useState('');
  const [ok, setOk] = useState('');
  const [loading, setLoading] = useState(true);
  const [confirm, setConfirm] = useState({ open: false });
  const { isAdmin } = useAuth();
  const navigate = useNavigate();

  const load = () => {
    accountingAPI.bookLock({ business: BIZ }).then(r => { setClosedThrough(r.data.closed_through); setLoading(false); }).catch(() => setLoading(false));
  };
  useEffect(load, []);

  const apply = async (value, msg) => {
    setError(''); setOk('');
    try {
      const r = await accountingAPI.setBookLock({ business: BIZ, closed_through: value });
      setClosedThrough(r.data.closed_through); setOk(msg);
    } catch (e) { setError(getErrorMessage(e)); }
  };

  const doClose = () => setConfirm({ open: true, danger: true, title: 'Close books',
    message: `Lock all transactions dated on or before ${pickDate}. No one can add or reverse anything on those days until re-opened. Continue?`,
    onConfirm: () => { setConfirm({ open: false }); apply(pickDate, `Books closed through ${pickDate}.`); } });

  const doReopen = () => setConfirm({ open: true, danger: true, title: 'Re-open books',
    message: 'Removes the lock so past days can be edited again. Use only for a genuine correction. Continue?',
    onConfirm: () => { setConfirm({ open: false }); apply(null, 'Books re-opened.'); } });

  if (loading) return <div className="loading">Loading…</div>;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <button className="back-link" onClick={() => navigate('/layer')}>&larr; Layer Farm</button>
          <h1>Day Close</h1>
        </div>
      </div>

      {error && <div className="error-msg">{error}</div>}
      {ok && <div className="alert-banner alert-banner-success">{ok}</div>}

      <div className="form-card" style={{ maxWidth: 520 }}>
        <p className="farm-meta" style={{ marginBottom: '1rem' }}>Closing the books locks all transactions up to a chosen date so past days can't be changed. Only an admin can close or re-open.</p>
        <div className="stat-card" style={{ marginBottom: '1rem' }}>
          <span className="stat-label">Currently closed through</span>
          <span className="stat-value">{closedThrough || 'Open (nothing locked)'}</span>
        </div>
        {isAdmin ? (
          <>
            <div className="form-group"><label>Close all transactions on or before</label><input type="date" value={pickDate} max={new Date().toISOString().slice(0, 10)} onChange={e => setPickDate(e.target.value)} /></div>
            <div className="form-actions">
              {closedThrough && <button className="btn btn-secondary" onClick={doReopen}>Re-open</button>}
              <button className="btn btn-primary" onClick={doClose}>Close Books</button>
            </div>
          </>
        ) : <p className="farm-meta">Only an admin can change the day-close.</p>}
      </div>

      <ConfirmModal open={confirm.open} title={confirm.title} message={confirm.message} danger confirmText="Yes" onConfirm={confirm.onConfirm} onCancel={() => setConfirm({ open: false })} />
    </div>
  );
}
