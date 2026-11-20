import { FlockDetailSkeleton } from '../components/Skeletons';
import UnsavedPrompt from '../components/UnsavedPrompt';
import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { farmAPI, flockAPI, authAPI, hatcheryAPI, getErrorMessage } from '../api/client';
import { useAuth } from '../context/AuthContext';
import useFeedTypes from '../utils/useFeedTypes';
import DocumentsSection from '../components/DocumentsSection';
import FarmPerformanceHistory from '../components/FarmPerformanceHistory';
import { todayISO } from '../utils/dates';

export default function FarmDetail() {
  const { id } = useParams();
  const { canEditFarm, canManageFarm, isAdmin } = useAuth();
  const feedTypes = useFeedTypes();
  const [farm, setFarm] = useState(null);
  const [cumulative, setCumulative] = useState(null);
  const [supervisors, setSupervisors] = useState([]);
  const [showFlockForm, setShowFlockForm] = useState(false);
  const [showDetails, setShowDetails] = useState(false);
  const EMPTY_FLOCK = { placement_date: '', chick_count: '', supervisor: '', hatchery: '', doa_count: '', chick_weight_g: '' };
  const [flockForm, setFlockForm] = useState(EMPTY_FLOCK);
  const [hatcheries, setHatcheries] = useState([]);
  const [loadError, setLoadError] = useState('');

  const load = async () => {
    let farmRes;
    try {
      farmRes = await farmAPI.get(id);
    } catch (err) {
      setLoadError(err.response?.status === 404
        ? 'Farm not found — it may have been deleted, or it is outside your regions.'
        : getErrorMessage(err));
      return;
    }
    setFarm(farmRes.data);
    try {
      const cumRes = await farmAPI.cumulative(id);
      setCumulative(cumRes.data);
    } catch { setCumulative(null); }
    if (isAdmin) {   // the user list is admin-only
      try {
        const usersRes = await authAPI.listUsers();
        setSupervisors(usersRes.data.filter(u => u.role === 'supervisor'));
      } catch { /* ignore */ }
    }
  };

  useEffect(() => { load(); }, [id]);
  useEffect(() => { hatcheryAPI.list().then(r => setHatcheries(r.data.filter(h => h.active))).catch(() => {}); }, []);

  const handleCreateFlock = async (e) => {
    e.preventDefault();
    try {
      await flockAPI.create({
        farm: id,
        placement_date: flockForm.placement_date,
        chick_count: parseInt(flockForm.chick_count),
        supervisor: flockForm.supervisor || null,
        hatchery: flockForm.hatchery || null,
        doa_count: parseInt(flockForm.doa_count) || 0,
        chick_weight_g: flockForm.chick_weight_g || null,
      });
      setShowFlockForm(false);
      setFlockForm(EMPTY_FLOCK);
      load();
    } catch (err) {
      alert(getErrorMessage(err));
    }
  };

  if (loadError) return (
    <div className="page">
      <div className="error-msg" role="alert" style={{ marginBottom: '1rem' }}>{loadError}</div>
      <Link to="/farms" className="btn btn-primary">Back to Farms</Link>
    </div>
  );
  if (!farm) return <FlockDetailSkeleton />;

  const fmt = (n) => n != null ? Number(n).toLocaleString('en-IN') : '—';
  const fmtDec = (n) => n != null ? Number(n).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—';

  const activeFlocks = farm.active_flocks || [];
  const closedFlocks = farm.closed_flocks || [];

  return (
    <div className="page">
      <UnsavedPrompt when={showFlockForm} message="You have an unsaved flock placement form. Discard?" />
      {/* HEADER */}
      <div className="page-header">
        <div>
          <Link to="/farms" className="back-link">&larr; All Farms</Link>
          <h1><span className="farm-code-badge">{farm.farm_code}</span> {farm.name}</h1>
          <p className="farm-meta">{farm.owner_name} &middot; {farm.region} &middot; {farm.shed_type}{farm.supervisor_names && <> &middot; Supervisor: {farm.supervisor_names}</>}</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button className="btn btn-secondary" onClick={() => setShowDetails(!showDetails)}>
            {showDetails ? 'Hide' : 'Farm'} Details
          </button>
          {canManageFarm(farm.id) && <Link to={`/farms/${id}/edit`} className="btn btn-secondary">Edit</Link>}
          <button className="btn btn-primary" onClick={() => setShowFlockForm(!showFlockForm)}>+ New Flock</button>
        </div>
      </div>

      {/* FARM DETAILS TILE */}
      {showDetails && (
        <div className="farm-details-tile">
          <h3>Farm Details</h3>
          <div className="farm-details-grid">
            <div><span className="detail-label">Farm Code</span><span className="detail-value">{farm.farm_code}</span></div>
            <div><span className="detail-label">Owner</span><span className="detail-value">{farm.owner_name}</span></div>
            <div><span className="detail-label">Shed Type</span><span className="detail-value"><span className={`shed-badge shed-badge-${(farm.shed_type || 'open').toLowerCase()}`}>{farm.shed_type === 'EC' ? 'EC' : 'Open'}</span></span></div>
            <div><span className="detail-label">Region</span><span className="detail-value">{farm.region || '—'}</span></div>
            <div><span className="detail-label">Location</span><span className="detail-value">{farm.location || '—'}</span></div>
            <div><span className="detail-label">Capacity</span><span className="detail-value">{farm.capacity?.toLocaleString()} birds</span></div>
            <div><span className="detail-label">Placement Range</span><span className="detail-value">{Math.floor(farm.capacity * 0.95).toLocaleString()} — {Math.floor(farm.capacity * 1.05).toLocaleString()}</span></div>
            <div><span className="detail-label">Total Batches</span><span className="detail-value">{activeFlocks.length + closedFlocks.length}</span></div>
            <div><span className="detail-label">Active</span><span className="detail-value">{activeFlocks.length}</span></div>
            <div><span className="detail-label">Completed</span><span className="detail-value">{closedFlocks.length}</span></div>
          </div>
        </div>
      )}

      {/* NEW FLOCK FORM */}
      {showFlockForm && (() => {
        const activeChicks = (farm.active_flocks || []).reduce((sum, f) => sum + f.chick_count, 0);
        const remaining = farm.capacity - activeChicks;
        return (
          <form onSubmit={handleCreateFlock} className="form-card" style={{ marginBottom: '1.5rem' }}>
            <h3>Place New Flock</h3>
            {activeChicks > 0 && <p className="farm-meta" style={{ marginBottom: '0.75rem' }}>Active flocks: {activeChicks.toLocaleString()} chicks — Remaining capacity: {remaining.toLocaleString()}</p>}
            <div className="form-row">
              <div className="form-group">
                <label>Placement Date *</label>
                <input type="date" value={flockForm.placement_date} onChange={e => setFlockForm({ ...flockForm, placement_date: e.target.value })} required max={todayISO()} />
              </div>
              <div className="form-group">
                <label>Chicks Placed *</label>
                <input type="text" inputMode="numeric" pattern="[0-9]*" value={flockForm.chick_count} onChange={e => setFlockForm({ ...flockForm, chick_count: e.target.value })} required />
                <small className="field-hint">Farm capacity: {farm.capacity?.toLocaleString()} | Available: {remaining.toLocaleString()}</small>
              </div>
              <div className="form-group">
                <label>Supervisor</label>
                <select value={flockForm.supervisor} onChange={e => setFlockForm({ ...flockForm, supervisor: e.target.value })}>
                  <option value="">Select supervisor...</option>
                  {supervisors.map(s => (
                    <option key={s.id} value={s.id}>{s.first_name} {s.last_name} ({s.username})</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label>Hatchery</label>
                <select value={flockForm.hatchery} onChange={e => setFlockForm({ ...flockForm, hatchery: e.target.value })}>
                  <option value="">Select hatchery...</option>
                  {hatcheries.map(h => <option key={h.id} value={h.id}>{h.name}</option>)}
                </select>
                <small className="field-hint">Where the chicks came from</small>
              </div>
              <div className="form-group">
                <label>Dead on Arrival</label>
                <input type="text" inputMode="numeric" pattern="[0-9]*" value={flockForm.doa_count} placeholder="0" onChange={e => setFlockForm({ ...flockForm, doa_count: e.target.value })} />
                <small className="field-hint">Chicks dead in the boxes (not deducted from chicks placed)</small>
              </div>
              <div className="form-group">
                <label>Avg Chick Weight (g)</label>
                <input type="text" inputMode="decimal" value={flockForm.chick_weight_g} placeholder="e.g. 40" onChange={e => setFlockForm({ ...flockForm, chick_weight_g: e.target.value })} />
                <small className="field-hint">Weigh one box ÷ chicks in it</small>
              </div>
            </div>
            <div className="form-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setShowFlockForm(false)}>Cancel</button>
              <button type="submit" className="btn btn-primary">Place Flock</button>
            </div>
          </form>
        );
      })()}

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
              <p className="farm-meta">Placed: {flock.placement_date} &middot; {flock.chick_count.toLocaleString()} chicks{flock.supervisor_name && <> &middot; {flock.supervisor_name}</>}</p>
              <div className="flock-stats">
                <div><strong>{flock.live_birds.toLocaleString()}</strong><br /><small>Live</small></div>
                <div className={flock.mortality_percentage > 5 ? 'text-danger' : ''}>
                  <strong>{flock.mortality_percentage}%</strong><br /><small>Mortality</small>
                </div>
                <div><strong>{parseFloat(flock.total_feed_kg).toLocaleString()} kg</strong><br /><small>Feed</small></div>
                <div><strong>{flock.fcr ?? '—'}</strong><br /><small>FCR</small></div>
              </div>
              {flock.flock_feed_stock && (
                <div className="flock-stock-row">
                  <small>Stock:</small>
                  {Object.entries(flock.flock_feed_stock.by_type || {}).map(([k, v]) => (
                    <span key={k} className="feed-badge-sm">{feedTypes.code(k)}:{v}</span>
                  ))}
                  <span className="feed-badge-sm"><strong>{flock.flock_feed_stock.total}</strong></span>
                </div>
              )}
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
            {isAdmin && <div className="stat-card stat-success">
              <span className="stat-label">Sale Amount</span>
              <span className="stat-value">₹{fmtDec(cumulative.total_sale_amount)}</span>
            </div>}
            <div className="stat-card">
              <span className="stat-label">Feed</span>
              <span className="stat-value">{fmtDec(cumulative.total_feed_kg)} kg</span>
              <span className="stat-sub">{cumulative.total_feed_bags} bags</span>
            </div>
            <div className="stat-card stat-info">
              <span className="stat-label">FCR</span>
              <span className="stat-value">{cumulative.fcr ?? '—'}</span>
            </div>
            {isAdmin && <div className="stat-card stat-info">
              <span className="stat-label">Feed Cost / kg</span>
              <span className="stat-value">{cumulative.cost_per_kg_production != null ? `₹${fmtDec(cumulative.cost_per_kg_production)}` : '—'}</span>
            </div>}
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

      <FarmPerformanceHistory farmId={farm.id} />
      <DocumentsSection farmId={farm.id} canEdit={canEditFarm(farm.id)} />
    </div>
  );
}
