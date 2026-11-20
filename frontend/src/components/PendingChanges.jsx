import { useState } from 'react';
import { Link } from 'react-router-dom';
import { changeRequestAPI, getErrorMessage } from '../api/client';
import { useAuth } from '../context/AuthContext';
import useFeedTypes from '../utils/useFeedTypes';
import { Chip } from './ui';
import { fmtDate } from '../utils/format';

const LABELS = {
  mortality_count: 'Mortality', cull_count: 'Culls', feed_bags: 'Feed bags',
  water_consumed_liters: 'Water (L)', avg_body_weight_grams: 'Weight (g)',
  bird_count: 'Birds', total_weight_kg: 'Weight (kg)', rate_per_kg: 'Rate ₹/kg', trader_name: 'Trader',
  name: 'Medicine', dose: 'Dose', cost: 'Cost ₹', date: 'Date', notes: 'Notes', reason: 'Reason',
};
const SKIP = new Set(['flock', 'id', 'entered_by', 'edited_by', 'is_deleted', 'deleted_at', 'deleted_by']);

/** Equal values written differently (0.00 vs 0, "5" vs 5) are not a change. */
const show = (v, code) => (v && typeof v === 'object' ? (Object.entries(v).map(([k, n]) => `${code(k)} ${n}`).join(', ') || '0') : v);
const same = (a, b) => {
  if ((a && typeof a === 'object') || (b && typeof b === 'object')) return JSON.stringify(a ?? {}) === JSON.stringify(b ?? {});
  const na = Number(a), nb = Number(b);
  if (a !== '' && b !== '' && a != null && b != null && !Number.isNaN(na) && !Number.isNaN(nb)) return na === nb;
  return String(a ?? '') === String(b ?? '');
};

/** What the request changes, in words: "Mortality 5 → 9" or the values for a new record. */
function describe(cr, code) {
  if (cr.action === 'delete') return 'Delete this record';
  const parts = Object.entries(cr.payload || {})
    .filter(([k, v]) => !SKIP.has(k) && v !== '' && v != null)
    .filter(([k, v]) => cr.action === 'create' || !same(cr.before?.[k], v))
    .map(([k, v]) => (cr.action === 'update' ? `${LABELS[k] || k} ${show(cr.before?.[k], code) ?? '—'} → ${show(v, code)}` : `${LABELS[k] || k} ${show(v, code)}`));
  return parts.join(' · ') || '—';
}

/** Changes waiting for an admin. Admins approve / reject here; others just see them. */
export default function PendingChanges({ rows, onDecided, showFarm = false, title = 'Waiting for admin approval' }) {
  const { isAdmin } = useAuth();
  const { code } = useFeedTypes();
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState('');
  if (!rows?.length) return null;

  const decide = async (cr, ok) => {
    setBusy(cr.id); setError('');
    try {
      await (ok ? changeRequestAPI.approve(cr.id) : changeRequestAPI.reject(cr.id));
      onDecided?.();
    } catch (err) {
      const d = err.response?.data;
      setError(`${d?.error || getErrorMessage(err)}${d?.detail ? ` ${JSON.stringify(d.detail)}` : ''}`);
    }
    setBusy(null);
  };

  return (
    <section className="panel pending-changes" aria-label={title}>
      <div className="panel-head"><h2>{title} <Chip tone="warn">{rows.length}</Chip></h2></div>
      {error && <p className="error-msg" role="alert">{error}</p>}
      <ul className="pc-list">
        {rows.map(cr => (
          <li key={cr.id}>
            <div className="pc-main">
              <strong>{cr.action_label} {cr.model_label.toLowerCase()} · {fmtDate(cr.record_date)}</strong>
              {showFarm && <> · <Link to={`/flocks/${cr.flock}`}>{cr.farm_name}</Link></>}
              <div className="pc-what">{describe(cr, code)}</div>
              <div className="cell-sub">“{cr.reason}” — {cr.requested_by_name}, {new Date(cr.requested_at).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' })}</div>
            </div>
            {isAdmin && (
              <div className="pc-actions">
                <button className="btn btn-primary btn-sm" disabled={busy === cr.id} onClick={() => decide(cr, true)}>Approve</button>
                <button className="btn btn-secondary btn-sm" disabled={busy === cr.id} onClick={() => decide(cr, false)}>Reject</button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
