import { useState, useEffect } from 'react';
import { BillSkeleton } from '../components/Skeletons';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { billAPI, getErrorMessage } from '../api/client';
import { useAuth } from '../context/AuthContext';
import brand from '../config/brand';

const REOPEN_MIN_CHARS = 10;

export default function BillView() {
  const { flockId } = useParams();
  const [bill, setBill] = useState(null);
  const [loading, setLoading] = useState(true);
  const [history, setHistory] = useState([]);
  const [showReopen, setShowReopen] = useState(false);
  const [reason, setReason] = useState('');
  const [reopening, setReopening] = useState(false);
  const [reopenError, setReopenError] = useState('');
  const { isAdmin } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    billAPI.get(flockId).then(res => {
      setBill(res.data);
      setLoading(false);
    }).catch(() => setLoading(false));
    billAPI.history(flockId).then(res => setHistory(res.data.versions || [])).catch(() => {});
  }, [flockId]);

  const submitReopen = async () => {
    setReopenError('');
    setReopening(true);
    try {
      await billAPI.reopen(flockId, reason.trim());
      navigate(`/flocks/${flockId}`);
    } catch (err) {
      setReopenError(getErrorMessage(err));
      setReopening(false);
    }
  };

  if (loading) return <BillSkeleton />;
  if (!bill) return <div className="empty-state"><p>Bill not found.</p><Link to="/" className="btn btn-primary">Back</Link></div>;

  const fmt = (n) => n != null ? Number(n).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—';
  const hasRecoveries = parseFloat(bill.total_recoveries) > 0;
  const hasIncentive = parseFloat(bill.rate_incentive_total) > 0;

  return (
    <div className="page bill-page">
      <div className="bill-no-print">
        <Link to={`/flocks/${flockId}`} className="back-link">&larr; Back to Flock</Link>
        <button className="btn btn-secondary" onClick={() => window.print()} style={{ float: 'right' }}>Print Bill</button>
        {isAdmin && !showReopen && (
          <button className="btn btn-danger" onClick={() => setShowReopen(true)} style={{ float: 'right', marginRight: '0.5rem' }}>Reopen Bill</button>
        )}
        <span style={{ float: 'right', marginRight: '0.75rem', lineHeight: '2.2rem', fontSize: '0.85rem', color: '#555' }}>
          🔒 Locked{bill.version > 1 ? ` · Revision ${bill.version}` : ''}
        </span>
      </div>

      {showReopen && (
        <div className="card bill-no-print" style={{ margin: '1rem 0', padding: '1rem', borderLeft: '4px solid #c0392b' }}>
          <h3 style={{ marginTop: 0 }}>Reopen this bill?</h3>
          <p style={{ fontSize: '0.9rem' }}>
            This archives version {bill.version} (₹{fmt(bill.net_payable)}) permanently and sets the flock back to active so its
            entries and sales can be corrected. Closing the flock again generates version {bill.version + 1}. The reason is recorded
            in the bill history and audit log.
          </p>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Reason for reopening (e.g. weighbridge slip corrected, missed sale entry)"
              rows={3}
            />
          </div>
          {reopenError && <div className="error-msg" style={{ marginTop: '0.5rem' }}>{reopenError}</div>}
          <div style={{ marginTop: '0.75rem', display: 'flex', gap: '0.5rem' }}>
            <button className="btn btn-danger" disabled={reopening || reason.trim().length < REOPEN_MIN_CHARS} onClick={submitReopen}>
              {reopening ? 'Reopening…' : 'Confirm Reopen'}
            </button>
            <button className="btn btn-secondary" disabled={reopening} onClick={() => { setShowReopen(false); setReason(''); setReopenError(''); }}>Cancel</button>
            {reason.trim().length < REOPEN_MIN_CHARS && (
              <span style={{ fontSize: '0.8rem', color: '#777', alignSelf: 'center' }}>At least {REOPEN_MIN_CHARS} characters</span>
            )}
          </div>
        </div>
      )}

      <div className="bill-a4">
        {/* HEADER */}
        <div className="bill-top">
          <div className="bill-company">
            <h2>{brand.billName}</h2>
            <p>{brand.address}</p>
          </div>
          <div className="bill-top-right">
            <span className={`bill-grade bill-grade-${bill.farmer_grade.toLowerCase().replace('+', 'plus')}`}>{bill.farmer_grade}</span>
            <span className="bill-date">{new Date(bill.generated_at).toLocaleDateString('en-IN')}</span>
            {bill.version > 1 && <span className="bill-date">Revision {bill.version}</span>}
          </div>
        </div>

        {/* FARM INFO — single row */}
        <div className="bill-info-row">
          <span><strong>{bill.farm_code}</strong> — {bill.farm_name}</span>
          <span>Farmer: {bill.farmer_name}</span>
          <span>Placed: {bill.placement_date}</span>
          <span>Age: {bill.age_days}d</span>
        </div>

        {/* TWO COLUMN LAYOUT */}
        <div className="bill-two-col">
          {/* LEFT — Flock Summary */}
          <div className="bill-col">
            <h4>Flock Summary</h4>
            <table className="bill-t">
              <tbody>
                <tr><td>Chicks Placed</td><td>{bill.chicks_placed.toLocaleString()}</td></tr>
                <tr><td>Mortality</td><td>{bill.total_mortality.toLocaleString()} ({(bill.total_mortality / bill.chicks_placed * 100).toFixed(1)}%)</td></tr>
                <tr><td>Birds Sold</td><td>{bill.total_sold_birds.toLocaleString()}</td></tr>
                <tr><td>Weight Sold</td><td>{fmt(bill.total_sold_weight_kg)} kg</td></tr>
                <tr><td>Avg Bird Weight</td><td>{bill.avg_bird_weight_kg ? `${bill.avg_bird_weight_kg} kg` : '—'}</td></tr>
                <tr><td>Avg Selling Price</td><td>₹{fmt(bill.avg_selling_price)}/kg</td></tr>
                <tr><td>Feed Consumed</td><td>{fmt(bill.total_feed_kg)} kg ({fmt(bill.total_feed_bags)} bags)</td></tr>
                <tr><td>FCR</td><td>{bill.fcr ?? '—'}</td></tr>
              </tbody>
            </table>
          </div>

          {/* RIGHT — Production Cost */}
          <div className="bill-col">
            <h4>Production Cost</h4>
            <table className="bill-t">
              <tbody>
                <tr><td>Chick Cost ({bill.chicks_placed} × ₹{bill.config_snapshot?.chick_cost_per_bird || '34'})</td><td>₹{fmt(bill.chick_cost)}</td></tr>
                <tr><td>Feed Cost ({fmt(bill.total_feed_kg)}kg × ₹{bill.config_snapshot?.feed_cost_per_kg || '44'})</td><td>₹{fmt(bill.feed_cost)}</td></tr>
                <tr><td>Medicine {bill.config_snapshot?.medicine_use_actual ? '(actual)' : `(${bill.chicks_placed} × ₹${bill.config_snapshot?.medicine_cost_per_chick || '5'})`}</td><td>₹{fmt(bill.medicine_cost)}</td></tr>
                <tr><td>Admin & Overhead</td><td>₹{fmt(bill.admin_cost)}</td></tr>
                <tr className="bill-t-total"><td>Total</td><td>₹{fmt(bill.production_cost_total)}</td></tr>
                <tr className="bill-t-highlight"><td>Cost per kg</td><td>₹{fmt(bill.production_cost_per_kg)}</td></tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* GROWING CHARGES + INCENTIVE + RECOVERIES — compact */}
        <div className="bill-two-col">
          <div className="bill-col">
            <h4>Growing Charges</h4>
            <table className="bill-t">
              <tbody>
                <tr><td>Grade</td><td><span className={`bill-grade bill-grade-${bill.farmer_grade.toLowerCase().replace('+', 'plus')}`}>{bill.farmer_grade}</span></td></tr>
                <tr><td>Rate</td><td>₹{fmt(bill.growing_charges_per_kg)}/kg</td></tr>
                <tr className="bill-t-total"><td>Total ({fmt(bill.total_sold_weight_kg)} kg)</td><td>₹{fmt(bill.growing_charges_total)}</td></tr>
              </tbody>
            </table>
            {hasIncentive && (
              <>
                <h4 style={{ marginTop: '0.5rem' }}>Rate Incentive</h4>
                <table className="bill-t">
                  <tbody>
                    <tr><td>₹{fmt(bill.rate_incentive_per_kg)}/kg</td><td className="text-ok">+ ₹{fmt(bill.rate_incentive_total)}</td></tr>
                  </tbody>
                </table>
              </>
            )}
          </div>

          <div className="bill-col">
            {hasRecoveries ? (
              <>
                <h4>Recoveries</h4>
                <table className="bill-t">
                  <tbody>
                    {parseFloat(bill.first_week_mortality_recovery) > 0 && <tr><td>1st Week Mortality</td><td className="text-danger">₹{fmt(bill.first_week_mortality_recovery)}</td></tr>}
                    {parseFloat(bill.negligence_recovery) > 0 && <tr><td>Negligence</td><td className="text-danger">₹{fmt(bill.negligence_recovery)}</td></tr>}
                    {parseFloat(bill.shortage_recovery) > 0 && <tr><td>Shortage</td><td className="text-danger">₹{fmt(bill.shortage_recovery)}</td></tr>}
                    {parseFloat(bill.fcr_recovery) > 0 && <tr><td>FCR Recovery</td><td className="text-danger">₹{fmt(bill.fcr_recovery)}</td></tr>}
                    {parseFloat(bill.ifft_charges) > 0 && <tr><td>IFFT ({fmt(bill.total_feed_bags)} bags × ₹25)</td><td className="text-danger">₹{fmt(bill.ifft_charges)}</td></tr>}
                    <tr className="bill-t-total"><td>Total Recoveries</td><td className="text-danger">₹{fmt(bill.total_recoveries)}</td></tr>
                  </tbody>
                </table>
              </>
            ) : (
              <div style={{ padding: '1rem 0', color: '#999', fontSize: '0.85rem' }}>No recoveries applied</div>
            )}
          </div>
        </div>

        {/* FINAL */}
        <div className="bill-final-compact">
          {parseFloat(bill.fcr_benchmark_adjustment) !== 0 && (
            <div className={`bill-final-line ${parseFloat(bill.fcr_benchmark_adjustment) >= 0 ? '' : 'bill-final-deduct'}`}>
              <span>FCR Benchmark {parseFloat(bill.fcr_benchmark_adjustment) >= 0 ? 'Premium' : 'Deduction'}</span>
              <span className={parseFloat(bill.fcr_benchmark_adjustment) >= 0 ? 'text-ok' : 'text-danger'}>
                {parseFloat(bill.fcr_benchmark_adjustment) >= 0 ? '+ ' : '- '}₹{fmt(Math.abs(parseFloat(bill.fcr_benchmark_adjustment)))}
              </span>
            </div>
          )}
          <div className="bill-final-line"><span>Gross Payable</span><span>₹{fmt(bill.gross_payable)}</span></div>
          {hasRecoveries && <div className="bill-final-line bill-final-deduct"><span>Less: Recoveries</span><span>- ₹{fmt(bill.total_recoveries)}</span></div>}
          <div className="bill-final-line bill-final-net"><span>Net Payable to Farmer</span><span>₹{fmt(bill.net_payable)}</span></div>
          {parseFloat(bill.tds_amount) > 0 && (
            <>
              <div className="bill-final-line bill-final-deduct">
                <span>Less: TDS @ {fmt(bill.tds_rate_pct)}%{bill.tds_pan_missing ? ' (PAN missing)' : ''}</span>
                <span>- ₹{fmt(bill.tds_amount)}</span>
              </div>
              <div className="bill-final-line bill-final-net"><span>Amount Paid (after TDS)</span><span>₹{fmt(bill.amount_paid)}</span></div>
            </>
          )}
          {parseFloat(bill.tds_amount) === 0 && bill.tds_pan_missing && (
            <div className="bill-final-line" style={{ color: '#b9770e', fontSize: '0.8rem' }}>⚠️ Grower PAN not on file — add it for TDS compliance.</div>
          )}
        </div>
      </div>

      {history.length > 0 && (
        <div className="card bill-no-print" style={{ margin: '1rem 0', padding: '1rem' }}>
          <h3 style={{ marginTop: 0 }}>Bill history</h3>
          <table className="report-table" style={{ width: '100%' }}>
            <thead>
              <tr><th>Version</th><th>Net payable</th><th>Generated</th><th>Reopened</th><th>By</th><th>Reason</th></tr>
            </thead>
            <tbody>
              {history.map(v => (
                <tr key={v.id}>
                  <td>v{v.version}</td>
                  <td>₹{fmt(v.net_payable)}</td>
                  <td>{v.generated_at ? new Date(v.generated_at).toLocaleDateString('en-IN') : '—'}</td>
                  <td>{new Date(v.reopened_at).toLocaleString('en-IN')}</td>
                  <td>{v.reopened_by_username || '—'}</td>
                  <td>{v.reason}</td>
                </tr>
              ))}
              <tr style={{ fontWeight: 600 }}>
                <td>v{bill.version} (current)</td>
                <td>₹{fmt(bill.net_payable)}</td>
                <td>{new Date(bill.generated_at).toLocaleDateString('en-IN')}</td>
                <td colSpan={3}>—</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
