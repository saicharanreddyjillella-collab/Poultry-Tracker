import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { farmAPI, flockAPI } from '../api/client';

export default function FarmDetail() {
  const { id } = useParams();
  const [farm, setFarm] = useState(null);
  const [cumulative, setCumulative] = useState(null);
  const [showFlockForm, setShowFlockForm] = useState(false);
  const [showDetails, setShowDetails] = useState(false);
  const [flockForm, setFlockForm] = useState({ placement_date: '', chick_count: '' });

  const load = async () => {
    const farmRes = await farmAPI.get(id);
    setFarm(farmRes.data);
    try {
      const cumRes = await farmAPI.cumulative(id);
      setCumulative(cumRes.data);
    } catch { setCumulative(null); }
  };

  useEffect(() => { load(); }, [id]);

  const handleCreateFlock = async (e) => {
    e.preventDefault();
    await flockAPI.create({ ...flockForm, farm: id, chick_count: parseInt(flockForm.chick_count) });
    setShowFlockForm(false);
    setFlockForm({ placement_date: '', chick_count: '' });
    load();
  };

  if (!farm) return <div className="loading">Loading...</div>;

  const fmt = (n) => n != null ? Number(n).toLocaleString('en-IN') : '—';
  const fmtDec = (n) => n != null ? Number(n).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—';

  const activeFlocks = farm.active_flocks || [];
  const closedFlocks = farm.closed_flocks || [];

  return (
    <div className="page">
      {/* HEADER */}
      <div className="page-header">
        <div>
          <Link to="/farms" className="back-link">&larr; All Farms</Link>
          <h1><span className="farm-code-badge">{farm.farm_code}</span> {farm.name}</h1>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button className="btn btn-secondary" onClick={() => setShowDetails(!showDetails)}>
            {showDetails ? 'Hide' : 'Farm'} Details
          </button>
          <Link to={`/farms/${id}/edit`} className="btn btn-secondary">Edit</Link>
          <button className="btn btn-primary" onClick={() => setShowFlockForm(!showFlockForm)}>
            + New Flock
          </button>
        </div>
      </div>

      {/* FARM DETAILS TILE */}
      {showDetails && (
        <div className="farm-details-tile">
          <h3>Farm Details</h3>
          <div className="farm-details-grid">
            <div><span className="detail-label">Farm Code</span><span className="detail-value">{farm.farm_code}</span></div>
            <div><span className="detail-label">Owner</span><span className="detail-value">{farm.owner_name}</span></div>
            <div><span className="detail-label">Location</span><span className="detail-value">{farm.location || '—'}</span></div>
            <div><span className="detail-label">Houses</span><span className="detail-value">{farm.house_count}</span></div>
            <div><span className="detail-label">Total Batches</span><span className="detail-value">{activeFlocks.length + closedFlocks.length}</span></div>
            <div><span className="detail-label">Active</span><span className="detail-value">{activeFlocks.length}</span></div>
            <div><span className="detail-label">Completed</span><span className="detail-value">{closedFlocks.length}</span></div>
          </div>
        </div>
      )}

      {/* NEW FLOCK FORM */}
      {showFlockForm && (
        <form onSubmit={handleCreateFlock} className="form-card" style={{ marginBottom: '1.5rem' }}>
          <h3>Place New Flock</h3>
          <div className="form-row">
            <div className="form-group">
              <label>Placement Date *</label>
              <input type="date" value={flockForm.placement_date} onChange={e => setFlockForm({ ...flockForm, placement_date: e.target.value })} required />
            </div>
            <div className="form-group">
              <label>Chicks Placed *</label>
              <input type="number" min="1" value={flockForm.chick_count} onChange={e => setFlockForm({ ...flockForm, chick_count: e.target.value })} required placeholder="e.g. 5000" />
            </div>
          </div>
          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={() => setShowFlockForm(false)}>Cancel</button>
            <button type="submit" className="btn btn-primary">Place Flock</button>
          </div>
        </form>
      )}

      {/* CURRENT FLOCK (active) */}
      <h2 className="section-title">Current Flock</h2>
      {activeFlocks.length > 0 ? (
        <div className="card-grid" style={{ marginBottom: '2rem' }}>
          {activeFlocks.map(flock => (
            <Link to={`/flocks/${flock.id}`} key={flock.id} className="flock-card flock-card-active">
              <div className="flock-header">
                <span className="flock-badge-active">ACTIVE</span>
                <span className="flock-age">Day {flock.age_days}</span>
              </div>
              <p className="farm-meta">Placed: {flock.placement_date} &middot; {flock.chick_count.toLocaleString()} chicks</p>
              <div className="flock-stats">
                <div><strong>{flock.live_birds.toLocaleString()}</strong><br /><small>Live</small></div>
                <div className={flock.mortality_percentage > 5 ? 'text-danger' : ''}>
                  <strong>{flock.mortality_percentage}%</strong><br /><small>Mortality</small>
                </div>
                <div><strong>{parseFloat(flock.total_feed_kg).toLocaleString()} kg</strong><br /><small>Feed</small></div>
                <div><strong>{flock.fcr ?? '—'}</strong><br /><small>FCR</small></div>
              </div>
              <div style={{ marginTop: '0.5rem' }}>
                <span className={`feed-badge feed-badge-${(flock.feed_schedule_status?.current_feed_type || '').toLowerCase()}`}>
                  {flock.feed_schedule_status?.current_feed_type}
                </span>
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <div className="empty-state" style={{ marginBottom: '2rem' }}>
          <p>No active flock. Place a new flock to start tracking.</p>
        </div>
      )}

      {/* CUMULATIVE — all closed flocks */}
      {cumulative && cumulative.closed_flock_count > 0 && (
        <>
          <h2 className="section-title">Farm Cumulative ({cumulative.closed_flock_count} completed batch{cumulative.closed_flock_count > 1 ? 'es' : ''})</h2>
          <div className="stats-grid stats-grid-wide" style={{ marginBottom: '1.5rem' }}>
            <div className="stat-card stat-highlight">
              <span className="stat-label">Birds Placed</span>
              <span className="stat-value">{fmt(cumulative.total_birds_placed)}</span>
            </div>
            <div className="stat-card stat-alert">
              <span className="stat-label">Mortality</span>
              <span className="stat-value">{fmt(cumulative.total_mortality)} <small>({cumulative.mortality_pct}%)</small></span>
            </div>
            <div className="stat-card stat-success">
              <span className="stat-label">Sold (Birds)</span>
              <span className="stat-value">{fmt(cumulative.total_sold_birds)}</span>
            </div>
            <div className="stat-card stat-success">
              <span className="stat-label">Sold (kg)</span>
              <span className="stat-value">{fmtDec(cumulative.total_sold_weight_kg)} kg</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Avg Bird Wt</span>
              <span className="stat-value">{cumulative.avg_bird_weight_kg ?? '—'} kg</span>
            </div>
            <div className="stat-card stat-success">
              <span className="stat-label">Sale Amount</span>
              <span className="stat-value">₹{fmtDec(cumulative.total_sale_amount)}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Feed</span>
              <span className="stat-value">{fmtDec(cumulative.total_feed_kg)} kg</span>
              <span className="stat-sub">{cumulative.total_feed_bags} bags</span>
            </div>
            <div className="stat-card stat-info">
              <span className="stat-label">FCR</span>
              <span className="stat-value">{cumulative.fcr ?? '—'}</span>
            </div>
            <div className="stat-card stat-info">
              <span className="stat-label">Feed Cost / kg</span>
              <span className="stat-value">{cumulative.cost_per_kg_production != null ? `₹${fmtDec(cumulative.cost_per_kg_production)}` : '—'}</span>
            </div>
          </div>
        </>
      )}

      {/* PREVIOUS FLOCKS (closed) */}
      {closedFlocks.length > 0 && (
        <>
          <h2 className="section-title">Previous Batches</h2>
          <div className="card-grid">
            {closedFlocks.map(flock => (
              <Link to={`/flocks/${flock.id}`} key={flock.id} className="flock-card flock-card-closed">
                <div className="flock-header">
                  <span className="flock-badge-closed">COMPLETED</span>
                  <span className="flock-age">{flock.age_days} days</span>
                </div>
                <p className="farm-meta">Placed: {flock.placement_date} &middot; {flock.chick_count.toLocaleString()} chicks</p>
                <div className="flock-stats">
                  <div><strong>{flock.total_sold_birds.toLocaleString()}</strong><br /><small>Sold</small></div>
                  <div><strong>{parseFloat(flock.total_sold_weight_kg).toLocaleString()} kg</strong><br /><small>Weight</small></div>
                  <div className={flock.mortality_percentage > 5 ? 'text-danger' : ''}>
                    <strong>{flock.mortality_percentage}%</strong><br /><small>Mortality</small>
                  </div>
                  <div><strong>{flock.fcr ?? '—'}</strong><br /><small>FCR</small></div>
                </div>
              </Link>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
