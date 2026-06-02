import { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { flockAPI, dailyEntryAPI, saleAPI } from '../api/client';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, AreaChart, Area } from 'recharts';

export default function FlockDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [flock, setFlock] = useState(null);
  const [cumulative, setCumulative] = useState(null);
  const [showEntryForm, setShowEntryForm] = useState(false);
  const [showSaleForm, setShowSaleForm] = useState(false);
  const [entryForm, setEntryForm] = useState({
    date: new Date().toISOString().split('T')[0],
    mortality_count: '', feed_bpsc_bags: '', feed_bsc_bags: '', feed_bfp_bags: '',
    water_consumed_liters: '', avg_body_weight_grams: '', notes: '',
  });
  const [saleForm, setSaleForm] = useState({
    date: new Date().toISOString().split('T')[0],
    bird_count: '', total_weight_kg: '', rate_per_kg: '', notes: '',
  });
  const [error, setError] = useState('');

  const load = async () => {
    const [flockRes, cumRes] = await Promise.all([flockAPI.get(id), flockAPI.cumulative(id)]);
    setFlock(flockRes.data);
    setCumulative(cumRes.data);
  };

  useEffect(() => { load(); }, [id]);

  const handleEntry = async (e) => {
    e.preventDefault(); setError('');
    try {
      await dailyEntryAPI.create({
        flock: id, date: entryForm.date,
        mortality_count: parseInt(entryForm.mortality_count) || 0,
        feed_bpsc_bags: parseFloat(entryForm.feed_bpsc_bags) || 0,
        feed_bsc_bags: parseFloat(entryForm.feed_bsc_bags) || 0,
        feed_bfp_bags: parseFloat(entryForm.feed_bfp_bags) || 0,
        water_consumed_liters: parseFloat(entryForm.water_consumed_liters) || 0,
        avg_body_weight_grams: entryForm.avg_body_weight_grams ? parseFloat(entryForm.avg_body_weight_grams) : null,
        notes: entryForm.notes,
      });
      setShowEntryForm(false);
      setEntryForm({ date: new Date().toISOString().split('T')[0], mortality_count: '', feed_bpsc_bags: '', feed_bsc_bags: '', feed_bfp_bags: '', water_consumed_liters: '', avg_body_weight_grams: '', notes: '' });
      load();
    } catch (err) { setError(err.response?.data ? JSON.stringify(err.response.data) : 'Failed'); }
  };

  const handleSale = async (e) => {
    e.preventDefault(); setError('');
    try {
      await saleAPI.create({
        flock: id, date: saleForm.date,
        bird_count: parseInt(saleForm.bird_count),
        total_weight_kg: parseFloat(saleForm.total_weight_kg),
        rate_per_kg: saleForm.rate_per_kg ? parseFloat(saleForm.rate_per_kg) : null,
        notes: saleForm.notes,
      });
      setShowSaleForm(false);
      setSaleForm({ date: new Date().toISOString().split('T')[0], bird_count: '', total_weight_kg: '', rate_per_kg: '', notes: '' });
      load();
    } catch (err) { setError(err.response?.data ? JSON.stringify(err.response.data) : 'Failed'); }
  };

  if (!flock || !cumulative) return <div className="loading">Loading flock data...</div>;

  const fs = cumulative.feed_schedule_status || {};
  const pctUsed = (used, quota) => quota > 0 ? Math.min(100, Math.round((used / quota) * 100)) : 0;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <Link to={`/farms/${flock.farm}`} className="back-link">&larr; Back to Farm</Link>
          <h1>{flock.farm_name} — Flock</h1>
          <p className="farm-meta">Placed: {flock.placement_date} &middot; Day {flock.age_days} &middot; {flock.chick_count.toLocaleString()} chicks</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button className="btn btn-primary" onClick={() => { setShowEntryForm(!showEntryForm); setShowSaleForm(false); }}>+ Daily Entry</button>
          <button className="btn btn-secondary" onClick={() => { setShowSaleForm(!showSaleForm); setShowEntryForm(false); }}>+ Record Sale</button>
          {flock.status === 'active' && (
            <button className="btn btn-danger" onClick={async () => {
              if (window.confirm('Close this flock? This will mark it as completed. Bill generation coming soon.')) {
                await flockAPI.update(id, { ...flock, status: 'closed', farm: flock.farm });
                navigate(`/farms/${flock.farm}`);
              }
            }}>Close Flock</button>
          )}
        </div>
      </div>

      {/* Stats */}
      <div className="stats-grid stats-grid-wide">
        <div className="stat-card"><span className="stat-label">Live Birds</span><span className="stat-value">{cumulative.live_birds.toLocaleString()}</span></div>
        <div className="stat-card stat-alert"><span className="stat-label">Mortality</span><span className="stat-value">{flock.total_mortality} ({flock.mortality_percentage}%)</span></div>
        <div className="stat-card stat-success"><span className="stat-label">Sold</span><span className="stat-value">{cumulative.total_sold_birds.toLocaleString()} / {cumulative.total_sold_weight_kg.toLocaleString()} kg</span></div>
        <div className="stat-card"><span className="stat-label">Total Feed</span><span className="stat-value">{(cumulative.feed_by_type.bpsc_bags + cumulative.feed_by_type.bsc_bags + cumulative.feed_by_type.bfp_bags).toFixed(1)} bags<br/><small>{cumulative.total_feed_kg.toLocaleString()} kg</small></span></div>
        <div className="stat-card stat-info"><span className="stat-label">FCR</span><span className="stat-value">{cumulative.fcr ?? '—'}</span></div>
        <div className="stat-card"><span className="stat-label">Current Feed</span><span className="stat-value"><span className={`feed-badge feed-badge-${(fs.current_feed_type || '').toLowerCase()}`}>{fs.current_feed_type || '—'}</span></span></div>
      </div>

      {/* Feed Schedule Progress */}
      <h2 style={{ margin: '1.5rem 0 0.75rem' }}>Feed Schedule</h2>
      <div className="feed-progress-grid">
        <div className="feed-progress-card">
          <div className="feed-progress-header">
            <span className="feed-badge feed-badge-bpsc">BPSC</span>
            <span>{fs.bpsc_used_bags} / ~{fs.bpsc_estimate_bags} bags ({fs.bpsc_used_kg} / ~{fs.bpsc_estimate_kg} kg)</span>
          </div>
          <div className="progress-bar"><div className="progress-fill progress-bpsc" style={{ width: `${pctUsed(fs.bpsc_used_kg, fs.bpsc_estimate_kg)}%` }}></div></div>
          <span className="feed-progress-sub">{fs.bpsc_remaining_kg} kg remaining (est.) &middot; ~{flock.bpsc_per_bird_kg} kg/bird</span>
        </div>
        <div className="feed-progress-card">
          <div className="feed-progress-header">
            <span className="feed-badge feed-badge-bsc">BSC</span>
            <span>{fs.bsc_used_bags} / ~{fs.bsc_estimate_bags} bags ({fs.bsc_used_kg} / ~{fs.bsc_estimate_kg} kg)</span>
          </div>
          <div className="progress-bar"><div className="progress-fill progress-bsc" style={{ width: `${pctUsed(fs.bsc_used_kg, fs.bsc_estimate_kg)}%` }}></div></div>
          <span className="feed-progress-sub">{fs.bsc_remaining_kg} kg remaining (est.) &middot; ~{flock.bsc_per_bird_kg} kg/bird</span>
        </div>
        <div className="feed-progress-card">
          <div className="feed-progress-header">
            <span className="feed-badge feed-badge-bfp">BFP</span>
            <span>{fs.bfp_used_bags} bags ({fs.bfp_used_kg} kg)</span>
          </div>
          <span className="feed-progress-sub">No fixed target — given after BPSC &amp; BSC</span>
        </div>
      </div>

      {error && <div className="error-msg">{error}</div>}

      {/* Daily Entry Form */}
      {showEntryForm && (
        <form onSubmit={handleEntry} className="form-card" style={{ margin: '1.5rem 0' }}>
          <h3>Add Daily Entry</h3>
          <div className="form-row">
            <div className="form-group"><label>Date *</label><input type="date" value={entryForm.date} onChange={e => setEntryForm({ ...entryForm, date: e.target.value })} required /></div>
            <div className="form-group"><label>Mortality</label><input type="number" min="0" value={entryForm.mortality_count} onChange={e => setEntryForm({ ...entryForm, mortality_count: e.target.value })} placeholder="0" /></div>
          </div>
          <div className="form-row">
            <div className="form-group"><label>BPSC (bags)</label><input type="number" step="0.5" min="0" value={entryForm.feed_bpsc_bags} onChange={e => setEntryForm({ ...entryForm, feed_bpsc_bags: e.target.value })} placeholder="0" /><small className="field-hint">1 bag = 50 kg</small></div>
            <div className="form-group"><label>BSC (bags)</label><input type="number" step="0.5" min="0" value={entryForm.feed_bsc_bags} onChange={e => setEntryForm({ ...entryForm, feed_bsc_bags: e.target.value })} placeholder="0" /><small className="field-hint">1 bag = 50 kg</small></div>
            <div className="form-group"><label>BFP (bags)</label><input type="number" step="0.5" min="0" value={entryForm.feed_bfp_bags} onChange={e => setEntryForm({ ...entryForm, feed_bfp_bags: e.target.value })} placeholder="0" /><small className="field-hint">1 bag = 50 kg</small></div>
          </div>
          <div className="form-row">
            <div className="form-group"><label>Water (L)</label><input type="number" step="0.01" min="0" value={entryForm.water_consumed_liters} onChange={e => setEntryForm({ ...entryForm, water_consumed_liters: e.target.value })} placeholder="0" /></div>
            <div className="form-group"><label>Body Weight (g)</label><input type="number" step="0.01" min="0" value={entryForm.avg_body_weight_grams} onChange={e => setEntryForm({ ...entryForm, avg_body_weight_grams: e.target.value })} placeholder="Optional" /></div>
            <div className="form-group"><label>Notes</label><input value={entryForm.notes} onChange={e => setEntryForm({ ...entryForm, notes: e.target.value })} /></div>
          </div>
          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={() => setShowEntryForm(false)}>Cancel</button>
            <button type="submit" className="btn btn-primary">Save</button>
          </div>
        </form>
      )}

      {/* Sale Form */}
      {showSaleForm && (
        <form onSubmit={handleSale} className="form-card" style={{ margin: '1.5rem 0' }}>
          <h3>Record Sale / Lifting</h3>
          <div className="form-row">
            <div className="form-group"><label>Date *</label><input type="date" value={saleForm.date} onChange={e => setSaleForm({ ...saleForm, date: e.target.value })} required /></div>
            <div className="form-group"><label>Birds *</label><input type="number" min="1" value={saleForm.bird_count} onChange={e => setSaleForm({ ...saleForm, bird_count: e.target.value })} required /></div>
            <div className="form-group"><label>Total Weight (kg) *</label><input type="number" step="0.01" min="0" value={saleForm.total_weight_kg} onChange={e => setSaleForm({ ...saleForm, total_weight_kg: e.target.value })} required /></div>
          </div>
          <div className="form-row">
            <div className="form-group"><label>Rate (₹/kg)</label><input type="number" step="0.01" min="0" value={saleForm.rate_per_kg} onChange={e => setSaleForm({ ...saleForm, rate_per_kg: e.target.value })} /></div>
            <div className="form-group"><label>Notes</label><input value={saleForm.notes} onChange={e => setSaleForm({ ...saleForm, notes: e.target.value })} /></div>
          </div>
          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={() => setShowSaleForm(false)}>Cancel</button>
            <button type="submit" className="btn btn-primary">Save Sale</button>
          </div>
        </form>
      )}

      {/* Charts */}
      {cumulative.entries.length > 0 && (
        <>
          <h2 style={{ margin: '2rem 0 1rem' }}>Feed by Type — Cumulative (bags)</h2>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={cumulative.entries}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
                <XAxis dataKey="day_number" label={{ value: 'Day', position: 'bottom' }} />
                <YAxis /><Tooltip /><Legend />
                <Area type="monotone" dataKey="cum_bpsc_bags" name="BPSC (bags)" stackId="1" stroke="#e67e22" fill="#fdebd0" />
                <Area type="monotone" dataKey="cum_bsc_bags" name="BSC (bags)" stackId="1" stroke="#2980b9" fill="#d4e6f1" />
                <Area type="monotone" dataKey="cum_bfp_bags" name="BFP (bags)" stackId="1" stroke="#27ae60" fill="#d5f5e3" />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          <h2 style={{ margin: '2rem 0 1rem' }}>Mortality</h2>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={cumulative.entries}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
                <XAxis dataKey="day_number" /><YAxis /><Tooltip /><Legend />
                <Line type="monotone" dataKey="cumulative_mortality" name="Cumulative" stroke="#e74c3c" strokeWidth={2} dot={{ r: 3 }} />
                <Line type="monotone" dataKey="daily_mortality" name="Daily" stroke="#e67e22" strokeWidth={1.5} strokeDasharray="4 4" dot={{ r: 2 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {cumulative.entries.some(e => e.avg_body_weight_grams) && (
            <>
              <h2 style={{ margin: '2rem 0 1rem' }}>Body Weight (g)</h2>
              <div className="chart-container">
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={cumulative.entries.filter(e => e.avg_body_weight_grams)}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
                    <XAxis dataKey="day_number" /><YAxis /><Tooltip />
                    <Line type="monotone" dataKey="avg_body_weight_grams" name="Avg Weight (g)" stroke="#3498db" strokeWidth={2} dot={{ r: 4 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </>
          )}

          <h2 style={{ margin: '2rem 0 1rem' }}>Daily Entries</h2>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Day</th><th>Date</th><th>Mort.</th><th>Cum.M</th><th>M%</th>
                  <th>BPSC</th><th>BSC</th><th>BFP</th><th>Total (bags)</th><th>Cum (bags)</th><th>Cum (kg)</th><th>Water</th><th>Wt(g)</th><th></th>
                </tr>
              </thead>
              <tbody>
                {cumulative.entries.map((e, i) => (
                  <tr key={i}>
                    <td>{e.day_number}</td><td>{e.date}</td>
                    <td>{e.daily_mortality}</td><td>{e.cumulative_mortality}</td>
                    <td className={e.mortality_percentage > 5 ? 'text-danger' : ''}>{e.mortality_percentage}%</td>
                    <td>{e.feed_bpsc_bags}</td><td>{e.feed_bsc_bags}</td><td>{e.feed_bfp_bags}</td>
                    <td>{e.daily_feed_bags}</td><td>{e.cumulative_feed_bags}</td><td>{e.cumulative_feed_kg}</td>
                    <td>{e.water_liters}</td><td>{e.avg_body_weight_grams || '—'}</td>
                    <td><button className="btn-delete" onClick={async (ev) => {
                      ev.stopPropagation();
                      if (window.confirm(`Delete entry for ${e.date}?`)) {
                        await dailyEntryAPI.delete(e.id);
                        load();
                      }
                    }}>&times;</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* Sales */}
      {cumulative.sales && cumulative.sales.length > 0 && (
        <>
          <h2 style={{ margin: '2rem 0 1rem' }}>Sales / Liftings</h2>
          <div className="table-wrapper">
            <table>
              <thead><tr><th>Date</th><th>Birds</th><th>Weight</th><th>Avg/Bird</th><th>Rate</th><th>Amount</th><th>Notes</th></tr></thead>
              <tbody>
                {cumulative.sales.map(s => (
                  <tr key={s.id}>
                    <td>{s.date}</td><td>{s.bird_count.toLocaleString()}</td>
                    <td>{parseFloat(s.total_weight_kg).toLocaleString()} kg</td>
                    <td>{s.avg_bird_weight_kg} kg</td>
                    <td>{s.rate_per_kg ? `₹${s.rate_per_kg}` : '—'}</td>
                    <td>{s.total_amount ? `₹${parseFloat(s.total_amount).toLocaleString()}` : '—'}</td>
                    <td>{s.notes || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {cumulative.entries.length === 0 && (
        <div className="empty-state" style={{ marginTop: '2rem' }}>
          <p>No entries yet. Click "+ Daily Entry" to start recording.</p>
        </div>
      )}
    </div>
  );
}
