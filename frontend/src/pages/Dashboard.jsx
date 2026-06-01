import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { dashboardAPI, feedRateAPI } from '../api/client';

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showFeedForm, setShowFeedForm] = useState(false);
  const [feedForm, setFeedForm] = useState({
    week_start_date: new Date().toISOString().split('T')[0],
    feed_type: 'BFP',
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
    setFeedForm({ week_start_date: new Date().toISOString().split('T')[0], feed_type: 'BFP', rate_per_kg: '', notes: '' });
    load();
  };

  if (loading) return <div className="loading">Loading dashboard...</div>;
  if (!data) return <div className="empty-state">Could not load dashboard. Is the Django server running?</div>;

  const fmt = (n) => n != null ? Number(n).toLocaleString('en-IN') : '—';
  const fmtDec = (n, d = 2) => n != null ? Number(n).toLocaleString('en-IN', { minimumFractionDigits: d, maximumFractionDigits: d }) : '—';
  const rates = data.latest_feed_rates || {};
  const feedToday = data.feed_today || {};
  const fb = data.feed_by_type || {};

  return (
    <div className="page">
      <div className="page-header">
        <h1>Integration Dashboard</h1>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn btn-secondary" onClick={() => setShowFeedForm(!showFeedForm)}>Update Feed Rate</button>
          <Link to="/farms/new" className="btn btn-primary">+ Add Farm</Link>
        </div>
      </div>

      {/* LIFETIME SUMMARY */}
      <h2 className="section-title">Lifetime Summary</h2>
      <div className="stats-grid stats-grid-wide">
        <div className="stat-card stat-highlight">
          <span className="stat-label">Birds Placed</span>
          <span className="stat-value">{fmt(data.total_birds_placed)}</span>
        </div>
        <div className="stat-card stat-success">
          <span className="stat-label">Sold (Birds)</span>
          <span className="stat-value">{fmt(data.total_sold_birds)}</span>
        </div>
        <div className="stat-card stat-success">
          <span className="stat-label">Sold (kg)</span>
          <span className="stat-value">{fmtDec(data.total_sold_weight_kg)} kg</span>
        </div>
        <div className="stat-card stat-success">
          <span className="stat-label">Sale Amount</span>
          <span className="stat-value">₹{fmtDec(data.total_sale_amount)}</span>
        </div>
        <div className="stat-card stat-alert">
          <span className="stat-label">Mortality</span>
          <span className="stat-value">{fmt(data.total_mortality)} <small>({data.mortality_percentage}%)</small></span>
        </div>
        <div className="stat-card stat-info">
          <span className="stat-label">FCR</span>
          <span className="stat-value">{data.fcr ?? '—'}</span>
        </div>
        <div className="stat-card stat-info">
          <span className="stat-label">Feed Cost / kg Production</span>
          <span className="stat-value">{data.cost_per_kg_production != null ? `₹${fmtDec(data.cost_per_kg_production)}` : '—'}</span>
        </div>
        <div className="stat-card stat-info">
          <span className="stat-label">Total Feed Cost</span>
          <span className="stat-value">₹{fmtDec(data.total_feed_cost)}</span>
        </div>
      </div>

      {/* FEED BREAKDOWN */}
      <h2 className="section-title" style={{ marginTop: '1.5rem' }}>Feed Consumed (by type)</h2>
      <div className="stats-grid">
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

      {/* FEED RATE FORM */}
      {showFeedForm && (
        <form onSubmit={handleFeedRate} className="form-card" style={{ margin: '1rem 0 1.5rem' }}>
          <h3>Update Feed Rate</h3>
          <div className="form-row">
            <div className="form-group">
              <label>Week Start Date *</label>
              <input type="date" value={feedForm.week_start_date} onChange={e => setFeedForm({ ...feedForm, week_start_date: e.target.value })} required />
            </div>
            <div className="form-group">
              <label>Feed Type *</label>
              <select value={feedForm.feed_type} onChange={e => setFeedForm({ ...feedForm, feed_type: e.target.value })}>
                <option value="BPSC">BPSC (Pre-Starter)</option>
                <option value="BSC">BSC (Starter)</option>
                <option value="BFP">BFP (Finisher)</option>
              </select>
            </div>
            <div className="form-group">
              <label>Rate per kg (₹) *</label>
              <input type="number" step="0.01" min="0" value={feedForm.rate_per_kg} onChange={e => setFeedForm({ ...feedForm, rate_per_kg: e.target.value })} required placeholder="e.g. 32.50" />
            </div>
          </div>
          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={() => setShowFeedForm(false)}>Cancel</button>
            <button type="submit" className="btn btn-primary">Save</button>
          </div>
        </form>
      )}

      {data.feed_rates && data.feed_rates.length > 0 && (
        <details className="feed-history">
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

      {/* TODAY */}
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
        <div className="stat-card feed-card-bpsc">
          <span className="stat-label">BPSC Today</span>
          <span className="stat-value">{fmtDec(feedToday.bpsc_bags)} bags</span>
        </div>
        <div className="stat-card feed-card-bsc">
          <span className="stat-label">BSC Today</span>
          <span className="stat-value">{fmtDec(feedToday.bsc_bags)} bags</span>
        </div>
        <div className="stat-card feed-card-bfp">
          <span className="stat-label">BFP Today</span>
          <span className="stat-value">{fmtDec(feedToday.bfp_bags)} bags</span>
        </div>
      </div>

      {/* FARMS */}
      <h2 className="section-title" style={{ marginTop: '2rem' }}>Farms</h2>
      {data.farms.length === 0 ? (
        <div className="empty-state">
          <p>No farms yet.</p>
          <Link to="/farms/new" className="btn btn-primary">+ Add Farm</Link>
        </div>
      ) : (
        <div className="card-grid">
          {data.farms.map(farm => (
            <Link to={`/farms/${farm.id}`} key={farm.id} className="farm-card">
              <h3>{farm.name}</h3>
              <p className="farm-meta">{farm.owner_name} &middot; {farm.location}</p>
              {farm.active_flocks.length > 0 ? (
                <div className="flock-summary">
                  {farm.active_flocks.map(f => (
                    <div key={f.id} className="flock-mini">
                      <span>Day {f.age_days}</span>
                      <span>{f.live_birds.toLocaleString()} birds</span>
                      <span className={f.mortality_percentage > 5 ? 'text-danger' : 'text-ok'}>{f.mortality_percentage}%</span>
                      <span className={`feed-badge feed-badge-${(f.feed_schedule_status?.current_feed_type || '').toLowerCase()}`}>
                        {f.feed_schedule_status?.current_feed_type}
                      </span>
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
