import { useState, useEffect } from 'react';
import { reportAPI } from '../api/client';

const MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];

export default function MonthlyReport() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [expandedFlock, setExpandedFlock] = useState(null);

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

  const years = [];
  for (let y = now.getFullYear(); y >= now.getFullYear() - 2; y--) years.push(y);

  const toggleFlock = (id) => setExpandedFlock(expandedFlock === id ? null : id);

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
          <button className="btn btn-secondary" onClick={() => window.open(`http://localhost:8000/api/reports/monthly/export/?year=${year}&month=${month}`, '_blank')}>
            Export Excel
          </button>
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
          <h2 className="section-title">{data.month_name} {data.year} — {data.flocks_count} Batch{data.flocks_count > 1 ? 'es' : ''} Sold</h2>

          {/* MAIN REPORT TABLE — all flocks as rows + totals */}
          <div className="table-wrapper" style={{ marginBottom: '2rem' }}>
            <table className="report-table">
              <thead>
                <tr>
                  <th>Farm</th>
                  <th>Placed</th>
                  <th>Chicks</th>
                  <th>Age</th>
                  <th>Mortality</th>
                  <th>Mort %</th>
                  <th>Sold (birds)</th>
                  <th>Sold (kg)</th>
                  <th>Avg Wt (kg)</th>
                  <th>Feed (kg)</th>
                  <th>Feed (bags)</th>
                  <th>FCR</th>
                  <th>Feed Cost (₹)</th>
                  <th>Cost/kg (₹)</th>
                  <th>Sale Amt (₹)</th>
                </tr>
              </thead>
              <tbody>
                {data.flocks.map(f => (
                  <tr key={f.flock_id} className="report-row-clickable" onClick={() => toggleFlock(f.flock_id)}>
                    <td><strong><span className="farm-code-badge-sm">{f.farm_code}</span> {f.farm_name}</strong></td>
                    <td>{f.placement_date}</td>
                    <td>{fmt(f.chick_count)}</td>
                    <td>{f.age_days}d</td>
                    <td>{fmt(f.total_mortality)}</td>
                    <td className={f.mortality_pct > 5 ? 'text-danger' : ''}>{f.mortality_pct}%</td>
                    <td>{fmt(f.total_sold_birds)}</td>
                    <td>{fmtDec(f.total_sold_weight_kg)}</td>
                    <td>{f.avg_bird_weight_kg ?? '—'}</td>
                    <td>{fmtDec(f.total_feed_kg)}</td>
                    <td>{f.total_feed_bags}</td>
                    <td className="report-highlight">{f.fcr ?? '—'}</td>
                    <td>{fmtDec(f.feed_cost)}</td>
                    <td className="report-highlight">{f.cost_per_kg_production != null ? fmtDec(f.cost_per_kg_production) : '—'}</td>
                    <td>{fmtDec(f.total_sale_amount)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="report-totals-row">
                  <td><strong>TOTAL</strong></td>
                  <td></td>
                  <td><strong>{fmt(data.summary.total_birds_placed)}</strong></td>
                  <td></td>
                  <td><strong>{fmt(data.summary.total_mortality)}</strong></td>
                  <td className={data.summary.mortality_pct > 5 ? 'text-danger' : ''}><strong>{data.summary.mortality_pct}%</strong></td>
                  <td><strong>{fmt(data.summary.total_sold_birds)}</strong></td>
                  <td><strong>{fmtDec(data.summary.total_sold_weight_kg)}</strong></td>
                  <td><strong>{data.summary.total_sold_weight_kg && data.summary.total_sold_birds ? (data.summary.total_sold_weight_kg / data.summary.total_sold_birds).toFixed(3) : '—'}</strong></td>
                  <td><strong>{fmtDec(data.summary.total_feed_kg)}</strong></td>
                  <td><strong>{(data.summary.total_feed_kg / 50).toFixed(1)}</strong></td>
                  <td className="report-highlight"><strong>{data.summary.fcr ?? '—'}</strong></td>
                  <td><strong>₹{fmtDec(data.summary.total_feed_cost)}</strong></td>
                  <td className="report-highlight"><strong>{data.summary.cost_per_kg_production != null ? fmtDec(data.summary.cost_per_kg_production) : '—'}</strong></td>
                  <td><strong>₹{fmtDec(data.summary.total_sale_amount)}</strong></td>
                </tr>
              </tfoot>
            </table>
          </div>

          {/* EXPANDED DETAIL — weekly mortality for clicked flock */}
          {data.flocks.map(f => (
            expandedFlock === f.flock_id && (
              <div key={`detail-${f.flock_id}`} className="report-batch">
                <div className="report-batch-header">
                  <h3>{f.farm_name} — Weekly Breakdown</h3>
                  <span className="farm-meta">Placed: {f.placement_date} &middot; {fmt(f.chick_count)} chicks &middot; Day {f.age_days}</span>
                </div>

                {/* Feed breakdown */}
                <div className="report-feed-row">
                  <span className="feed-badge feed-badge-bpsc">BPSC: {fmtDec(f.feed_bpsc_kg)} kg</span>
                  <span className="feed-badge feed-badge-bsc">BSC: {fmtDec(f.feed_bsc_kg)} kg</span>
                  <span className="feed-badge feed-badge-bfp">BFP: {fmtDec(f.feed_bfp_kg)} kg</span>
                  <span>Total: {fmtDec(f.total_feed_kg)} kg ({f.total_feed_bags} bags)</span>
                </div>

                {/* This month's sales */}
                <div className="report-month-sales">
                  Sales this month: {fmt(f.month_sold_birds)} birds &middot; {fmtDec(f.month_sold_weight_kg)} kg &middot; ₹{fmtDec(f.month_sale_amount)}
                </div>

                {/* Weekly mortality table */}
                <h4 style={{ margin: '1rem 0 0.5rem' }}>Weekly Mortality</h4>
                <div className="table-wrapper">
                  <table>
                    <thead>
                      <tr><th>Week</th><th>Days</th><th>Mortality</th><th>Mortality %</th></tr>
                    </thead>
                    <tbody>
                      {f.weekly_mortality.map(w => (
                        <tr key={w.week}>
                          <td>Week {w.week}</td>
                          <td>{w.days}</td>
                          <td>{w.mortality}</td>
                          <td className={w.mortality_pct > 1 ? 'text-danger' : ''}>{w.mortality_pct}%</td>
                        </tr>
                      ))}
                      <tr className="table-total-row">
                        <td colSpan={2}><strong>Total</strong></td>
                        <td><strong>{f.total_mortality}</strong></td>
                        <td><strong>{f.mortality_pct}%</strong></td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <button className="btn btn-secondary" style={{ marginTop: '1rem' }} onClick={() => setExpandedFlock(null)}>
                  Close
                </button>
              </div>
            )
          ))}
        </>
      )}
    </div>
  );
}
