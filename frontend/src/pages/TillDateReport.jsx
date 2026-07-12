import { useState, useEffect } from 'react';
import { ReportSkeleton } from '../components/Skeletons';
import { reportAPI } from '../api/client';

export default function TillDateReport() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    reportAPI.tillDate().then(res => {
      setData(res.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) return <ReportSkeleton />;
  if (!data) return <div className="empty-state">Could not load data.</div>;

  const fmt = (n) => n != null ? Number(n).toLocaleString('en-IN') : '—';
  const fmtDec = (n) => n != null ? Number(n).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—';
  const fb = data.feed_by_type || {};
  const rates = data.latest_feed_rates || {};

  return (
    <div className="page">
      <h1>Till Date Report</h1>
      <p className="farm-meta" style={{ marginBottom: '1.5rem' }}>Cumulative data across all flocks since inception</p>

      {/* BIRDS */}
      <h2 className="section-title">Birds</h2>
      <div className="stats-grid stats-grid-wide">
        <div className="stat-card stat-highlight">
          <span className="stat-label">Birds Placed</span>
          <span className="stat-value">{fmt(data.total_birds_placed)}</span>
        </div>
        <div className="stat-card stat-alert">
          <span className="stat-label">Total Mortality</span>
          <span className="stat-value">{fmt(data.total_mortality)}</span>
          <span className="stat-sub">{data.mortality_percentage}% of placed</span>
        </div>
        <div className="stat-card stat-success">
          <span className="stat-label">Sold (Birds)</span>
          <span className="stat-value">{fmt(data.total_sold_birds)}</span>
        </div>
        <div className="stat-card stat-success">
          <span className="stat-label">Sold (Weight)</span>
          <span className="stat-value">{fmtDec(data.total_sold_weight_kg)} kg</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Live Birds (current)</span>
          <span className="stat-value">{fmt(data.total_live_birds)}</span>
        </div>
      </div>

      {/* SALES */}
      <h2 className="section-title" style={{ marginTop: '2rem' }}>Sales</h2>
      <div className="stats-grid stats-grid-wide">
        <div className="stat-card stat-success">
          <span className="stat-label">Total Sale Amount</span>
          <span className="stat-value">₹{fmtDec(data.total_sale_amount)}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Avg Bird Weight</span>
          <span className="stat-value">{data.total_sold_birds > 0 ? (data.total_sold_weight_kg / data.total_sold_birds).toFixed(3) : '—'} kg</span>
        </div>
      </div>

      {/* FEED */}
      <h2 className="section-title" style={{ marginTop: '2rem' }}>Feed</h2>
      <div className="stats-grid stats-grid-wide">
        <div className="stat-card feed-card-bpsc">
          <span className="stat-label">BPSC (Pre-Starter)</span>
          <span className="stat-value">{fmtDec(fb.bpsc_bags)} bags</span>
          <span className="stat-sub">{fmtDec(fb.bpsc_kg)} kg {rates.BPSC ? `· ₹${rates.BPSC}/kg` : ''}</span>
        </div>
        <div className="stat-card feed-card-bsc">
          <span className="stat-label">BSC (Starter)</span>
          <span className="stat-value">{fmtDec(fb.bsc_bags)} bags</span>
          <span className="stat-sub">{fmtDec(fb.bsc_kg)} kg {rates.BSC ? `· ₹${rates.BSC}/kg` : ''}</span>
        </div>
        <div className="stat-card feed-card-bfp">
          <span className="stat-label">BFP (Finisher)</span>
          <span className="stat-value">{fmtDec(fb.bfp_bags)} bags</span>
          <span className="stat-sub">{fmtDec(fb.bfp_kg)} kg {rates.BFP ? `· ₹${rates.BFP}/kg` : ''}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Total Feed</span>
          <span className="stat-value">{fmtDec(data.total_feed_bags)} bags</span>
          <span className="stat-sub">{fmtDec(data.total_feed_kg)} kg</span>
        </div>
      </div>

      {/* EFFICIENCY */}
      <h2 className="section-title" style={{ marginTop: '2rem' }}>Efficiency</h2>
      <div className="stats-grid stats-grid-wide">
        <div className="stat-card stat-info">
          <span className="stat-label">FCR (Feed Conversion Ratio)</span>
          <span className="stat-value">{data.fcr ?? '—'}</span>
          <span className="stat-sub">Total feed ÷ Total weight sold</span>
        </div>
        <div className="stat-card stat-info">
          <span className="stat-label">Feed Cost / kg Production</span>
          <span className="stat-value">{data.cost_per_kg_production != null ? `₹${fmtDec(data.cost_per_kg_production)}` : '—'}</span>
          <span className="stat-sub">Feed cost ÷ Weight sold</span>
        </div>
        <div className="stat-card stat-info">
          <span className="stat-label">Total Feed Cost</span>
          <span className="stat-value">₹{fmtDec(data.total_feed_cost)}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Livability</span>
          <span className="stat-value">{data.total_birds_placed > 0 ? (100 - data.mortality_percentage).toFixed(2) : '—'}%</span>
        </div>
      </div>

      {/* CURRENT FEED RATES */}
      {Object.keys(rates).length > 0 && (
        <>
          <h2 className="section-title" style={{ marginTop: '2rem' }}>Current Feed Rates</h2>
          <div className="feed-rate-bar">
            {rates.BPSC && <span><strong>BPSC ₹{rates.BPSC}/kg</strong></span>}
            {rates.BSC && <span> · <strong>BSC ₹{rates.BSC}/kg</strong></span>}
            {rates.BFP && <span> · <strong>BFP ₹{rates.BFP}/kg</strong></span>}
          </div>
        </>
      )}

      {data.feed_rates && data.feed_rates.length > 0 && (
        <details className="feed-history" style={{ marginTop: '0.5rem' }}>
          <summary>Feed Rate History ({data.feed_rates.length})</summary>
          <div className="table-wrapper" style={{ marginTop: '0.5rem' }}>
            <table>
              <thead><tr><th>Week</th><th>Type</th><th>Rate (₹/kg)</th><th>Notes</th></tr></thead>
              <tbody>
                {data.feed_rates.map(fr => (
                  <tr key={fr.id}><td>{fr.week_start_date}</td><td><span className={`feed-badge feed-badge-${fr.feed_type.toLowerCase()}`}>{fr.feed_type}</span></td><td>₹{fr.rate_per_kg}</td><td>{fr.notes || '—'}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </div>
  );
}
