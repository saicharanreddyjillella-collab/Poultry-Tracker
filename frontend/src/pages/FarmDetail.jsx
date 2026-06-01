import { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { farmAPI, flockAPI } from '../api/client';

export default function FarmDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [farm, setFarm] = useState(null);
  const [showFlockForm, setShowFlockForm] = useState(false);
  const [flockForm, setFlockForm] = useState({
    breed: '', placement_date: '', chick_count: '',
  });

  const load = () => farmAPI.get(id).then(res => setFarm(res.data));

  useEffect(() => { load(); }, [id]);

  const handleCreateFlock = async (e) => {
    e.preventDefault();
    await flockAPI.create({ ...flockForm, farm: id, chick_count: parseInt(flockForm.chick_count) });
    setShowFlockForm(false);
    setFlockForm({ breed: '', placement_date: '', chick_count: '' });
    load();
  };

  if (!farm) return <div className="loading">Loading...</div>;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>{farm.name}</h1>
          <p className="farm-meta">{farm.owner_name} &middot; {farm.location} &middot; {farm.house_count} house(s)</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <Link to={`/farms/${id}/edit`} className="btn btn-secondary">Edit Farm</Link>
          <button className="btn btn-primary" onClick={() => setShowFlockForm(!showFlockForm)}>
            + New Flock
          </button>
        </div>
      </div>

      {showFlockForm && (
        <form onSubmit={handleCreateFlock} className="form-card" style={{ marginBottom: '1.5rem' }}>
          <h3>Place New Flock</h3>
          <div className="form-row">
            <div className="form-group">
              <label>Breed</label>
              <input value={flockForm.breed} onChange={e => setFlockForm({ ...flockForm, breed: e.target.value })} placeholder="e.g. Cobb 400" />
            </div>
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

      <h2>Active Flocks</h2>
      {farm.active_flocks && farm.active_flocks.length > 0 ? (
        <div className="card-grid">
          {farm.active_flocks.map(flock => (
            <Link to={`/flocks/${flock.id}`} key={flock.id} className="flock-card">
              <div className="flock-header">
                <span className="flock-breed">{flock.breed || 'Unknown breed'}</span>
                <span className="flock-age">Day {flock.age_days}</span>
              </div>
              <div className="flock-stats">
                <div><strong>{flock.chick_count.toLocaleString()}</strong><br /><small>Placed</small></div>
                <div><strong>{flock.live_birds.toLocaleString()}</strong><br /><small>Live</small></div>
                <div className={flock.mortality_percentage > 5 ? 'text-danger' : ''}>
                  <strong>{flock.mortality_percentage}%</strong><br /><small>Mortality</small>
                </div>
                <div><strong>{parseFloat(flock.total_feed_kg).toLocaleString()} kg</strong><br /><small>Feed</small></div>
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <p>No active flocks. Place a new flock to start tracking.</p>
        </div>
      )}
    </div>
  );
}
