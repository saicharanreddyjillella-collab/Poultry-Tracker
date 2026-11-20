import { useEffect, useState } from 'react';
import { changeRequestAPI } from '../api/client';
import PendingChanges from '../components/PendingChanges';
import { Chip, Panel } from '../components/ui';
import { fmtDate } from '../utils/format';

/** Admin: everything waiting for a decision — changes outside the edit window (and bills). */
export default function Approvals() {
  const [pending, setPending] = useState(null);
  const [recent, setRecent] = useState([]);
  const load = () => {
    changeRequestAPI.list({ status: 'pending' }).then(r => setPending(r.data)).catch(() => setPending([]));
    changeRequestAPI.list({}).then(r => setRecent(r.data.filter(x => x.status !== 'pending').slice(0, 30))).catch(() => {});
  };
  useEffect(() => { load(); }, []);

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Approvals</h1>
          <p className="farm-meta">Changes supervisors asked for outside the edit window. Approving applies the change
            as theirs, with all the usual checks; rejecting leaves the record as it is.</p>
        </div>
      </div>
      {pending === null ? <p className="muted">Loading…</p> : pending.length === 0
        ? <p className="panel panel-body muted">Nothing is waiting for approval.</p>
        : <PendingChanges rows={pending} onDecided={load} showFarm title="Changes waiting for approval" />}

      {recent.length > 0 && (
        <Panel title="Recently decided">
          <div className="table-wrapper">
            <table className="data-table cards-on-phone">
              <thead><tr><th>Change</th><th>Farm</th><th>Asked by</th><th>Reason</th><th>Decision</th></tr></thead>
              <tbody>
                {recent.map(cr => (
                  <tr key={cr.id}>
                    <td className="cell-main">{cr.action_label} {cr.model_label.toLowerCase()} · {fmtDate(cr.record_date)}</td>
                    <td data-label="Farm">{cr.farm_name}</td>
                    <td data-label="Asked by">{cr.requested_by_name}</td>
                    <td data-label="Reason">{cr.reason}</td>
                    <td data-label="Decision"><Chip tone={cr.status === 'approved' ? 'ok' : 'danger'}>{cr.status_label}</Chip>
                      <span className="cell-sub">{cr.decided_by_name}{cr.decision_note ? ` — ${cr.decision_note}` : ''}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </div>
  );
}
