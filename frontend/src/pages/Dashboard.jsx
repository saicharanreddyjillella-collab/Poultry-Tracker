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

  if (loading) return <div className="loading">Loading...</div>;
  if (!data) return <div className="empty-state">Could not load dashboard. Is the Django server running?</div>;

  const fmt = (n) => n != null ? Number(n).toLocaleString('en-IN') : '—';
  const fmtDec = (n) => n != null ? Number(n).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—';
  const feedToday = data.feed_today || {};
  const todayTotalBags = (feedToday.bpsc_bags || 0) + (feedToday.bsc_bags || 0) + (feedToday.bfp_bags || 0);

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Today's Dashboard</h1>
          <p className="farm-meta">{new Date().toLocaleDateString('en-IN', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn btn-secondary" onClick={() => setShowFeedForm(!showFeedForm)}>Update Feed Rate</button>
          <Link to="/farms/new" className="btn btn-primary">+ Add Farm</Link>
        </div>
      </div>

      {/* TODAY STATS */}
      <div className="stats-grid stats-grid-wide">
        <div className="stat-card stat-highlight">
          <span className="stat-label">Active Farms</span>
          <span className="stat-value">{data.total_farms}</span>
        </div>
        <div className="stat-card stat-highlight">
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
      </div>

      {/* TODAY FEED */}
      <h2 className="section-title" style={{ marginTop: '1.5rem' }}>Feed Today</h2>
      <div className="stats-grid">
        <div className="stat-card feed-card-bpsc">
          <span className="stat-label">BPSC</span>
          <span className="stat-value">{fmtDec(feedToday.bpsc_bags)} bags</span>
          <span className="stat-sub">{fmtDec((feedToday.bpsc_bags || 0) * 50)} kg</span>
        </div>
        <div className="stat-card feed-card-bsc">
          <span className="stat-label">BSC</span>
          <span className="stat-value">{fmtDec(feedToday.bsc_bags)} bags</span>
          <span className="stat-sub">{fmtDec((feedToday.bsc_bags || 0) * 50)} kg</span>
        </div>
        <div className="stat-card feed-card-bfp">
          <span className="stat-label">BFP</span>
          <span className="stat-value">{fmtDec(feedToday.bfp_bags)} bags</span>
          <span className="stat-sub">{fmtDec((feedToday.bfp_bags || 0) * 50)} kg</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Total Feed Today</span>
          <span className="stat-value">{fmtDec(todayTotalBags)} bags</span>
          <span className="stat-sub">{fmtDec(todayTotalBags * 50)} kg</span>
        </div>
      </div>

      {/* FEED RATE */}
      {data.latest_feed_rates && Object.keys(data.latest_feed_rates).length > 0 && (
        <div className="feed-rate-bar" style={{ marginTop: '1rem' }}>
          Current Rates:
          {data.latest_feed_rates.BPSC && <span> <strong>BPSC ₹{data.latest_feed_rates.BPSC}/kg</strong></span>}
          {data.latest_feed_rates.BSC && <span> · <strong>BSC ₹{data.latest_feed_rates.BSC}/kg</strong></span>}
          {data.latest_feed_rates.BFP && <span> · <strong>BFP ₹{data.latest_feed_rates.BFP}/kg</strong></span>}
        </div>
      )}

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

      {/* FARMS LIST */}
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
              <div className="farm-card-header">
                <span className="farm-code-badge">{farm.farm_code}</span>
                <h3>{farm.name}</h3>
                <span className={`shed-badge shed-badge-${(farm.shed_type || 'open').toLowerCase()}`} style={{ marginLeft: 'auto' }}>{farm.shed_type === 'EC' ? 'EC' : 'Open'}</span>
              </div>
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
