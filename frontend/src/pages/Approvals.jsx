import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { billAPI, changeRequestAPI } from '../api/client';
import PendingChanges from '../components/PendingChanges';
import { Chip, Panel } from '../components/ui';
import { PAY_LABEL, PAY_TONE, fmtDate, fmtNum } from '../utils/format';

/** Admin: everything waiting for a decision — bills to approve, bills still to pay,
 *  and changes outside the edit window. */
export default function Approvals() {
  const [pending, setPending] = useState(null);
  const [recent, setRecent] = useState([]);
  const [bills, setBills] = useState([]);
  const load = () => {
    billAPI.list().then(r => setBills(r.data)).catch(() => {});
    changeRequestAPI.list({ status: 'pending' }).then(r => setPending(r.data)).catch(() => setPending([]));
    changeRequestAPI.list({}).then(r => setRecent(r.data.filter(x => x.status !== 'pending').slice(0, 30))).catch(() => {});
  };
  useEffect(() => { load(); }, []);

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Approvals</h1>
          <p className="farm-meta">Bills to check before payment, payments still due, and changes supervisors asked for
            outside the edit window (approving applies the change as theirs, with all the usual checks).</p>
        </div>
      </div>
      <BillTable title="Bills waiting for approval" rows={bills.filter(b => b.approval_status === 'pending')}
                 empty="No bills waiting for approval." />
      <BillTable title="Approved bills still to pay" rows={bills.filter(b => b.approval_status === 'approved' && b.payment_status !== 'paid')}
                 empty="Every approved bill is paid." showPaid />

      {pending === null ? <p className="muted">Loading…</p> : pending.length === 0
        ? <Panel title="Changes waiting for approval" className="approvals-block"><p className="panel-body muted">No changes waiting for approval.</p></Panel>
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

function BillTable({ title, rows, empty, showPaid }) {
  return (
    <Panel title={title} className="approvals-block" actions={<span className="muted small">{rows.length || ''}</span>}>
      {rows.length === 0 ? <p className="panel-body muted">{empty}</p> : (
        <div className="table-wrapper">
          <table className="data-table cards-on-phone">
            <thead><tr><th>Farm</th><th>Generated</th><th className="r">To pay</th>{showPaid && <th className="r">Balance</th>}<th>Status</th><th></th></tr></thead>
            <tbody>
              {rows.map(b => (
                <tr key={b.id}>
                  <td className="cell-main"><strong>{b.farm_name}</strong> <span className="muted">{b.farm_code}</span>
                    <span className="cell-sub">{b.farmer_name}</span></td>
                  <td data-label="Generated">{fmtDate(b.generated_at)}<span className="cell-sub">by {b.generated_by_name || '—'}</span></td>
                  <td data-label="To pay" className="r num">₹{fmtNum(b.amount_paid)}</td>
                  {showPaid && <td data-label="Balance" className="r num">₹{fmtNum(b.balance_due)}</td>}
                  <td data-label="Status">{b.approval_status === 'pending' ? <Chip tone="warn">Waiting for approval</Chip>
                    : <Chip tone={PAY_TONE[b.payment_status]}>{PAY_LABEL[b.payment_status]}</Chip>}</td>
                  <td className="row-actions"><Link to={`/flocks/${b.flock}/bill`} className="btn btn-secondary btn-sm">Open bill</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}
