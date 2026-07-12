import { useState, useEffect } from 'react';
import { ReportSkeleton } from '../components/Skeletons';
import { reportAPI } from '../api/client';

export default function Reports() {
  const [view, setView] = useState('monthly'); // monthly, tilldate, region
  const [year, setYear] = useState(new Date().getFullYear());
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [regionFilter, setRegionFilter] = useState('');
  const [data, setData] = useState(null);
  const [regions, setRegions] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      if (view === 'monthly') {
        const res = await reportAPI.monthly(year, month);
        setData(res.data);
      } else if (view === 'tilldate') {
        const res = await reportAPI.tillDate();
        setData(res.data);
      } else if (view === 'region') {
        const res = await reportAPI.region(regionFilter);
        setData(res.data);
        if (res.data.regions) setRegions(res.data.regions);
      }
    } catch (err) {
      console.error('Report error:', err);
      setData(null);
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, [view, year, month, regionFilter]);

  const fmt = (n) => n != null ? Number(n).toLocaleString('en-IN') : '—';
  const fmtDec = (n) => n != null ? Number(n).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—';

  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  const handleExport = async () => {
    if (view !== 'monthly') return;
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${import.meta.env.VITE_API_URL || '/api'}/reports/monthly/export/?year=${year}&month=${month}`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `report_${year}_${String(month).padStart(2, '0')}.xlsx`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch { alert('Export failed'); }
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1>Reports</h1>
        {view === 'monthly' && <button className="btn btn-secondary" onClick={handleExport}>Export Excel</button>}
      </div>

      {/* FILTERS BAR */}
      <div className="report-filters-bar">
        <div className="report-view-tabs">
          <button className={`report-tab ${view === 'monthly' ? 'report-tab-active' : ''}`} onClick={() => setView('monthly')}>Monthly</button>
          <button className={`report-tab ${view === 'tilldate' ? 'report-tab-active' : ''}`} onClick={() => setView('tilldate')}>Till Date</button>
          <button className={`report-tab ${view === 'region' ? 'report-tab-active' : ''}`} onClick={() => setView('region')}>Region</button>
        </div>
        <div className="report-filter-controls">
          {view === 'monthly' && (
            <>
              <select value={month} onChange={e => setMonth(parseInt(e.target.value))}>
                {months.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
              </select>
              <select value={year} onChange={e => setYear(parseInt(e.target.value))}>
                {[2024, 2025, 2026, 2027].map(y => <option key={y} value={y}>{y}</option>)}
              </select>
            </>
          )}
          {view === 'region' && regions.length > 0 && (
            <select value={regionFilter} onChange={e => setRegionFilter(e.target.value)}>
              <option value="">All Regions</option>
              {regions.map(r => <option key={r} value={r}>{r}</option>)}
            </select>
          )}
        </div>
      </div>

      {loading ? <ReportSkeleton /> : !data ? (
        <div className="empty-state"><p>No data available.</p></div>
      ) : (
        <>
          {/* MONTHLY VIEW */}
          {view === 'monthly' && (
            <>
              <p className="report-subtitle">{data.month_name} {data.year} — {data.flocks_count} flock(s) sold</p>
              {data.flocks && data.flocks.length > 0 ? (
                <div className="table-wrapper">
                  <table className="report-table">
                    <thead>
                      <tr>
                        <th>Farm</th><th>Owner</th><th>Region</th><th>Placed</th><th>Chicks</th>
                        <th>Age</th><th>Mort%</th><th>Sold</th><th>Weight</th><th>Avg Wt</th>
                        <th>Feed kg</th><th>FCR</th><th>Cost/kg</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.flocks.map((f, i) => (
                        <tr key={i}>
                          <td><span className="farm-code-badge-sm">{f.farm_code}</span> {f.farm_name}</td>
                          <td>{f.owner}</td><td>{f.region}</td>
                          <td>{f.placement_date}</td><td>{fmt(f.chick_count)}</td>
                          <td>{f.age_days}d</td>
                          <td className={f.mortality_pct > 5 ? 'text-danger' : ''}>{f.mortality_pct}%</td>
                          <td>{fmt(f.total_sold_birds)}</td>
                          <td>{fmtDec(f.total_sold_weight_kg)} kg</td>
                          <td>{f.avg_bird_weight_kg ? `${f.avg_bird_weight_kg} kg` : '—'}</td>
                          <td>{fmt(f.total_feed_kg)}</td>
                          <td>{f.fcr ?? '—'}</td>
                          <td className={f.cost_per_kg_production > 95 ? 'text-danger' : f.cost_per_kg_production ? 'text-ok' : ''}>
                            {f.cost_per_kg_production ? `₹${fmtDec(f.cost_per_kg_production)}` : '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : <div className="empty-state"><p>No flocks sold in {data.month_name} {data.year}</p></div>}
            </>
          )}

          {/* TILL DATE VIEW */}
          {view === 'tilldate' && (
            <div className="stats-grid stats-grid-wide" style={{ marginTop: '1rem' }}>
              <div className="stat-card"><span className="stat-label">Total Birds Placed</span><span className="stat-value">{fmt(data.total_birds_placed)}</span></div>
              <div className="stat-card"><span className="stat-label">Total Mortality</span><span className="stat-value">{fmt(data.total_mortality)} ({data.mortality_percentage}%)</span></div>
              <div className="stat-card"><span className="stat-label">Live Birds</span><span className="stat-value">{fmt(data.total_live_birds)}</span></div>
              <div className="stat-card"><span className="stat-label">Birds Sold</span><span className="stat-value">{fmt(data.total_sold_birds)}</span></div>
              <div className="stat-card"><span className="stat-label">Weight Sold</span><span className="stat-value">{fmtDec(data.total_sold_weight_kg)} kg</span></div>
              <div className="stat-card"><span className="stat-label">Total Feed</span><span className="stat-value">{fmt(data.total_feed_kg)} kg ({fmt(data.total_feed_bags)} bags)</span></div>
              <div className="stat-card"><span className="stat-label">FCR</span><span className="stat-value">{data.fcr ?? '—'}</span></div>
              <div className="stat-card"><span className="stat-label">Feed Cost</span><span className="stat-value">₹{fmt(data.total_feed_cost)}</span></div>
              <div className="stat-card"><span className="stat-label">Cost per kg</span><span className="stat-value">{data.cost_per_kg_production ? `₹${fmtDec(data.cost_per_kg_production)}` : '—'}</span></div>
              <div className="stat-card"><span className="stat-label">Sale Amount</span><span className="stat-value">₹{fmt(data.total_sale_amount)}</span></div>
            </div>
          )}

          {/* REGION VIEW */}
          {view === 'region' && (
            <>
              {data.data && data.data.length > 0 ? (
                <div className="table-wrapper" style={{ marginTop: '1rem' }}>
                  <table className="report-table">
                    <thead>
                      <tr><th>Region</th><th>Farms</th><th>Batches</th><th>Placed</th><th>Mort%</th><th>Sold</th><th>Weight</th><th>Feed kg</th><th>FCR</th></tr>
                    </thead>
                    <tbody>
                      {data.data.map((r, i) => (
                        <tr key={i}>
                          <td><strong>{r.region}</strong></td>
                          <td>{r.farms}</td><td>{r.batches}</td><td>{fmt(r.total_placed)}</td>
                          <td className={r.mortality_pct > 5 ? 'text-danger' : ''}>{r.mortality_pct}%</td>
                          <td>{fmt(r.total_sold_birds)}</td>
                          <td>{fmtDec(r.total_sold_weight)} kg</td>
                          <td>{fmt(r.total_feed_kg)}</td>
                          <td>{r.fcr ?? '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : <div className="empty-state"><p>No closed flocks found{regionFilter ? ` in ${regionFilter}` : ''}</p></div>}
            </>
          )}
        </>
      )}
    </div>
  );
}
