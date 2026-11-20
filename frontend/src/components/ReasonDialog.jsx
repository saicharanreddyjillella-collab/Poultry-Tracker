import { useState } from 'react';

/** Asks why a change outside the edit window is needed. Controlled by useApprovalSave(). */
export default function ReasonDialog({ open, message, onSubmit, onCancel }) {
  const [reason, setReason] = useState('');
  if (!open) return null;
  const submit = (e) => { e.preventDefault(); if (reason.trim()) { onSubmit(reason.trim()); setReason(''); } };
  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="reason-title">
      <form className="modal-card" style={{ maxWidth: 480 }} onSubmit={submit}>
        <h3 id="reason-title">Needs admin approval</h3>
        <p className="muted">{message}</p>
        <div className="form-group">
          <label htmlFor="change-reason">Reason *</label>
          <textarea id="change-reason" rows={3} required autoFocus value={reason} onChange={e => setReason(e.target.value)}
                    placeholder="e.g. Forgot to enter on the day / recount found 2 more dead" />
        </div>
        <div className="form-actions" style={{ justifyContent: 'flex-end' }}>
          <button type="button" className="btn btn-secondary" onClick={() => { setReason(''); onCancel(); }}>Cancel</button>
          <button type="submit" className="btn btn-primary">Send for approval</button>
        </div>
      </form>
    </div>
  );
}
