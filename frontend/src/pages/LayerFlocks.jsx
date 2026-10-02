import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { layerAPI, getErrorMessage } from '../api/client';

export default function LayerFlocks() {
  const [flocks, setFlocks] = useState([]);
  const [farms, setFarms] = useState([]);
  const [showFlock, setShowFlock] = useState(false);
  const [showFarm, setShowFarm] = useState(false);
  const [flockForm, setFlockForm] = useState({ farm: '', name: '', placement_date: new Date().toISOString().slice(0, 10), bird_count: '' });
  const [farmForm, setFarmForm] = useState({ name: '', code: '', location: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const load = () => {
    Promise.all([layerAPI.flocks(), layerAPI.farms()]).then(([fl, fa]) => {
      setFlocks(fl.data); setFarms(fa.data); setLoading(false);
    }).catch(() => setLoading(false));
  };
  useEffect(load, []);

  const fmt = (n) => Number(n).toLocaleString('en-IN', { maximumFractionDigits: 2 });

  const submitFarm = async (e) => {
    e.preventDefault(); setError('');
    try {
      await layerAPI.createFarm(farmForm);
      setShowFarm(false); setFarmForm({ name: '', code: '', location: '' }); load();
    } catch (err) { setError(getErrorMessage(err)); }
  };

  const submitFlock = async (e) => {
    e.preventDefault(); setError('');
    try {
      await layerAPI.createFlock({ ...flockForm, bird_count: parseInt(flockForm.bird_count) });
      setShowFlock(false); setFlockForm({ farm: '', name: '', placement_date: new Date().toISOString().slice(0, 10), bird_count: '' }); load();
    } catch (err) { setError(getErrorMessage(err)); }
  };

  if (loading) return <div className="loading">Loading…</div>;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <button className="back-link" onClick={() => navigate('/layer')}>&larr; Layer Farm</button>
          <h1>Flocks</h1>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn btn-primary" onClick={() => { setShowFlock(!showFlock); setShowFarm(false); }}>+ Flock</button>
          <button className="btn btn-secondary" onClick={() => { setShowFarm(!showFarm); setShowFlock(false); }}>+ Farm</button>
        </div>
      </div>

      {error && <div className="error-msg">{error}</div>}

      {showFarm && (
        <form onSubmit={submitFarm} className="form-card" style={{ maxWidth: 480, marginBottom: '1.5rem' }}>
          <h3>Add Farm / Shed</h3>
          <div className="form-row">
            <div className="form-group"><label>Name *</label><input value={farmForm.name} onChange={e => setFarmForm({ ...farmForm, name: e.target.value })} required /></div>
            <div className="form-group"><label>Code *</label><input value={farmForm.code} onChange={e => setFarmForm({ ...farmForm, code: e.target.value })} required /></div>
          </div>
          <div className="form-group"><label>Location</label><input value={farmForm.location} onChange={e => setFarmForm({ ...farmForm, location: e.target.value })} /></div>
          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={() => setShowFarm(false)}>Cancel</button>
            <button type="submit" className="btn btn-primary">Save Farm</button>
          </div>
        </form>
      )}

      {showFlock && (
        <form onSubmit={submitFlock} className="form-card" style={{ maxWidth: 480, marginBottom: '1.5rem' }}>
          <h3>Place New Flock</h3>
          {farms.length === 0 && <p className="farm-meta">Add a farm first.</p>}
          <div className="form-group">
            <label>Farm *</label>
            <select value={flockForm.farm} onChange={e => setFlockForm({ ...flockForm, farm: e.target.value })} required>
              <option value="">Select farm…</option>
              {farms.map(f => <option key={f.id} value={f.id}>{f.code} — {f.name}</option>)}
            </select>
          </div>
          <div className="form-row">
            <div className="form-group"><label>Flock name *</label><input value={flockForm.name} onChange={e => setFlockForm({ ...flockForm, name: e.target.value })} required placeholder="e.g. Batch-2026-A" /></div>
            <div className="form-group"><label>Birds placed *</label><input type="text" inputMode="numeric" value={flockForm.bird_count} onChange={e => setFlockForm({ ...flockForm, bird_count: e.target.value })} required /></div>
          </div>
          <div className="form-group"><label>Placement date *</label><input type="date" value={flockForm.placement_date} max={new Date().toISOString().slice(0, 10)} onChange={e => setFlockForm({ ...flockForm, placement_date: e.target.value })} required /></div>
          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={() => setShowFlock(false)}>Cancel</button>
            <button type="submit" className="btn btn-primary">Place Flock</button>
          </div>
        </form>
      )}

      {flocks.length ? (
        <div className="table-wrapper">
          <table className="report-table">
            <thead><tr><th>Flock</th><th>Farm</th><th>Status</th><th>Age</th><th>Birds</th><th>Live</th><th>Cost</th><th>Egg Rev.</th></tr></thead>
            <tbody>
              {flocks.map(f => (
                <tr key={f.id}>
                  <td><Link to={`/layer/flocks/${f.id}`}>{f.name}</Link></td>
                  <td>{f.farm_code}</td>
                  <td><span className={`wa-badge ${f.status === 'ACTIVE' ? 'wa-sent' : 'wa-disabled'}`}>{f.status}</span></td>
                  <td>{f.age_days}d</td>
                  <td>{fmt(f.bird_count)}</td>
                  <td>{fmt(f.live_birds)}</td>
                  <td>₹{fmt(f.total_cost)}</td>
                  <td className="text-ok">₹{fmt(f.egg_revenue)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <p className="farm-meta">No flocks yet.</p>}
    </div>
  );
}
