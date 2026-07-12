import { useState, useEffect } from 'react';
import { BillSkeleton } from '../components/Skeletons';
import { useParams, Link } from 'react-router-dom';
import { billAPI } from '../api/client';

export default function BillView() {
  const { flockId } = useParams();
  const [bill, setBill] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    billAPI.get(flockId).then(res => {
      setBill(res.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [flockId]);

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
      </div>

      <div className="bill-a4">
        {/* HEADER */}
        <div className="bill-top">
          <div className="bill-company">
            <h2>Sai Ram Feeds</h2>
            <p>Vill. Nagaram, Mdl. Lingalaghanpur, Dist. Jangaon - 506 167</p>
          </div>
          <div className="bill-top-right">
            <span className={`bill-grade bill-grade-${bill.farmer_grade.toLowerCase().replace('+', 'plus')}`}>{bill.farmer_grade}</span>
            <span className="bill-date">{new Date(bill.generated_at).toLocaleDateString('en-IN')}</span>
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
          <div className="bill-final-line"><span>Gross Payable</span><span>₹{fmt(bill.gross_payable)}</span></div>
          {hasRecoveries && <div className="bill-final-line bill-final-deduct"><span>Less: Recoveries</span><span>- ₹{fmt(bill.total_recoveries)}</span></div>}
          <div className="bill-final-line bill-final-net"><span>Net Payable to Farmer</span><span>₹{fmt(bill.net_payable)}</span></div>
        </div>
      </div>
    </div>
  );
}
