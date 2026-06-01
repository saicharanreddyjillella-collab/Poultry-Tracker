import { useState, useEffect } from 'react';
import { reportAPI } from '../api/client';

const MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];

export default function MonthlyReport() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = () => {
    setLoading(true);
    reportAPI.monthly(year, month).then(res => {
      setData(res.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(() => { load(); }, [year, month]);

  const fmt = (n) => n != null ? Number(n).toLocaleString('en-IN') : '—';
  const fmtDec = (n) => n != null ? Number(n).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—';

  // Generate year options (current year and 2 years back)
  const years = [];
  for (let y = now.getFullYear(); y >= now.getFullYear() - 2; y--) years.push(y);

  return (
    <div className="page">
      <div className="page-header">
        <h1>Monthly Report</h1>
        <div className="report-filters">
          <select value={month} onChange={e => setMonth(parseInt(e.target.value))}>
            {MONTHS.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
          </select>
          <select value={year} onChange={e => setYear(parseInt(e.target.value))}>
            {years.map(y => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>
      </div>

      {loading && <div className="loading">Loading report...</div>}

      {!loading && data && data.flocks_count === 0 && (
        <div className="empty-state">
          <p>No batches sold in {data.month_name} {data.year}.</p>
        </div>
      )}

      {!loading && data && data.flocks_count > 0 && (
        <>
          {/* GRAND SUMMARY */}
          <h2 className="section-title">{data.month_name} {data.year} — Summary ({data.flocks_count} batch{data.flocks_count > 1 ? 'es' : ''})</h2>
          <div className="stats-grid stats-grid-wide">
            <div className="stat-card stat-highlight">
              <span className="stat-label">Birds Placed</span>
              <span className="stat-value">{fmt(data.summary.total_birds_placed)}</span>
            </div>
            <div className="stat-card stat-alert">
              <span className="stat-label">Total Mortality</span>
              <span className="stat-value">{fmt(data.summary.total_mortality)} <small>({data.summary.mortality_pct}%)</small></span>
            </div>
            <div className="stat-card stat-success">
              <span className="stat-label">Sold (Birds)</span>
              <span className="stat-value">{fmt(data.summary.total_sold_birds)}</span>
            </div>
            <div className="stat-card stat-success">
              <span className="stat-label">Sold (kg)</span>
              <span className="stat-value">{fmtDec(data.summary.total_sold_weight_kg)} kg</span>
            </div>
            <div className="stat-card stat-success">
              <span className="stat-label">Sale Amount</span>
              <span className="stat-value">₹{fmtDec(data.summary.total_sale_amount)}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Total Feed</span>
              <span className="stat-value">{fmtDec(data.summary.total_feed_kg)} kg</span>
            </div>
            <div className="stat-card stat-info">
              <span className="stat-label">FCR</span>
              <span className="stat-value">{data.summary.fcr ?? '—'}</span>
            </div>
            <div className="stat-card stat-info">
              <span className="stat-label">Feed Cost / kg</span>
              <span className="stat-value">{data.summary.cost_per_kg_production != null ? `₹${fmtDec(data.summary.cost_per_kg_production)}` : '—'}</span>
            </div>
          </div>

          {/* PER BATCH */}
          {data.flocks.map(flock => (
            <div key={flock.flock_id} className="report-batch">
              <div className="report-batch-header">
                <h3>{flock.farm_name}</h3>
                <span className="farm-meta">Placed: {flock.placement_date} &middot; {fmt(flock.chick_count)} chicks &middot; Day {flock.age_days}</span>
              </div>

              {/* Batch summary row */}
              <div className="stats-grid" style={{ marginBottom: '1rem' }}>
                <div className="stat-card stat-alert">
                  <span className="stat-label">Mortality</span>
                  <span className="stat-value">{flock.total_mortality} <small>({flock.mortality_pct}%)</small></span>
                </div>
                <div className="stat-card stat-success">
                  <span className="stat-label">Sold</span>
                  <span className="stat-value">{fmt(flock.total_sold_birds)} / {fmtDec(flock.total_sold_weight_kg)} kg</span>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Avg Bird Wt</span>
                  <span className="stat-value">{flock.avg_bird_weight_kg ? `${flock.avg_bird_weight_kg} kg` : '—'}</span>
                </div>
                <div className="stat-card stat-info">
                  <span className="stat-label">FCR</span>
                  <span className="stat-value">{flock.fcr ?? '—'}</span>
                </div>
                <div className="stat-card stat-info">
                  <span className="stat-label">Feed Cost/kg</span>
                  <span className="stat-value">{flock.cost_per_kg_production != null ? `₹${fmtDec(flock.cost_per_kg_production)}` : '—'}</span>
                </div>
              </div>

              {/* Feed breakdown */}
              <div className="report-feed-row">
                <span className="feed-badge feed-badge-bpsc">BPSC: {fmtDec(flock.feed_bpsc_kg)} kg</span>
                <span className="feed-badge feed-badge-bsc">BSC: {fmtDec(flock.feed_bsc_kg)} kg</span>
                <span className="feed-badge feed-badge-bfp">BFP: {fmtDec(flock.feed_bfp_kg)} kg</span>
                <span>Total: {fmtDec(flock.total_feed_kg)} kg ({flock.total_feed_bags} bags)</span>
                <span>Feed Cost: ₹{fmtDec(flock.feed_cost)}</span>
              </div>

              {/* This month's sales */}
              <div className="report-month-sales">
                <span>This month: {fmt(flock.month_sold_birds)} birds, {fmtDec(flock.month_sold_weight_kg)} kg, ₹{fmtDec(flock.month_sale_amount)}</span>
              </div>

              {/* Weekly mortality table */}
              <h4 style={{ margin: '1rem 0 0.5rem' }}>Weekly Mortality</h4>
              <div className="table-wrapper">
                <table>
                  <thead>
                    <tr><th>Week</th><th>Days</th><th>Mortality</th><th>Mortality %</th></tr>
                  </thead>
                  <tbody>
                    {flock.weekly_mortality.map(w => (
                      <tr key={w.week}>
                        <td>Week {w.week}</td>
                        <td>{w.days}</td>
                        <td>{w.mortality}</td>
                        <td className={w.mortality_pct > 1 ? 'text-danger' : ''}>{w.mortality_pct}%</td>
                      </tr>
                    ))}
                    <tr className="table-total-row">
                      <td colSpan={2}><strong>Total</strong></td>
                      <td><strong>{flock.total_mortality}</strong></td>
                      <td><strong>{flock.mortality_pct}%</strong></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
