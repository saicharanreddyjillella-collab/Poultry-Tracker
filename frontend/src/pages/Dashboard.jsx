import { useState, useEffect } from 'react';
import { DashboardSkeleton } from '../components/Skeletons';
import { Link } from 'react-router-dom';
import { dashboardAPI } from '../api/client';

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    dashboardAPI.get().then(res => {
      setData(res.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) return <DashboardSkeleton />;
  if (!data) return <div className="empty-state">Could not load dashboard. Is the Django server running?</div>;

  const fmt = (n) => n != null ? Number(n).toLocaleString('en-IN') : '—';
  const fmtDec = (n) => n != null ? Number(n).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—';
  const feedToday = data.feed_today || {};
  const todayTotalBags = (feedToday.bpsc_bags || 0) + (feedToday.bsc_bags || 0) + (feedToday.bfp_bags || 0);
  const rates = data.latest_feed_rates || {};

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Today's Dashboard</h1>
          <p className="farm-meta">{new Date().toLocaleDateString('en-IN', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</p>
        </div>
        <Link to="/farms/new" className="btn btn-primary">+ Add Farm</Link>
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

      {/* FEED RATES */}
      {Object.keys(rates).length > 0 && (
        <div className="feed-rate-bar" style={{ marginTop: '1rem' }}>
          Current Rates:
          {rates.BPSC && <span> <strong>BPSC ₹{rates.BPSC}/kg</strong></span>}
          {rates.BSC && <span> · <strong>BSC ₹{rates.BSC}/kg</strong></span>}
          {rates.BFP && <span> · <strong>BFP ₹{rates.BFP}/kg</strong></span>}
          <Link to="/feed" style={{ marginLeft: '0.5rem', fontSize: '0.85rem' }}>Update →</Link>
        </div>
      )}

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
