import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { farmAPI } from '../api/client';

export default function FarmsList() {
  const [farms, setFarms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  useEffect(() => {
    farmAPI.list().then(res => {
      setFarms(res.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const filtered = farms.filter(f => {
    const q = search.toLowerCase();
    return (
      f.farm_code.toLowerCase().includes(q) ||
      f.name.toLowerCase().includes(q) ||
      f.owner_name.toLowerCase().includes(q) ||
      (f.region || '').toLowerCase().includes(q) ||
      (f.location || '').toLowerCase().includes(q)
    );
  });

  if (loading) return <div className="loading">Loading farms...</div>;

  return (
    <div className="page">
      <div className="page-header">
        <h1>Farms ({farms.length})</h1>
        <Link to="/farms/new" className="btn btn-primary">+ Add Farm</Link>
      </div>

      <div className="search-bar">
        <input
          type="text"
          placeholder="Search by code, name, owner or location..."
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        {search && <button className="search-clear" onClick={() => setSearch('')}>&times;</button>}
      </div>

      {filtered.length === 0 && search ? (
        <div className="empty-state">
          <p>No farms match "{search}"</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <p>No farms yet.</p>
          <Link to="/farms/new" className="btn btn-primary">+ Add Farm</Link>
        </div>
      ) : (
        <div className="card-grid">
          {filtered.map(farm => (
            <Link to={`/farms/${farm.id}`} key={farm.id} className="farm-card">
              <div className="farm-card-header">
                <span className="farm-code-badge">{farm.farm_code}</span>
                <h3>{farm.name}</h3>
              </div>
              <p className="farm-meta">{farm.owner_name} &middot; {farm.region ? `${farm.region} · ` : ''}{farm.location}</p>
              {farm.active_flocks.length > 0 ? (
                <div className="flock-summary">
                  {farm.active_flocks.map(f => (
                    <div key={f.id} className="flock-mini">
                      <span>Day {f.age_days}</span>
                      <span>{f.live_birds.toLocaleString()} birds</span>
                      <span className={f.mortality_percentage > 5 ? 'text-danger' : 'text-ok'}>{f.mortality_percentage}%</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="farm-meta" style={{ marginTop: '0.5rem' }}>No active flocks</p>
              )}
              {farm.closed_flocks && farm.closed_flocks.length > 0 && (
                <p className="farm-meta" style={{ marginTop: '0.25rem' }}>{farm.closed_flocks.length} previous batch{farm.closed_flocks.length > 1 ? 'es' : ''}</p>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
