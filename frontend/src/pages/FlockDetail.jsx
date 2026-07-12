import { FlockDetailSkeleton } from '../components/Skeletons';
import ConfirmModal from '../components/ConfirmModal';
import UnsavedPrompt from '../components/UnsavedPrompt';
import { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { flockAPI, dailyEntryAPI, saleAPI, medicationAPI, feedOrderAPI, feedStockAPI, billAPI } from '../api/client';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, AreaChart, Area } from 'recharts';

export default function FlockDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [flock, setFlock] = useState(null);
  const [cumulative, setCumulative] = useState(null);
  const [farmStock, setFarmStock] = useState(null);
  const [showEntryForm, setShowEntryForm] = useState(false);
  const [showSaleForm, setShowSaleForm] = useState(false);
  const [showMedForm, setShowMedForm] = useState(false);
  const [showFeedOrderForm, setShowFeedOrderForm] = useState(false);
  const [editingEntry, setEditingEntry] = useState(null);
  const [confirm, setConfirm] = useState({ open: false, title: '', message: '', onConfirm: null, danger: false });
  const [entryForm, setEntryForm] = useState({
    date: new Date().toISOString().split('T')[0],
    mortality_count: '', feed_type: 'BPSC', feed_bags: '',
    water_consumed_liters: '', avg_body_weight_grams: '', notes: '',
  });
  const [saleForm, setSaleForm] = useState({
    date: new Date().toISOString().split('T')[0],
    bird_count: '', total_weight_kg: '', rate_per_kg: '', notes: '',
  });
  const [medForm, setMedForm] = useState({
    date: new Date().toISOString().split('T')[0],
    name: '', dose: '', route: '', cost: '', reason: '',
  });
  const [feedOrderForm, setFeedOrderForm] = useState({ feed_type: 'BPSC', quantity_bags: '', notes: '' });
  const [error, setError] = useState('');
  const [loadError, setLoadError] = useState('');

  const load = async () => {
    try {
      const [flockRes, cumRes] = await Promise.all([flockAPI.get(id), flockAPI.cumulative(id)]);
      setFlock(flockRes.data);
      setCumulative(cumRes.data);
      try {
        const stockRes = await feedStockAPI.list(flockRes.data.farm);
        if (stockRes.data.length > 0) setFarmStock(stockRes.data[0]);
      } catch {}
    } catch (err) {
      console.error('Flock load error:', err);
      setLoadError(err.response?.data?.error || err.response?.data?.detail || 'Failed to load flock data. Check console for details.');
    }
  };

  useEffect(() => { load(); }, [id]);

  const resetEntryForm = () => {
    setEntryForm({ date: new Date().toISOString().split('T')[0], mortality_count: '', feed_type: 'BPSC', feed_bags: '', water_consumed_liters: '', avg_body_weight_grams: '', notes: '' });
    setEditingEntry(null);
  };

  const startEditEntry = (entry) => {
    // Figure out which feed type was used
    let feed_type = 'BPSC', feed_bags = '';
    if (entry.feed_bpsc_bags > 0) { feed_type = 'BPSC'; feed_bags = entry.feed_bpsc_bags; }
    else if (entry.feed_bsc_bags > 0) { feed_type = 'BSC'; feed_bags = entry.feed_bsc_bags; }
    else if (entry.feed_bfp_bags > 0) { feed_type = 'BFP'; feed_bags = entry.feed_bfp_bags; }

    setEntryForm({
      date: entry.date,
      mortality_count: entry.daily_mortality || '',
      feed_type,
      feed_bags: feed_bags || '',
      water_consumed_liters: entry.water_liters || '',
      avg_body_weight_grams: entry.avg_body_weight_grams || '',
      notes: '',
    });
    setEditingEntry(entry);
    setShowEntryForm(true);
    setShowSaleForm(false);
    setShowMedForm(false);
    setShowFeedOrderForm(false);
  };

  const handleEntry = async (e) => {
    e.preventDefault(); setError('');
    const bags = parseInt(entryForm.feed_bags) || 0;
    const data = {
      flock: id, date: entryForm.date,
      mortality_count: parseInt(entryForm.mortality_count) || 0,
      feed_bpsc_bags: entryForm.feed_type === 'BPSC' ? bags : 0,
      feed_bsc_bags: entryForm.feed_type === 'BSC' ? bags : 0,
      feed_bfp_bags: entryForm.feed_type === 'BFP' ? bags : 0,
      water_consumed_liters: parseFloat(entryForm.water_consumed_liters) || 0,
      avg_body_weight_grams: entryForm.avg_body_weight_grams ? parseFloat(entryForm.avg_body_weight_grams) : null,
      notes: entryForm.notes,
    };
    try {
      if (editingEntry) {
        await dailyEntryAPI.update(editingEntry.id, data);
      } else {
        await dailyEntryAPI.create(data);
      }
      setShowEntryForm(false);
      resetEntryForm();
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

  const handleMed = async (e) => {
    e.preventDefault(); setError('');
    try {
      await medicationAPI.create({
        flock: id, date: medForm.date, name: medForm.name,
        dose: medForm.dose, route: medForm.route,
        cost: parseFloat(medForm.cost) || 0, reason: medForm.reason,
      });
      setShowMedForm(false);
      setMedForm({ date: new Date().toISOString().split('T')[0], name: '', dose: '', route: '', cost: '', reason: '' });
      load();
    } catch (err) { setError(err.response?.data ? JSON.stringify(err.response.data) : 'Failed'); }
  };

  const handleFeedOrder = async (e) => {
    e.preventDefault(); setError('');
    try {
      await feedOrderAPI.create({
        farm: flock.farm,
        feed_type: feedOrderForm.feed_type,
        quantity_bags: parseInt(feedOrderForm.quantity_bags),
        notes: feedOrderForm.notes,
      });
      setShowFeedOrderForm(false);
      setFeedOrderForm({ feed_type: 'BPSC', quantity_bags: '', notes: '' });
      load();
    } catch (err) { setError(err.response?.data ? JSON.stringify(err.response.data) : 'Failed'); }
  };

  const exportFlock = () => {
    window.open(`${import.meta.env.VITE_API_URL || 'http://localhost:8000/api'}/flocks/${id}/export/`, '_blank');
  };

  if (loadError) return (
    <div className="page">
      <div className="error-msg" style={{ marginBottom: '1rem' }}>{loadError}</div>
      <Link to="/" className="btn btn-primary">Back to Dashboard</Link>
    </div>
  );
  if (!flock || !cumulative) return <FlockDetailSkeleton />;

  const fs = cumulative.feed_schedule_status || {};
  const pctUsed = (used, quota) => quota > 0 ? Math.min(100, Math.round((used / quota) * 100)) : 0;

  return (
    <div className="page">
      <UnsavedPrompt when={showEntryForm || showSaleForm || showMedForm || showFeedOrderForm} message="You have an unsaved form open. Discard changes?" />
      <div className="page-header">
        <div>
          <Link to={`/farms/${flock.farm}`} className="back-link">&larr; Back to Farm</Link>
          <h1>{flock.farm_name} — Flock</h1>
          <p className="farm-meta">Placed: {flock.placement_date} &middot; Day {flock.age_days} &middot; {flock.chick_count.toLocaleString()} chicks</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button className="btn btn-primary" onClick={() => { setShowEntryForm(!showEntryForm); setShowSaleForm(false); setShowMedForm(false); setShowFeedOrderForm(false); }}>+ Daily Entry</button>
          <button className="btn btn-secondary" onClick={() => { setShowSaleForm(!showSaleForm); setShowEntryForm(false); setShowMedForm(false); setShowFeedOrderForm(false); }}>+ Sale</button>
          <button className="btn btn-secondary" onClick={() => { setShowMedForm(!showMedForm); setShowEntryForm(false); setShowSaleForm(false); setShowFeedOrderForm(false); }}>+ Medicine</button>
          <button className="btn btn-secondary" onClick={() => { setShowFeedOrderForm(!showFeedOrderForm); setShowEntryForm(false); setShowSaleForm(false); setShowMedForm(false); }}>+ Order Feed</button>
          <button className="btn btn-secondary" onClick={exportFlock}>Export</button>
          {flock.status === 'active' && (
            <button className="btn btn-danger" onClick={() => setConfirm({
              open: true, danger: true,
              title: 'Close Flock & Generate Bill',
              message: `This will close the flock at ${flock.farm_name} and generate the farmer bill. This action cannot be undone.`,
              onConfirm: async () => {
                setConfirm({ ...confirm, open: false });
                try {
                  await billAPI.closeAndBill(id);
                  navigate(`/flocks/${id}/bill`);
                } catch (err) {
                  alert(err.response?.data?.error || 'Failed to close flock');
                }
              }
            })}>Close & Generate Bill</button>
          )}
          {flock.status === 'closed' && (
            <Link to={`/flocks/${id}/bill`} className="btn btn-secondary">View Bill</Link>
          )}
        </div>
      </div>

      {error && <div className="error-msg">{error}</div>}

      {/* === ALL FORMS — appear right below buttons === */}

      {/* Daily Entry Form */}
      {showEntryForm && (
        <form onSubmit={handleEntry} className="form-card" style={{ marginBottom: '1.5rem' }}>
          <h3>{editingEntry ? 'Edit Daily Entry' : 'Add Daily Entry'}</h3>
          <div className="form-row">
            <div className="form-group"><label>Date *</label><input type="date" value={entryForm.date} onChange={e => setEntryForm({ ...entryForm, date: e.target.value })} required disabled={!!editingEntry} /></div>
            <div className="form-group"><label>Mortality</label><input type="text" inputMode="numeric" pattern="[0-9]*" value={entryForm.mortality_count} onChange={e => setEntryForm({ ...entryForm, mortality_count: e.target.value })} placeholder="0" /></div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Feed Type</label>
              <select value={entryForm.feed_type} onChange={e => setEntryForm({ ...entryForm, feed_type: e.target.value })}>
                <option value="BPSC">BPSC (Pre-Starter)</option>
                <option value="BSC">BSC (Starter)</option>
                <option value="BFP">BFP (Finisher)</option>
              </select>
            </div>
            <div className="form-group"><label>Bags</label><input type="text" inputMode="numeric" pattern="[0-9]*" value={entryForm.feed_bags} onChange={e => setEntryForm({ ...entryForm, feed_bags: e.target.value })} placeholder="0" /><small className="field-hint">1 bag = 50 kg</small></div>
          </div>
          <div className="form-row">
            <div className="form-group"><label>Water (L)</label><input type="text" inputMode="decimal" value={entryForm.water_consumed_liters} onChange={e => setEntryForm({ ...entryForm, water_consumed_liters: e.target.value })} placeholder="0" /></div>
            <div className="form-group"><label>Body Weight (g)</label><input type="text" inputMode="decimal" value={entryForm.avg_body_weight_grams} onChange={e => setEntryForm({ ...entryForm, avg_body_weight_grams: e.target.value })} placeholder="Optional" /></div>
            <div className="form-group"><label>Notes</label><input value={entryForm.notes} onChange={e => setEntryForm({ ...entryForm, notes: e.target.value })} /></div>
          </div>
          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={() => { setShowEntryForm(false); resetEntryForm(); }}>Cancel</button>
            <button type="submit" className="btn btn-primary">{editingEntry ? 'Update' : 'Save'}</button>
          </div>
        </form>
      )}

      {/* Sale Form */}
      {showSaleForm && (
        <form onSubmit={handleSale} className="form-card" style={{ marginBottom: '1.5rem' }}>
          <h3>Record Sale / Lifting</h3>
          <div className="form-row">
            <div className="form-group"><label>Date *</label><input type="date" value={saleForm.date} onChange={e => setSaleForm({ ...saleForm, date: e.target.value })} required /></div>
            <div className="form-group"><label>Birds *</label><input type="text" inputMode="numeric" pattern="[0-9]*" value={saleForm.bird_count} onChange={e => setSaleForm({ ...saleForm, bird_count: e.target.value })} required /></div>
            <div className="form-group"><label>Total Weight (kg) *</label><input type="text" inputMode="decimal" value={saleForm.total_weight_kg} onChange={e => setSaleForm({ ...saleForm, total_weight_kg: e.target.value })} required /></div>
          </div>
          <div className="form-row">
            <div className="form-group"><label>Rate (₹/kg)</label><input type="text" inputMode="decimal" value={saleForm.rate_per_kg} onChange={e => setSaleForm({ ...saleForm, rate_per_kg: e.target.value })} /></div>
            <div className="form-group"><label>Notes</label><input value={saleForm.notes} onChange={e => setSaleForm({ ...saleForm, notes: e.target.value })} /></div>
          </div>
          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={() => setShowSaleForm(false)}>Cancel</button>
            <button type="submit" className="btn btn-primary">Save Sale</button>
          </div>
        </form>
      )}

      {/* Medication Form */}
      {showMedForm && (
        <form onSubmit={handleMed} className="form-card" style={{ marginBottom: '1.5rem' }}>
          <h3>Add Medication / Vaccine</h3>
          <div className="form-row">
            <div className="form-group"><label>Date *</label><input type="date" value={medForm.date} onChange={e => setMedForm({ ...medForm, date: e.target.value })} required /></div>
            <div className="form-group"><label>Medicine Name *</label><input value={medForm.name} onChange={e => setMedForm({ ...medForm, name: e.target.value })} required placeholder="e.g. Lasota, Enrofloxacin" /></div>
            <div className="form-group"><label>Dose</label><input value={medForm.dose} onChange={e => setMedForm({ ...medForm, dose: e.target.value })} placeholder="e.g. 1ml/L water" /></div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Route</label>
              <select value={medForm.route} onChange={e => setMedForm({ ...medForm, route: e.target.value })}>
                <option value="">Select...</option>
                <option value="water">Drinking Water</option>
                <option value="feed">Feed</option>
                <option value="injection">Injection</option>
                <option value="spray">Spray</option>
                <option value="eye_drop">Eye Drop</option>
                <option value="other">Other</option>
              </select>
            </div>
            <div className="form-group"><label>Cost (₹)</label><input type="text" inputMode="decimal" value={medForm.cost} onChange={e => setMedForm({ ...medForm, cost: e.target.value })} placeholder="0" /></div>
            <div className="form-group"><label>Reason</label><input value={medForm.reason} onChange={e => setMedForm({ ...medForm, reason: e.target.value })} placeholder="e.g. Vaccination schedule" /></div>
          </div>
          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={() => setShowMedForm(false)}>Cancel</button>
            <button type="submit" className="btn btn-primary">Save</button>
          </div>
        </form>
      )}

      {/* Feed Order Form */}
      {showFeedOrderForm && (
        <form onSubmit={handleFeedOrder} className="form-card" style={{ marginBottom: '1.5rem' }}>
          <h3>Order Feed for {flock.farm_name}</h3>
          {farmStock && (
            <div className="stock-inline">
              Current stock:
              <span className="feed-badge feed-badge-bpsc">BPSC: {farmStock.stock.bpsc} bags</span>
              <span className="feed-badge feed-badge-bsc">BSC: {farmStock.stock.bsc} bags</span>
              <span className="feed-badge feed-badge-bfp">BFP: {farmStock.stock.bfp} bags</span>
            </div>
          )}
          <div className="form-row">
            <div className="form-group">
              <label>Feed Type *</label>
              <select value={feedOrderForm.feed_type} onChange={e => setFeedOrderForm({ ...feedOrderForm, feed_type: e.target.value })}>
                <option value="BPSC">BPSC (Pre-Starter)</option>
                <option value="BSC">BSC (Starter)</option>
                <option value="BFP">BFP (Finisher)</option>
              </select>
            </div>
            <div className="form-group">
              <label>Quantity (bags) *</label>
              <input type="text" inputMode="numeric" pattern="[0-9]*" value={feedOrderForm.quantity_bags} onChange={e => setFeedOrderForm({ ...feedOrderForm, quantity_bags: e.target.value })} required placeholder="e.g. 10" />
              <small className="field-hint">1 bag = 50 kg</small>
            </div>
            <div className="form-group">
              <label>Notes</label>
              <input value={feedOrderForm.notes} onChange={e => setFeedOrderForm({ ...feedOrderForm, notes: e.target.value })} placeholder="Optional" />
            </div>
          </div>
          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={() => setShowFeedOrderForm(false)}>Cancel</button>
            <button type="submit" className="btn btn-primary">Place Order</button>
          </div>
        </form>
      )}

      {/* Stats */}
      <div className="stats-grid stats-grid-wide">
        <div className="stat-card"><span className="stat-label">Live Birds</span><span className="stat-value">{cumulative.live_birds.toLocaleString()}</span></div>
        <div className="stat-card stat-alert"><span className="stat-label">Mortality</span><span className="stat-value">{flock.total_mortality} ({flock.mortality_percentage}%)</span></div>
        <div className="stat-card stat-success"><span className="stat-label">Sold</span><span className="stat-value">{cumulative.total_sold_birds.toLocaleString()} / {cumulative.total_sold_weight_kg.toLocaleString()} kg</span></div>
        <div className="stat-card"><span className="stat-label">Total Feed</span><span className="stat-value">{(cumulative.feed_by_type.bpsc_bags + cumulative.feed_by_type.bsc_bags + cumulative.feed_by_type.bfp_bags).toFixed(1)} bags<br/><small>{cumulative.total_feed_kg.toLocaleString()} kg</small></span></div>
        <div className="stat-card stat-info"><span className="stat-label">FCR</span><span className="stat-value">{cumulative.fcr ?? '—'}</span></div>
        <div className="stat-card"><span className="stat-label">Med Cost</span><span className="stat-value">₹{parseFloat(flock.total_medication_cost).toLocaleString()}</span></div>
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

          {/* Body Weight vs Standard Curve */}
          {(cumulative.entries.some(e => e.avg_body_weight_grams) || cumulative.standard_curve) && (
            <>
              <h2 style={{ margin: '2rem 0 1rem' }}>Body Weight vs Cobb 400 Standard</h2>
              <div className="chart-container">
                <ResponsiveContainer width="100%" height={350}>
                  <LineChart>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
                    <XAxis
                      dataKey="day_number"
                      type="number"
                      domain={[0, 'auto']}
                      allowDuplicatedCategory={false}
                      label={{ value: 'Day', position: 'bottom', offset: 0 }}
                    />
                    <YAxis label={{ value: 'Weight (g)', angle: -90, position: 'insideLeft' }} />
                    <Tooltip />
                    <Legend />
                    {/* Standard curve — dashed line */}
                    <Line
                      data={cumulative.standard_curve || []}
                      type="monotone"
                      dataKey="standard_weight_grams"
                      name="Cobb 400 Standard"
                      stroke="#bdc3c7"
                      strokeWidth={2}
                      strokeDasharray="6 4"
                      dot={false}
                    />
                    {/* Actual weights — solid line with dots */}
                    <Line
                      data={cumulative.entries.filter(e => e.avg_body_weight_grams)}
                      type="monotone"
                      dataKey="avg_body_weight_grams"
                      name="Actual Weight"
                      stroke="#3498db"
                      strokeWidth={2.5}
                      dot={{ r: 5, fill: '#3498db' }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              {/* Weight comparison table */}
              {cumulative.entries.some(e => e.avg_body_weight_grams) && (
                <div className="weight-comparison" style={{ marginTop: '1rem' }}>
                  <div className="table-wrapper">
                    <table>
                      <thead>
                        <tr>
                          <th>Day</th><th>Date</th><th>Actual (g)</th><th>Standard (g)</th><th>Difference</th><th>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {cumulative.entries.filter(e => e.avg_body_weight_grams).map((e, i) => {
                          const diff = e.avg_body_weight_grams - e.standard_weight_grams;
                          const pct = ((diff / e.standard_weight_grams) * 100).toFixed(1);
                          const isGood = diff >= 0;
                          return (
                            <tr key={i}>
                              <td>{e.day_number}</td>
                              <td>{e.date}</td>
                              <td><strong>{e.avg_body_weight_grams}</strong></td>
                              <td>{e.standard_weight_grams}</td>
                              <td className={isGood ? 'text-ok' : 'text-danger'}>
                                {diff > 0 ? '+' : ''}{diff.toFixed(0)} g ({pct}%)
                              </td>
                              <td>
                                <span className={`weight-status ${isGood ? 'weight-above' : 'weight-below'}`}>
                                  {isGood ? '▲ Above' : '▼ Below'}
                                </span>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </>
          )}

          <h2 style={{ margin: '2rem 0 1rem' }}>Daily Entries</h2>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Day</th><th>Date</th><th>Mort.</th><th>Cum.M</th><th>M%</th>
                  <th>Feed</th><th>Bags</th><th>Cum (bags)</th><th>Cum (kg)</th><th>Water</th><th>Wt(g)</th><th>Std(g)</th><th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {cumulative.entries.map((e, i) => {
                  const feedType = e.feed_bpsc_bags > 0 ? 'BPSC' : e.feed_bsc_bags > 0 ? 'BSC' : e.feed_bfp_bags > 0 ? 'BFP' : '—';
                  const feedBags = e.feed_bpsc_bags || e.feed_bsc_bags || e.feed_bfp_bags || 0;
                  return (
                    <tr key={i}>
                      <td>{e.day_number}</td><td>{e.date}</td>
                      <td>{e.daily_mortality}</td><td>{e.cumulative_mortality}</td>
                      <td className={e.mortality_percentage > 5 ? 'text-danger' : ''}>{e.mortality_percentage}%</td>
                      <td>{feedType !== '—' ? <span className={`feed-badge feed-badge-${feedType.toLowerCase()}`}>{feedType}</span> : '—'}</td>
                      <td>{feedBags || '—'}</td>
                      <td>{e.cumulative_feed_bags}</td><td>{e.cumulative_feed_kg}</td>
                      <td>{e.water_liters}</td><td>{e.avg_body_weight_grams || '—'}</td><td className="text-muted-cell">{e.standard_weight_grams}</td>
                      <td className="entry-actions">
                        <button className="btn-action btn-action-edit" onClick={() => startEditEntry(e)}>Edit</button>
                        <button className="btn-action btn-action-cancel" onClick={() => setConfirm({
                          open: true, danger: true,
                          title: 'Delete Entry',
                          message: `Delete daily entry for ${e.date}? This will remove mortality, feed, and weight data for this day.`,
                          onConfirm: async () => {
                            setConfirm({ ...confirm, open: false });
                            await dailyEntryAPI.delete(e.id);
                            load();
                          }
                        })}>Delete</button>
                      </td>
                    </tr>
                  );
                })}
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

      {/* Medications */}
      {flock.medications && flock.medications.length > 0 && (
        <>
          <h2 style={{ margin: '2rem 0 1rem' }}>Medications / Vaccines <small style={{ fontWeight: 400, color: '#6b6b6b' }}>(Total: ₹{parseFloat(flock.total_medication_cost).toLocaleString()})</small></h2>
          <div className="table-wrapper">
            <table>
              <thead><tr><th>Date</th><th>Day</th><th>Name</th><th>Dose</th><th>Route</th><th>Cost (₹)</th><th>Reason</th></tr></thead>
              <tbody>
                {flock.medications.map(m => (
                  <tr key={m.id}>
                    <td>{m.date}</td>
                    <td>{Math.floor((new Date(m.date) - new Date(flock.placement_date)) / 86400000)}</td>
                    <td><strong>{m.name}</strong></td>
                    <td>{m.dose || '—'}</td>
                    <td>{m.route || '—'}</td>
                    <td>₹{parseFloat(m.cost).toLocaleString()}</td>
                    <td>{m.reason || '—'}</td>
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

      <ConfirmModal
        open={confirm.open}
        title={confirm.title}
        message={confirm.message}
        danger={confirm.danger}
        confirmText={confirm.danger ? 'Yes, proceed' : 'Confirm'}
        onConfirm={confirm.onConfirm}
        onCancel={() => setConfirm({ ...confirm, open: false })}
      />
    </div>
  );
}
