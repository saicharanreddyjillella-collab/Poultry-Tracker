import { useState, useEffect } from 'react';
import { reportAPI } from '../api/client';

export default function RegionPerformance() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedRegion, setSelectedRegion] = useState('');

  const load = () => {
    setLoading(true);
    reportAPI.region(selectedRegion).then(res => {
      setData(res.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(() => { load(); }, [selectedRegion]);

  const fmt = (n) => n != null ? Number(n).toLocaleString('en-IN') : '—';
  const fmtDec = (n) => n != null ? Number(n).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—';

  if (loading && !data) return <div className="loading">Loading...</div>;

  return (
    <div className="page">
      <div className="page-header">
        <h1>Region Performance</h1>
        {data && data.regions.length > 0 && (
          <div className="report-filters">
            <select value={selectedRegion} onChange={e => setSelectedRegion(e.target.value)}>
              <option value="">All Regions</option>
              {data.regions.map(r => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
        )}
      </div>

      {data && data.data.length === 0 && (
        <div className="empty-state"><p>No regions found. Add a region to your farms first.</p></div>
      )}

      {data && data.data.length > 0 && (
        <>
          {/* COMPARISON TABLE */}
          <div className="table-wrapper" style={{ marginBottom: '2rem' }}>
            <table className="report-table">
              <thead>
                <tr>
                  <th>Region</th>
                  <th>Farms</th>
                  <th>Active</th>
                  <th>Completed</th>
                  <th>Live Birds</th>
                  <th>Placed</th>
                  <th>Mortality</th>
                  <th>Mort %</th>
                  <th>Sold (birds)</th>
                  <th>Sold (kg)</th>
                  <th>Avg Wt</th>
                  <th>Feed (kg)</th>
                  <th>FCR</th>
                  <th>Feed Cost</th>
                  <th>Cost/kg</th>
                  <th>Sale Amt</th>
                </tr>
              </thead>
              <tbody>
                {data.data.map(r => (
                  <tr key={r.region} className={selectedRegion ? '' : 'report-row-clickable'} onClick={() => { if (!selectedRegion) setSelectedRegion(r.region === 'Unassigned' ? '' : r.region); }}>
                    <td><strong>{r.region}</strong></td>
                    <td>{r.farm_count}</td>
                    <td>{r.active_flocks}</td>
                    <td>{r.closed_flocks}</td>
                    <td>{fmt(r.live_birds)}</td>
                    <td>{fmt(r.total_birds_placed)}</td>
                    <td>{fmt(r.total_mortality)}</td>
                    <td className={r.mortality_pct > 5 ? 'text-danger' : ''}>{r.mortality_pct}%</td>
                    <td>{fmt(r.total_sold_birds)}</td>
                    <td>{fmtDec(r.total_sold_weight_kg)}</td>
                    <td>{r.avg_bird_weight_kg ?? '—'}</td>
                    <td>{fmtDec(r.total_feed_kg)}</td>
                    <td className="report-highlight">{r.fcr ?? '—'}</td>
                    <td>₹{fmtDec(r.total_feed_cost)}</td>
                    <td className="report-highlight">{r.cost_per_kg_production != null ? `₹${fmtDec(r.cost_per_kg_production)}` : '—'}</td>
                    <td>₹{fmtDec(r.total_sale_amount)}</td>
                  </tr>
                ))}
              </tbody>
              {data.data.length > 1 && (
                <tfoot>
                  <tr className="report-totals-row">
                    <td><strong>TOTAL</strong></td>
                    <td><strong>{data.data.reduce((s, r) => s + r.farm_count, 0)}</strong></td>
                    <td><strong>{data.data.reduce((s, r) => s + r.active_flocks, 0)}</strong></td>
                    <td><strong>{data.data.reduce((s, r) => s + r.closed_flocks, 0)}</strong></td>
                    <td><strong>{fmt(data.data.reduce((s, r) => s + r.live_birds, 0))}</strong></td>
                    <td><strong>{fmt(data.data.reduce((s, r) => s + r.total_birds_placed, 0))}</strong></td>
                    <td><strong>{fmt(data.data.reduce((s, r) => s + r.total_mortality, 0))}</strong></td>
                    <td>{(() => {
                      const tp = data.data.reduce((s, r) => s + r.total_birds_placed, 0);
                      const tm = data.data.reduce((s, r) => s + r.total_mortality, 0);
                      return tp ? (tm / tp * 100).toFixed(2) + '%' : '—';
                    })()}</td>
                    <td><strong>{fmt(data.data.reduce((s, r) => s + r.total_sold_birds, 0))}</strong></td>
                    <td><strong>{fmtDec(data.data.reduce((s, r) => s + r.total_sold_weight_kg, 0))}</strong></td>
                    <td>{(() => {
                      const sb = data.data.reduce((s, r) => s + r.total_sold_birds, 0);
                      const sw = data.data.reduce((s, r) => s + r.total_sold_weight_kg, 0);
                      return sb ? (sw / sb).toFixed(3) : '—';
                    })()}</td>
                    <td><strong>{fmtDec(data.data.reduce((s, r) => s + r.total_feed_kg, 0))}</strong></td>
                    <td className="report-highlight"><strong>{(() => {
                      const f = data.data.reduce((s, r) => s + r.total_feed_kg, 0);
                      const w = data.data.reduce((s, r) => s + r.total_sold_weight_kg, 0);
                      return w ? (f / w).toFixed(3) : '—';
                    })()}</strong></td>
                    <td><strong>₹{fmtDec(data.data.reduce((s, r) => s + r.total_feed_cost, 0))}</strong></td>
                    <td className="report-highlight"><strong>{(() => {
                      const fc = data.data.reduce((s, r) => s + r.total_feed_cost, 0);
                      const w = data.data.reduce((s, r) => s + r.total_sold_weight_kg, 0);
                      return w ? `₹${(fc / w).toFixed(2)}` : '—';
                    })()}</strong></td>
                    <td><strong>₹{fmtDec(data.data.reduce((s, r) => s + r.total_sale_amount, 0))}</strong></td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>

          {/* VISUAL COMPARISON CARDS */}
          {data.data.length > 1 && (
            <>
              <h2 className="section-title">Key Metrics Comparison</h2>
              <div className="region-compare-grid">
                {data.data.map(r => (
                  <div key={r.region} className="region-compare-card">
                    <h3>{r.region}</h3>
                    <div className="region-metrics">
                      <div className="region-metric">
                        <span className="region-metric-label">FCR</span>
                        <span className={`region-metric-value ${r.fcr && r.fcr <= Math.min(...data.data.filter(x => x.fcr).map(x => x.fcr)) ? 'text-ok' : ''}`}>
                          {r.fcr ?? '—'}
                        </span>
                      </div>
                      <div className="region-metric">
                        <span className="region-metric-label">Mortality</span>
                        <span className={`region-metric-value ${r.mortality_pct > 5 ? 'text-danger' : ''}`}>{r.mortality_pct}%</span>
                      </div>
                      <div className="region-metric">
                        <span className="region-metric-label">Cost/kg</span>
                        <span className="region-metric-value">{r.cost_per_kg_production != null ? `₹${r.cost_per_kg_production}` : '—'}</span>
                      </div>
                      <div className="region-metric">
                        <span className="region-metric-label">Avg Wt</span>
                        <span className="region-metric-value">{r.avg_bird_weight_kg ?? '—'} kg</span>
                      </div>
                    </div>
                    <p className="farm-meta">{r.farm_count} farms &middot; {r.active_flocks} active &middot; {fmt(r.live_birds)} live birds</p>
                  </div>
                ))}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
