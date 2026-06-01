import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { flockAPI, dailyEntryAPI, saleAPI } from '../api/client';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

export default function FlockDetail() {
  const { id } = useParams();
  const [flock, setFlock] = useState(null);
  const [cumulative, setCumulative] = useState(null);
  const [showEntryForm, setShowEntryForm] = useState(false);
  const [showSaleForm, setShowSaleForm] = useState(false);
  const [entryForm, setEntryForm] = useState({
    date: new Date().toISOString().split('T')[0],
    mortality_count: '', feed_consumed_kg: '', water_consumed_liters: '',
    avg_body_weight_grams: '', notes: '',
  });
  const [saleForm, setSaleForm] = useState({
    date: new Date().toISOString().split('T')[0],
    bird_count: '', total_weight_kg: '', rate_per_kg: '', notes: '',
  });
  const [error, setError] = useState('');

  const load = async () => {
    const [flockRes, cumRes] = await Promise.all([
      flockAPI.get(id), flockAPI.cumulative(id),
    ]);
    setFlock(flockRes.data);
    setCumulative(cumRes.data);
  };

  useEffect(() => { load(); }, [id]);

  const handleEntry = async (e) => {
    e.preventDefault();
    setError('');
    try {
      await dailyEntryAPI.create({
        flock: id,
        date: entryForm.date,
        mortality_count: parseInt(entryForm.mortality_count) || 0,
        feed_consumed_kg: parseFloat(entryForm.feed_consumed_kg) || 0,
        water_consumed_liters: parseFloat(entryForm.water_consumed_liters) || 0,
        avg_body_weight_grams: entryForm.avg_body_weight_grams ? parseFloat(entryForm.avg_body_weight_grams) : null,
        notes: entryForm.notes,
      });
      setShowEntryForm(false);
      setEntryForm({ date: new Date().toISOString().split('T')[0], mortality_count: '', feed_consumed_kg: '', water_consumed_liters: '', avg_body_weight_grams: '', notes: '' });
      load();
    } catch (err) {
      setError(err.response?.data ? JSON.stringify(err.response.data) : 'Failed to save entry');
    }
  };

  const handleSale = async (e) => {
    e.preventDefault();
    setError('');
    try {
      await saleAPI.create({
        flock: id,
        date: saleForm.date,
        bird_count: parseInt(saleForm.bird_count),
        total_weight_kg: parseFloat(saleForm.total_weight_kg),
        rate_per_kg: saleForm.rate_per_kg ? parseFloat(saleForm.rate_per_kg) : null,
        notes: saleForm.notes,
      });
      setShowSaleForm(false);
      setSaleForm({ date: new Date().toISOString().split('T')[0], bird_count: '', total_weight_kg: '', rate_per_kg: '', notes: '' });
      load();
    } catch (err) {
      setError(err.response?.data ? JSON.stringify(err.response.data) : 'Failed to save sale');
    }
  };

  if (!flock || !cumulative) return <div className="loading">Loading flock data...</div>;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <Link to={`/farms/${flock.farm}`} className="back-link">&larr; Back to Farm</Link>
          <h1>{flock.farm_name} — {flock.breed || 'Flock'}</h1>
          <p className="farm-meta">Placed: {flock.placement_date} &middot; Day {flock.age_days} &middot; {flock.chick_count.toLocaleString()} chicks placed</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button className="btn btn-primary" onClick={() => { setShowEntryForm(!showEntryForm); setShowSaleForm(false); }}>+ Daily Entry</button>
          <button className="btn btn-secondary" onClick={() => { setShowSaleForm(!showSaleForm); setShowEntryForm(false); }}>+ Record Sale</button>
        </div>
      </div>

      {/* Stats */}
      <div className="stats-grid stats-grid-wide">
        <div className="stat-card">
          <span className="stat-label">Live Birds</span>
          <span className="stat-value">{cumulative.live_birds.toLocaleString()}</span>
        </div>
        <div className="stat-card stat-alert">
          <span className="stat-label">Mortality</span>
          <span className="stat-value">{flock.total_mortality} ({flock.mortality_percentage}%)</span>
        </div>
        <div className="stat-card stat-success">
          <span className="stat-label">Sold (birds)</span>
          <span className="stat-value">{cumulative.total_sold_birds.toLocaleString()}</span>
        </div>
        <div className="stat-card stat-success">
          <span className="stat-label">Sold (kg)</span>
          <span className="stat-value">{cumulative.total_sold_weight_kg.toLocaleString()} kg</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Total Feed</span>
          <span className="stat-value">{cumulative.total_feed_kg.toLocaleString()} kg</span>
        </div>
        <div className="stat-card stat-info">
          <span className="stat-label">FCR</span>
          <span className="stat-value">{cumulative.fcr != null ? cumulative.fcr : '—'}</span>
        </div>
      </div>

      {error && <div className="error-msg">{error}</div>}

      {/* Daily Entry Form */}
      {showEntryForm && (
        <form onSubmit={handleEntry} className="form-card" style={{ margin: '1.5rem 0' }}>
          <h3>Add Daily Entry</h3>
          <div className="form-row">
            <div className="form-group">
              <label>Date *</label>
              <input type="date" value={entryForm.date} onChange={e => setEntryForm({ ...entryForm, date: e.target.value })} required />
            </div>
            <div className="form-group">
              <label>Mortality Count</label>
              <input type="number" min="0" value={entryForm.mortality_count} onChange={e => setEntryForm({ ...entryForm, mortality_count: e.target.value })} placeholder="0" />
            </div>
            <div className="form-group">
              <label>Feed Consumed (kg)</label>
              <input type="number" step="0.01" min="0" value={entryForm.feed_consumed_kg} onChange={e => setEntryForm({ ...entryForm, feed_consumed_kg: e.target.value })} placeholder="0" />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Water (liters)</label>
              <input type="number" step="0.01" min="0" value={entryForm.water_consumed_liters} onChange={e => setEntryForm({ ...entryForm, water_consumed_liters: e.target.value })} placeholder="0" />
            </div>
            <div className="form-group">
              <label>Avg Body Weight (g)</label>
              <input type="number" step="0.01" min="0" value={entryForm.avg_body_weight_grams} onChange={e => setEntryForm({ ...entryForm, avg_body_weight_grams: e.target.value })} placeholder="Optional" />
            </div>
            <div className="form-group">
              <label>Notes</label>
              <input value={entryForm.notes} onChange={e => setEntryForm({ ...entryForm, notes: e.target.value })} placeholder="Any observations..." />
            </div>
          </div>
          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={() => setShowEntryForm(false)}>Cancel</button>
            <button type="submit" className="btn btn-primary">Save Entry</button>
          </div>
        </form>
      )}

      {/* Sale Form */}
      {showSaleForm && (
        <form onSubmit={handleSale} className="form-card" style={{ margin: '1.5rem 0' }}>
          <h3>Record Bird Sale / Lifting</h3>
          <div className="form-row">
            <div className="form-group">
              <label>Date *</label>
              <input type="date" value={saleForm.date} onChange={e => setSaleForm({ ...saleForm, date: e.target.value })} required />
            </div>
            <div className="form-group">
              <label>Birds Sold *</label>
              <input type="number" min="1" value={saleForm.bird_count} onChange={e => setSaleForm({ ...saleForm, bird_count: e.target.value })} required placeholder="e.g. 2000" />
            </div>
            <div className="form-group">
              <label>Total Weight (kg) *</label>
              <input type="number" step="0.01" min="0" value={saleForm.total_weight_kg} onChange={e => setSaleForm({ ...saleForm, total_weight_kg: e.target.value })} required placeholder="e.g. 4500" />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Rate per kg (₹)</label>
              <input type="number" step="0.01" min="0" value={saleForm.rate_per_kg} onChange={e => setSaleForm({ ...saleForm, rate_per_kg: e.target.value })} placeholder="Optional" />
            </div>
            <div className="form-group">
              <label>Notes</label>
              <input value={saleForm.notes} onChange={e => setSaleForm({ ...saleForm, notes: e.target.value })} placeholder="Optional" />
            </div>
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
          <h2 style={{ margin: '2rem 0 1rem' }}>Cumulative Mortality</h2>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={cumulative.entries}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
                <XAxis dataKey="day_number" label={{ value: 'Day', position: 'bottom' }} />
                <YAxis /><Tooltip /><Legend />
                <Line type="monotone" dataKey="cumulative_mortality" name="Cumulative Deaths" stroke="#e74c3c" strokeWidth={2} dot={{ r: 3 }} />
                <Line type="monotone" dataKey="daily_mortality" name="Daily Deaths" stroke="#e67e22" strokeWidth={1.5} strokeDasharray="4 4" dot={{ r: 2 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <h2 style={{ margin: '2rem 0 1rem' }}>Cumulative Feed (kg)</h2>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={cumulative.entries}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
                <XAxis dataKey="day_number" label={{ value: 'Day', position: 'bottom' }} />
                <YAxis /><Tooltip /><Legend />
                <Line type="monotone" dataKey="cumulative_feed_kg" name="Total Feed (kg)" stroke="#27ae60" strokeWidth={2} dot={{ r: 3 }} />
                <Line type="monotone" dataKey="daily_feed_kg" name="Daily Feed (kg)" stroke="#2ecc71" strokeWidth={1.5} strokeDasharray="4 4" dot={{ r: 2 }} />
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
                    <XAxis dataKey="day_number" label={{ value: 'Day', position: 'bottom' }} />
                    <YAxis /><Tooltip />
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
                  <th>Day</th><th>Date</th><th>Mortality</th><th>Cum. Mort.</th><th>Mort. %</th>
                  <th>Feed (kg)</th><th>Cum. Feed</th><th>Water (L)</th><th>Weight (g)</th>
                </tr>
              </thead>
              <tbody>
                {cumulative.entries.map((entry, i) => (
                  <tr key={i}>
                    <td>{entry.day_number}</td><td>{entry.date}</td>
                    <td>{entry.daily_mortality}</td><td>{entry.cumulative_mortality}</td>
                    <td className={entry.mortality_percentage > 5 ? 'text-danger' : ''}>{entry.mortality_percentage}%</td>
                    <td>{entry.daily_feed_kg}</td><td>{entry.cumulative_feed_kg}</td>
                    <td>{entry.water_liters}</td><td>{entry.avg_body_weight_grams || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* Sales Table */}
      {cumulative.sales && cumulative.sales.length > 0 && (
        <>
          <h2 style={{ margin: '2rem 0 1rem' }}>Sales / Liftings</h2>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr><th>Date</th><th>Birds</th><th>Weight (kg)</th><th>Avg/Bird (kg)</th><th>Rate (₹/kg)</th><th>Amount (₹)</th><th>Notes</th></tr>
              </thead>
              <tbody>
                {cumulative.sales.map(s => (
                  <tr key={s.id}>
                    <td>{s.date}</td><td>{s.bird_count.toLocaleString()}</td>
                    <td>{parseFloat(s.total_weight_kg).toLocaleString()}</td>
                    <td>{s.avg_bird_weight_kg}</td>
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
          <p>No entries yet. Click "+ Daily Entry" to start recording data.</p>
        </div>
      )}
    </div>
  );
}
