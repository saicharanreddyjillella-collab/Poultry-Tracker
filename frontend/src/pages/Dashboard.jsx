import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { dashboardAPI, feedRateAPI } from '../api/client';

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showFeedForm, setShowFeedForm] = useState(false);
  const [feedForm, setFeedForm] = useState({
    week_start_date: new Date().toISOString().split('T')[0],
    rate_per_kg: '',
    notes: '',
  });

  const load = () => {
    dashboardAPI.get().then(res => {
      setData(res.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleFeedRate = async (e) => {
    e.preventDefault();
    await feedRateAPI.create(feedForm);
    setShowFeedForm(false);
    setFeedForm({ week_start_date: new Date().toISOString().split('T')[0], rate_per_kg: '', notes: '' });
    load();
  };

  if (loading) return <div className="loading">Loading dashboard...</div>;
  if (!data) return <div className="empty-state">Could not load dashboard. Is the Django server running?</div>;

  const fmt = (n) => n != null ? Number(n).toLocaleString('en-IN') : '—';
  const fmtDec = (n, d = 2) => n != null ? Number(n).toLocaleString('en-IN', { minimumFractionDigits: d, maximumFractionDigits: d }) : '—';

  return (
    <div className="page">
      <div className="page-header">
        <h1>Integration Dashboard</h1>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn btn-secondary" onClick={() => setShowFeedForm(!showFeedForm)}>
            Update Feed Rate
          </button>
          <Link to="/farms/new" className="btn btn-primary">+ Add Farm</Link>
        </div>
      </div>

      {/* ---- LIFETIME SUMMARY ---- */}
      <h2 className="section-title">Lifetime Summary</h2>
      <div className="stats-grid stats-grid-wide">
        <div className="stat-card stat-highlight">
          <span className="stat-label">Birds Placed Till Date</span>
          <span className="stat-value">{fmt(data.total_birds_placed)}</span>
        </div>
        <div className="stat-card stat-success">
          <span className="stat-label">Sold Till Date (Birds)</span>
          <span className="stat-value">{fmt(data.total_sold_birds)}</span>
        </div>
        <div className="stat-card stat-success">
          <span className="stat-label">Sold Till Date (kg)</span>
          <span className="stat-value">{fmtDec(data.total_sold_weight_kg)} kg</span>
        </div>
        <div className="stat-card stat-success">
          <span className="stat-label">Sale Amount Till Date</span>
          <span className="stat-value">₹{fmtDec(data.total_sale_amount)}</span>
        </div>
        <div className="stat-card stat-alert">
          <span className="stat-label">Mortality Till Date</span>
          <span className="stat-value">{fmt(data.total_mortality)} <small>({data.mortality_percentage}%)</small></span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Total Feed Consumed</span>
          <span className="stat-value">{fmtDec(data.total_feed_kg)} kg</span>
        </div>
        <div className="stat-card stat-info">
          <span className="stat-label">FCR Till Date</span>
          <span className="stat-value">{data.fcr != null ? data.fcr : '—'}</span>
        </div>
        <div className="stat-card stat-info">
          <span className="stat-label">Cost / kg Production</span>
          <span className="stat-value">{data.cost_per_kg_production != null ? `₹${fmtDec(data.cost_per_kg_production)}` : '—'}</span>
        </div>
      </div>

      {/* ---- FEED RATE ---- */}
      <div className="feed-rate-bar">
        <span>Current Feed Rate: <strong>{data.current_feed_rate != null ? `₹${data.current_feed_rate}/kg` : 'Not set'}</strong></span>
      </div>

      {showFeedForm && (
        <form onSubmit={handleFeedRate} className="form-card" style={{ marginBottom: '1.5rem' }}>
          <h3>Update Weekly Feed Rate</h3>
          <div className="form-row">
            <div className="form-group">
              <label>Week Start Date *</label>
              <input type="date" value={feedForm.week_start_date} onChange={e => setFeedForm({ ...feedForm, week_start_date: e.target.value })} required />
            </div>
            <div className="form-group">
              <label>Rate per kg (₹) *</label>
              <input type="number" step="0.01" min="0" value={feedForm.rate_per_kg} onChange={e => setFeedForm({ ...feedForm, rate_per_kg: e.target.value })} required placeholder="e.g. 32.50" />
            </div>
            <div className="form-group">
              <label>Notes</label>
              <input value={feedForm.notes} onChange={e => setFeedForm({ ...feedForm, notes: e.target.value })} placeholder="Optional" />
            </div>
          </div>
          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={() => setShowFeedForm(false)}>Cancel</button>
            <button type="submit" className="btn btn-primary">Save Feed Rate</button>
          </div>
        </form>
      )}

      {data.feed_rates && data.feed_rates.length > 0 && (
        <details className="feed-history">
          <summary>Feed Rate History ({data.feed_rates.length} entries)</summary>
          <div className="table-wrapper" style={{ marginTop: '0.5rem' }}>
            <table>
              <thead><tr><th>Week Start</th><th>Rate (₹/kg)</th><th>Notes</th></tr></thead>
              <tbody>
                {data.feed_rates.map(fr => (
                  <tr key={fr.id}><td>{fr.week_start_date}</td><td>₹{fr.rate_per_kg}</td><td>{fr.notes || '—'}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}

      {/* ---- TODAY ---- */}
      <h2 className="section-title" style={{ marginTop: '2rem' }}>Today</h2>
      <div className="stats-grid">
        <div className="stat-card">
          <span className="stat-label">Active Farms</span>
          <span className="stat-value">{data.total_farms}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Active Flocks</span>
          <span className="stat-value">{data.total_active_flocks}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Live Birds</span>
          <span className="stat-value">{fmt(data.total_live_birds)}</span>
        </div>
        <div className="stat-card stat-alert">
          <span className="stat-label">Mortality Today</span>
          <span className="stat-value">{data.mortality_today}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Feed Today (kg)</span>
          <span className="stat-value">{fmtDec(data.feed_today)}</span>
        </div>
      </div>

      {/* ---- FARMS ---- */}
      <h2 className="section-title" style={{ marginTop: '2rem' }}>Farms</h2>
      {data.farms.length === 0 ? (
        <div className="empty-state">
          <p>No farms yet. Add your first farm to get started.</p>
          <Link to="/farms/new" className="btn btn-primary">+ Add Farm</Link>
        </div>
      ) : (
        <div className="card-grid">
          {data.farms.map(farm => (
            <Link to={`/farms/${farm.id}`} key={farm.id} className="farm-card">
              <h3>{farm.name}</h3>
              <p className="farm-meta">{farm.owner_name} &middot; {farm.location}</p>
              <p className="farm-meta">{farm.house_count} house(s)</p>
              {farm.active_flocks.length > 0 ? (
                <div className="flock-summary">
                  {farm.active_flocks.map(f => (
                    <div key={f.id} className="flock-mini">
                      <span>Day {f.age_days}</span>
                      <span>{f.live_birds.toLocaleString()} birds</span>
                      <span className={f.mortality_percentage > 5 ? 'text-danger' : 'text-ok'}>
                        {f.mortality_percentage}% mort.
                      </span>
                      <span>{f.fcr != null ? `FCR ${f.fcr}` : ''}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="farm-meta" style={{ marginTop: '0.5rem' }}>No active flocks</p>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
