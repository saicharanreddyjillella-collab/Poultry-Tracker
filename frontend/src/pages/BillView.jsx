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
  if (!bill) return <div className="empty-state"><p>Bill not found.</p><Link to="/" className="btn btn-primary">Back to Dashboard</Link></div>;

  const fmt = (n) => n != null ? Number(n).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—';

  return (
    <div className="page bill-page">
      <div className="page-header">
        <div>
          <Link to={`/flocks/${flockId}`} className="back-link">&larr; Back to Flock</Link>
          <h1>Farmer Bill</h1>
        </div>
        <button className="btn btn-secondary" onClick={() => window.print()}>Print Bill</button>
      </div>

      {/* BILL HEADER */}
      <div className="bill-card">
        <div className="bill-header-section">
          <div className="bill-company">
            <h2>🐔 Sai Ram Feeds</h2>
            <p>Vill. Nagaram, Mdl. Lingalaghanpur, Dist. Jangaon - 506 167</p>
          </div>
          <div className="bill-meta">
            <div><span className="bill-label">Bill Date</span><span>{new Date(bill.generated_at).toLocaleDateString('en-IN')}</span></div>
            <div><span className="bill-label">Grade</span><span className={`bill-grade bill-grade-${bill.farmer_grade.toLowerCase().replace('+', 'plus')}`}>{bill.farmer_grade}</span></div>
          </div>
        </div>

        <div className="bill-farmer-info">
          <div className="bill-info-grid">
            <div><span className="bill-label">Farm Code</span><span className="farm-code-badge">{bill.farm_code}</span></div>
            <div><span className="bill-label">Farm Name</span><span>{bill.farm_name}</span></div>
            <div><span className="bill-label">Farmer</span><span>{bill.farmer_name}</span></div>
            <div><span className="bill-label">Placement Date</span><span>{bill.placement_date}</span></div>
            <div><span className="bill-label">Age at Close</span><span>{bill.age_days} days</span></div>
          </div>
        </div>

        {/* FLOCK SUMMARY */}
        <h3 className="bill-section-title">Flock Summary</h3>
        <div className="bill-table-wrap">
          <table className="bill-table">
            <tbody>
              <tr><td>Chicks Placed</td><td className="bill-val">{bill.chicks_placed.toLocaleString()}</td></tr>
              <tr><td>Total Mortality</td><td className="bill-val">{bill.total_mortality.toLocaleString()} ({(bill.total_mortality / bill.chicks_placed * 100).toFixed(2)}%)</td></tr>
              <tr><td>Birds Sold</td><td className="bill-val">{bill.total_sold_birds.toLocaleString()}</td></tr>
              <tr><td>Total Weight Sold</td><td className="bill-val">{fmt(bill.total_sold_weight_kg)} kg</td></tr>
              <tr><td>Average Selling Price</td><td className="bill-val">₹{fmt(bill.avg_selling_price)}/kg</td></tr>
              <tr><td>Total Feed Consumed</td><td className="bill-val">{fmt(bill.total_feed_kg)} kg ({fmt(bill.total_feed_bags)} bags)</td></tr>
              <tr><td>FCR</td><td className="bill-val">{bill.fcr ?? '—'}</td></tr>
              <tr><td>Avg Bird Weight</td><td className="bill-val">{bill.avg_bird_weight_kg ? `${bill.avg_bird_weight_kg} kg` : '—'}</td></tr>
            </tbody>
          </table>
        </div>

        {/* COST BREAKDOWN */}
        <h3 className="bill-section-title">Production Cost</h3>
        <div className="bill-table-wrap">
          <table className="bill-table">
            <tbody>
              <tr><td>Chick Cost ({bill.chicks_placed} × ₹{bill.config_snapshot?.chick_cost_per_bird || '34'})</td><td className="bill-val">₹{fmt(bill.chick_cost)}</td></tr>
              <tr><td>Feed Cost ({fmt(bill.total_feed_kg)} kg × ₹{bill.config_snapshot?.feed_cost_per_kg || '44'})</td><td className="bill-val">₹{fmt(bill.feed_cost)}</td></tr>
              <tr><td>Medicine/Vaccine Cost</td><td className="bill-val">₹{fmt(bill.medicine_cost)}</td></tr>
              <tr><td>Admin & Overhead Cost</td><td className="bill-val">₹{fmt(bill.admin_cost)}</td></tr>
              <tr className="bill-row-total"><td>Total Production Cost</td><td className="bill-val">₹{fmt(bill.production_cost_total)}</td></tr>
              <tr className="bill-row-highlight"><td>Production Cost per kg</td><td className="bill-val">₹{fmt(bill.production_cost_per_kg)}/kg</td></tr>
            </tbody>
          </table>
        </div>

        {/* GROWING CHARGES */}
        <h3 className="bill-section-title">Growing Charges</h3>
        <div className="bill-table-wrap">
          <table className="bill-table">
            <tbody>
              <tr><td>Farmer Grade</td><td className="bill-val"><span className={`bill-grade bill-grade-${bill.farmer_grade.toLowerCase().replace('+', 'plus')}`}>{bill.farmer_grade}</span></td></tr>
              <tr><td>Growing Charges per kg</td><td className="bill-val">₹{fmt(bill.growing_charges_per_kg)}/kg</td></tr>
              <tr className="bill-row-total"><td>Growing Charges ({fmt(bill.total_sold_weight_kg)} kg × ₹{fmt(bill.growing_charges_per_kg)})</td><td className="bill-val">₹{fmt(bill.growing_charges_total)}</td></tr>
            </tbody>
          </table>
        </div>

        {/* RATE INCENTIVE */}
        {parseFloat(bill.rate_incentive_total) > 0 && (
          <>
            <h3 className="bill-section-title">Rate Incentive</h3>
            <div className="bill-table-wrap">
              <table className="bill-table">
                <tbody>
                  <tr><td>Rate Incentive per kg</td><td className="bill-val">₹{fmt(bill.rate_incentive_per_kg)}/kg</td></tr>
                  <tr className="bill-row-total"><td>Rate Incentive Total</td><td className="bill-val text-ok">+ ₹{fmt(bill.rate_incentive_total)}</td></tr>
                </tbody>
              </table>
            </div>
          </>
        )}

        {/* RECOVERIES */}
        {parseFloat(bill.total_recoveries) > 0 && (
          <>
            <h3 className="bill-section-title">Recoveries</h3>
            <div className="bill-table-wrap">
              <table className="bill-table">
                <tbody>
                  {parseFloat(bill.first_week_mortality_recovery) > 0 && <tr><td>1st Week Excess Mortality</td><td className="bill-val text-danger">- ₹{fmt(bill.first_week_mortality_recovery)}</td></tr>}
                  {parseFloat(bill.negligence_recovery) > 0 && <tr><td>Farmer Negligence</td><td className="bill-val text-danger">- ₹{fmt(bill.negligence_recovery)}</td></tr>}
                  {parseFloat(bill.shortage_recovery) > 0 && <tr><td>Shortage of Birds</td><td className="bill-val text-danger">- ₹{fmt(bill.shortage_recovery)}</td></tr>}
                  {parseFloat(bill.fcr_recovery) > 0 && <tr><td>FCR Recovery</td><td className="bill-val text-danger">- ₹{fmt(bill.fcr_recovery)}</td></tr>}
                  {parseFloat(bill.ifft_charges) > 0 && <tr><td>IFFT Charges ({fmt(bill.total_feed_bags)} bags × ₹25)</td><td className="bill-val text-danger">- ₹{fmt(bill.ifft_charges)}</td></tr>}
                  <tr className="bill-row-total"><td>Total Recoveries</td><td className="bill-val text-danger">- ₹{fmt(bill.total_recoveries)}</td></tr>
                </tbody>
              </table>
            </div>
          </>
        )}

        {/* FINAL */}
        <div className="bill-final">
          <div className="bill-final-row">
            <span>Gross Payable (Growing + Incentive)</span>
            <span>₹{fmt(bill.gross_payable)}</span>
          </div>
          {parseFloat(bill.total_recoveries) > 0 && (
            <div className="bill-final-row bill-final-deduct">
              <span>Less: Recoveries</span>
              <span>- ₹{fmt(bill.total_recoveries)}</span>
            </div>
          )}
          <div className="bill-final-row bill-final-net">
            <span>Net Payable to Farmer</span>
            <span>₹{fmt(bill.net_payable)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
