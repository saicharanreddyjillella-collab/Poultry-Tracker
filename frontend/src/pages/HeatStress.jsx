import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { insightsAPI, regionLocationAPI, getErrorMessage } from '../api/client';
import { useAuth } from '../context/AuthContext';
import '../styles/insights.css';

const LEVEL_TEXT = { none: 'OK', watch: 'Watch', danger: 'Danger', emergency: 'Emergency' };
const dayLabel = (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' });
const Level = ({ level }) => <span className={`heat heat-${level}`}>{LEVEL_TEXT[level]}</span>;

function RegionLocations({ onSaved }) {
  const [rows, setRows] = useState([]);
  const [edits, setEdits] = useState({});
  const [msg, setMsg] = useState('');
  const load = () => regionLocationAPI.list().then(r => setRows(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const value = (region, k) => edits[region]?.[k] ?? rows.find(r => r.region === region)?.[k] ?? '';
  const set = (region, k, v) => setEdits(e => ({ ...e, [region]: { ...e[region], [k]: v } }));
  const here = (region) => navigator.geolocation?.getCurrentPosition(
    p => setEdits(e => ({ ...e, [region]: { latitude: p.coords.latitude.toFixed(5), longitude: p.coords.longitude.toFixed(5) } })),
    () => setMsg('Could not read your location — allow location access, or type the numbers.'));
  const save = async (region) => {
    setMsg('');
    try {
      await regionLocationAPI.save(region, value(region, 'latitude'), value(region, 'longitude'));
      setEdits(e => { const n = { ...e }; delete n[region]; return n; });
      setMsg(`Saved ${region}.`);
      load(); onSaved();
    } catch (err) { setMsg(getErrorMessage(err)); }
  };

  return (
    <section style={{ marginTop: '2rem' }}>
      <h2>Region locations</h2>
      <p className="muted">One map point per region is used for its weather. In Google Maps, long-press the middle of the
        region and copy the two numbers (e.g. 17.38500, 78.48670) — or tap “Use my location” while you are there.</p>
      {msg && <div className="alert-banner">{msg}</div>}
      {rows.map(r => (
        <div className="loc-row" key={r.region} data-region={r.region}>
          <strong>{r.region}</strong>
          <div className="form-group"><label>Latitude</label>
            <input value={value(r.region, 'latitude')} onChange={e => set(r.region, 'latitude', e.target.value)} placeholder="17.38500" inputMode="decimal" /></div>
          <div className="form-group"><label>Longitude</label>
            <input value={value(r.region, 'longitude')} onChange={e => set(r.region, 'longitude', e.target.value)} placeholder="78.48670" inputMode="decimal" /></div>
          <button type="button" className="btn btn-secondary" onClick={() => here(r.region)}>Use my location</button>
          <button type="button" className="btn btn-primary" onClick={() => save(r.region)}>Save</button>
        </div>
      ))}
    </section>
  );
}

/** Next 5 days of heat risk per farm (admin: all farms; supervisor: their regions). */
export default function HeatStress() {
  const { isAdmin } = useAuth();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const load = () => insightsAPI.heatStress().then(r => { setData(r.data); setError(''); })
    .catch(err => setError(getErrorMessage(err)));
  useEffect(() => { load(); }, []);

  const levelsSeen = new Set((data?.farms || []).flatMap(f => f.days.map(c => c.level)));

  return (
    <div className="page">
      <div className="page-header">
        <h1>Heat Stress Forecast</h1>
        {isAdmin && <Link to="/insights" className="btn btn-secondary">← Insights</Link>}
      </div>
      <p className="muted">Next 5 days, from the weather forecast for each region, adjusted for the birds' age on each day
        (heavy birds 28+ days suffer most; young chicks less) and the shed (EC sheds are better protected).</p>
      {error && <div className="alert-banner alert-banner-danger">{error}</div>}
      {!data && !error && <p className="muted">Loading…</p>}
      {data && (
        <>
          {data.summary.regions_missing_location.length > 0 && (
            <div className="alert-banner alert-banner-warning">
              No location set for {data.summary.regions_missing_location.join(', ')} — their farms are not checked.
              {isAdmin ? ' Set them under Region locations below.' : ' Ask the admin to set them.'}
            </div>
          )}
          {data.regions.filter(r => r.error).map(r => (
            <div key={r.region} className="alert-banner alert-banner-warning">{r.region}: {r.error}</div>
          ))}
          <div className="stats-grid" style={{ marginBottom: '1rem' }}>
            <div className={`stat-card ${data.summary.at_risk_next_3_days ? 'stat-alert' : ''}`}>
              <span className="stat-label">Farms at danger+ (3 days)</span><span className="stat-value">{data.summary.at_risk_next_3_days}</span></div>
            <div className="stat-card"><span className="stat-label">At emergency (3 days)</span><span className="stat-value">{data.summary.emergency_next_3_days}</span></div>
          </div>

          {data.regions.some(r => r.days.length) && (
            <>
              <h2>Weather by region</h2>
              <div className="table-wrapper">
                <table>
                  <thead><tr><th>Region</th>{data.dates.map(d => <th key={d}>{dayLabel(d)}</th>)}</tr></thead>
                  <tbody>
                    {data.regions.filter(r => r.days.length).map(r => (
                      <tr key={r.region}>
                        <td>{r.region}</td>
                        {r.days.map(d => (
                          <td key={d.date} className="heat-cell">
                            <Level level={d.level} />
                            <small>{d.peak_temp}°C · {d.peak_rh}% at {d.peak_hour}:00</small>
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          <h2 style={{ marginTop: '1.5rem' }}>Farms</h2>
          <div className="heat-legend">
            {['none', 'watch', 'danger', 'emergency'].map(l => <Level key={l} level={l} />)}
            <span className="muted">Cell shows the birds' age that day.</span>
          </div>
          {data.farms.length === 0 ? <div className="alert-banner">No active flocks with a weather forecast.</div> : (
            <div className="table-wrapper">
              <table>
                <thead><tr><th>Farm</th><th>Shed</th>{data.dates.map(d => <th key={d}>{dayLabel(d)}</th>)}</tr></thead>
                <tbody>
                  {data.farms.map(f => (
                    <tr key={f.flock_id}>
                      <td><Link to={`/flocks/${f.flock_id}`}>{f.farm_name}</Link><br /><small className="muted">{f.region}</small></td>
                      <td>{f.shed_type === 'EC' ? 'EC' : 'Open'}</td>
                      {f.days.map(c => (
                        <td key={c.date} className="heat-cell"><Level level={c.level} /><small>day {c.age}</small></td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {['watch', 'danger', 'emergency'].some(l => levelsSeen.has(l)) && (
            <>
              <h2 style={{ marginTop: '1.5rem' }}>What to do</h2>
              <ul style={{ lineHeight: 1.6 }}>
                {['watch', 'danger', 'emergency'].filter(l => levelsSeen.has(l)).map(l => (
                  <li key={l}><Level level={l} /> {data.advice[l]}</li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
      {isAdmin && <RegionLocations onSaved={load} />}
    </div>
  );
}
