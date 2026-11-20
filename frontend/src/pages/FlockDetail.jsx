import { FlockDetailSkeleton } from '../components/Skeletons';
import ConfirmModal from '../components/ConfirmModal';
import UnsavedPrompt from '../components/UnsavedPrompt';
import { useState, useEffect } from 'react';
import { useParams, Link, useNavigate, useSearchParams } from 'react-router-dom';
import { flockAPI, dailyEntryAPI, saleAPI, medicationAPI, feedOrderAPI, feedStockAPI, billAPI, changeRequestAPI, getErrorMessage } from '../api/client';
import ReasonDialog from '../components/ReasonDialog';
import PendingChanges from '../components/PendingChanges';
import useApprovalSave from '../utils/useApprovalSave';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, AreaChart, Area } from 'recharts';
import { useAuth } from '../context/AuthContext';
import FeedBadge from '../components/FeedBadge';
import useFeedTypes from '../utils/useFeedTypes';
import BillCardPicker from '../components/BillCardPicker';
import DocumentsSection from '../components/DocumentsSection';
import BagCountSection from '../components/BagCountSection';
import ChickQualityCard from '../components/ChickQualityCard';
import { todayISO } from '../utils/dates';
import { Chip, Panel, StatTile } from '../components/ui';
import { fmtDate, fmtNum } from '../utils/format';

const TABS = [
  { key: 'overview', label: 'Overview' },
  { key: 'entries', label: 'Daily entries' },
  { key: 'sales', label: 'Sales' },
  { key: 'feed', label: 'Feed' },
  { key: 'health', label: 'Health' },
  { key: 'documents', label: 'Documents' },
];

export default function FlockDetail() {
  const { id } = useParams();
  const [params, setParams] = useSearchParams();
  const showTab = (k) => setParams(k === 'overview' ? {} : { tab: k }, { replace: true });
  const navigate = useNavigate();
  const { canEditFarm, isAdmin } = useAuth();
  const [flock, setFlock] = useState(null);
  const [cumulative, setCumulative] = useState(null);
  const [farmStock, setFarmStock] = useState(null);
  const [showEntryForm, setShowEntryForm] = useState(false);
  const [showSaleForm, setShowSaleForm] = useState(false);
  const [showMedForm, setShowMedForm] = useState(false);
  const [showFeedOrderForm, setShowFeedOrderForm] = useState(false);
  const [editingEntry, setEditingEntry] = useState(null);
  const [showCloseModal, setShowCloseModal] = useState(false);
  const [billCard, setBillCard] = useState(null);
  const [pendingChanges, setPendingChanges] = useState([]);
  const [notice, setNotice] = useState('');
  const { run: saveWithApproval, dialogProps: reasonDialog } = useApprovalSave();
  // After a save: closes the form; if it went for approval, says so instead of showing a new row.
  const afterSave = (result, close, tab) => {
    if (result.cancelled) return false;
    close();
    if (result.pending) setNotice('Sent to an admin for approval — it is outside the edit window. Nothing changes until it is approved.');
    else { setNotice(''); showTab(tab); }
    load();
    return true;
  };           // admin's choice; null = card for the placement date
  const [closeFlags, setCloseFlags] = useState({
    recovery_excess_mortality: true,
    recovery_negligence: false,
    recovery_shortage: true,
    recovery_fcr: true,
    recovery_ifft: true,
    fcr_benchmark_enabled: false,
    medicine_use_actual: false,
  });
  const [confirm, setConfirm] = useState({ open: false, title: '', message: '', onConfirm: null, danger: false });
  const [entryForm, setEntryForm] = useState({
    date: todayISO(),
    mortality_count: '', cull_count: '', feed_type: '', feed_bags: '', extra_feeds: [],
    water_consumed_liters: '', avg_body_weight_grams: '', notes: '',
  });
  const [saleForm, setSaleForm] = useState({
    date: todayISO(),
    bird_count: '', total_weight_kg: '', rate_per_kg: '', trader_name: '', notes: '',
  });
  const [medForm, setMedForm] = useState({
    date: todayISO(),
    name: '', dose: '', route: '', cost: '', reason: '',
  });
  const [feedOrderForm, setFeedOrderForm] = useState({ feed_type: '', quantity_bags: '', notes: '' });
  const feedTypes = useFeedTypes();
  // New entries / orders start on the feed the flock is on now (Settings → Feed types order + amounts)
  const defaultFeed = cumulative?.feed_schedule_status?.current_feed_type || feedTypes.active[0]?.key || '';
  // Active types to choose from, plus the record's own (possibly retired) type when editing
  const feedOptions = (current) => feedTypes.types
    .filter(t => t.active || t.key === current)
    .map(t => <option key={t.key} value={t.key}>{t.code}{t.name ? ` (${t.name})` : ''}{t.active ? '' : ' — retired'}</option>);
  const [error, setError] = useState('');
  const [loadError, setLoadError] = useState('');

  const load = async () => {
    try {
      const [flockRes, cumRes] = await Promise.all([flockAPI.get(id), flockAPI.cumulative(id)]);
      setFlock(flockRes.data);
      setCumulative(cumRes.data);
      changeRequestAPI.list({ flock: id, status: 'pending' }).then(r => setPendingChanges(r.data)).catch(() => {});
      try {
        const stockRes = await feedStockAPI.list(flockRes.data.farm);
        if (stockRes.data.length > 0) setFarmStock(stockRes.data[0]);
      } catch {}
    } catch (err) {
      console.error('Flock load error:', err);
      setLoadError(err.response?.status === 404
        ? 'Flock not found — it may have been deleted, or it belongs to a farm outside your regions.'
        : (err.response?.data?.error || err.response?.data?.detail || 'Failed to load flock data. Please try again.'));
    }
  };

  useEffect(() => { load(); }, [id]);

  const resetEntryForm = () => {
    setEntryForm({ date: todayISO(), mortality_count: '', cull_count: '', feed_type: '', feed_bags: '', extra_feeds: [], water_consumed_liters: '', avg_body_weight_grams: '', notes: '' });
    setEditingEntry(null);
  };

  const startEditEntry = (entry) => {
    // The day's feeds: first one in the main row, any others as extra rows
    const [[feed_type, feed_bags] = ['', ''], ...rest] = Object.entries(entry.feed_bags || {});

    setEntryForm({
      date: entry.date,
      mortality_count: entry.daily_mortality || '',
      cull_count: entry.daily_culls || '',
      feed_type,
      feed_bags: feed_bags || '',
      extra_feeds: rest.map(([type, bags]) => ({ type, bags: String(bags) })),
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
    const feedRows = [{ type: entryForm.feed_type || defaultFeed, bags: entryForm.feed_bags }, ...entryForm.extra_feeds];
    const feed_bags = {};
    for (const r of feedRows) {
      const n = parseInt(r.bags) || 0;
      if (n > 0 && r.type) feed_bags[r.type] = (feed_bags[r.type] || 0) + n;
    }
    const bags = Object.values(feed_bags).reduce((a, b) => a + b, 0);
    const mortality = parseInt(entryForm.mortality_count) || 0;
    const culls = parseInt(entryForm.cull_count) || 0;
    const water = parseFloat(entryForm.water_consumed_liters) || 0;
    const bodyWeight = entryForm.avg_body_weight_grams ? parseFloat(entryForm.avg_body_weight_grams) : null;

    // Frontend validations
    if (water < 0) { setError('Water consumed cannot be negative.'); return; }
    if (bodyWeight !== null && bodyWeight < 0) { setError('Body weight cannot be negative.'); return; }
    if (bags < 0) { setError('Feed bags cannot be negative.'); return; }

    // Mortality > 0.4% of live birds — confirm
    if (mortality > 0 && cumulative) {
      const liveBirds = cumulative.live_birds || flock.chick_count;
      const mortPct = (mortality / liveBirds) * 100;
      if (mortPct > 0.4) {
        const ok = window.confirm(
          `⚠️ High mortality alert!\n\n${mortality} deaths = ${mortPct.toFixed(2)}% of ${liveBirds.toLocaleString()} live birds.\n\nAre you sure this is correct?`
        );
        if (!ok) return;
      }
    }

    // Feed bags > daily max estimate — confirm (not block)
    if (bags > 0 && flock) {
      const maxBagsPerDay = Math.ceil((flock.chick_count * 0.2) / 50);
      if (bags > maxBagsPerDay) {
        const ok = window.confirm(
          `⚠️ High feed usage!\n\n${bags} bags entered. Estimated daily max for ${flock.chick_count.toLocaleString()} birds is ~${maxBagsPerDay} bags.\n\nAre you sure this is correct?`
        );
        if (!ok) return;
      }
    }

    const data = {
      flock: id, date: entryForm.date,
      mortality_count: mortality,
      cull_count: culls,
      feed_bags,
      water_consumed_liters: water,
      avg_body_weight_grams: bodyWeight,
      notes: entryForm.notes,
    };
    try {
      const result = await saveWithApproval(extra => (editingEntry
        ? dailyEntryAPI.update(editingEntry.id, { ...data, ...extra })
        : dailyEntryAPI.create({ ...data, ...extra })));
      afterSave(result, () => { setShowEntryForm(false); resetEntryForm(); }, 'entries');
    } catch (err) { setError(getErrorMessage(err)); }
  };

  const handleSale = async (e) => {
    e.preventDefault(); setError('');
    try {
      const result = await saveWithApproval(extra => saleAPI.create({
        flock: id, date: saleForm.date,
        bird_count: parseInt(saleForm.bird_count),
        total_weight_kg: parseFloat(saleForm.total_weight_kg),
        rate_per_kg: saleForm.rate_per_kg ? parseFloat(saleForm.rate_per_kg) : null,
        trader_name: saleForm.trader_name,
        notes: saleForm.notes,
        ...extra,
      }));
      afterSave(result, () => {
        setShowSaleForm(false);
        setSaleForm({ date: todayISO(), bird_count: '', total_weight_kg: '', rate_per_kg: '', trader_name: '', notes: '' });
      }, 'sales');
    } catch (err) { setError(getErrorMessage(err)); }
  };

  const handleMed = async (e) => {
    e.preventDefault(); setError('');
    try {
      const result = await saveWithApproval(extra => medicationAPI.create({
        flock: id, date: medForm.date, name: medForm.name,
        dose: medForm.dose, route: medForm.route,
        cost: parseFloat(medForm.cost) || 0, reason: medForm.reason,
        ...extra,
      }));
      afterSave(result, () => {
        setShowMedForm(false);
        setMedForm({ date: todayISO(), name: '', dose: '', route: '', cost: '', reason: '' });
      }, 'health');
    } catch (err) { setError(getErrorMessage(err)); }
  };

  const handleFeedOrder = async (e) => {
    e.preventDefault(); setError('');
    try {
      await feedOrderAPI.create({
        farm: flock.farm,
        flock: parseInt(id),
        feed_type: feedOrderForm.feed_type || defaultFeed,
        quantity_bags: parseInt(feedOrderForm.quantity_bags),
        notes: feedOrderForm.notes,
      });
      setShowFeedOrderForm(false);
      showTab('feed');                       // show what was just saved
      setFeedOrderForm({ feed_type: '', quantity_bags: '', notes: '' });
      load();
    } catch (err) { setError(getErrorMessage(err)); }
  };

  const exportFlock = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${import.meta.env.VITE_API_URL || '/api'}/flocks/${id}/export/`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `flock_${id}_report.xlsx`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch { alert('Export failed'); }
  };

  if (loadError) return (
    <div className="page">
      <div className="error-msg" style={{ marginBottom: '1rem' }}>{loadError}</div>
      <Link to="/farms" className="btn btn-primary">Back to Farms</Link>
    </div>
  );
  if (!flock || !cumulative) return <FlockDetailSkeleton />;

  const fs = cumulative.feed_schedule_status || {};
  const pctUsed = (used, quota) => quota > 0 ? Math.min(100, Math.round((used / quota) * 100)) : 0;


  const tab = TABS.some(t => t.key === params.get('tab')) ? params.get('tab') : 'overview';
  const counts = { entries: cumulative.entries.length, sales: (cumulative.sales || []).length, health: (flock.medications || []).length };
  const wvs = cumulative.weight_vs_standard;
  const fr = cumulative.feed_reconciliation;
  const totalBags = Object.values(cumulative.feed_by_type || {}).reduce((a, t) => a + t.bags, 0);
  const stockByType = cumulative.flock_feed_stock?.by_type || {};
  // feed types worth showing on this flock: active ones + any old type it actually used or holds
  const flockTypes = feedTypes.types.filter(t => t.active || cumulative.feed_by_type?.[t.key] || stockByType[t.key]);
  // cumulative bags per type by day, for the stacked chart
  const feedSeries = (() => {
    const run = {};
    return cumulative.entries.map(e => {
      for (const [k, v] of Object.entries(e.feed_bags || {})) run[k] = (run[k] || 0) + v;
      return { day_number: e.day_number, ...Object.fromEntries(flockTypes.map(t => [t.key, run[t.key] || 0])) };
    });
  })();

  const hasEntries = cumulative.entries.length > 0;

  return (
    <div className="page flock-page">
      <UnsavedPrompt when={showEntryForm || showSaleForm || showMedForm || showFeedOrderForm} message="You have an unsaved form open. Discard changes?" />
      <nav className="crumbs" aria-label="Breadcrumb">
        <Link to="/farms">Farms</Link><span aria-hidden="true">/</span>
        <Link to={`/farms/${flock.farm}`} className="back-link">{flock.farm_name}</Link><span aria-hidden="true">/</span>
        <span>Flock placed {fmtDate(flock.placement_date)}</span>
      </nav>
      <div className="page-header flock-header">
        <div>
          <h1>{flock.farm_name} — Flock {flock.status === 'active'
            ? <Chip tone={cumulative.live_birds > 0 ? 'ok' : 'info'}>{cumulative.live_birds > 0 ? `Active · day ${flock.age_days}` : 'Sold out · bill due'}</Chip>
            : <Chip>Closed</Chip>}</h1>
          <p className="farm-meta">Placed: {flock.placement_date} &middot; Day {flock.age_days} &middot; {flock.chick_count.toLocaleString()} chicks</p>
        </div>
        <div className="header-actions">
          {flock.status === 'active' && (
            <>
              <button className="btn btn-primary" onClick={() => { setShowEntryForm(!showEntryForm); setShowSaleForm(false); setShowMedForm(false); setShowFeedOrderForm(false); }}>+ Daily Entry</button>
              <button className="btn btn-secondary" onClick={() => { setShowSaleForm(!showSaleForm); setShowEntryForm(false); setShowMedForm(false); setShowFeedOrderForm(false); }}>+ Sale</button>
              <button className="btn btn-secondary" onClick={() => { setShowMedForm(!showMedForm); setShowEntryForm(false); setShowSaleForm(false); setShowFeedOrderForm(false); }}>+ Medicine</button>
              <button className="btn btn-secondary" onClick={() => { setShowFeedOrderForm(!showFeedOrderForm); setShowEntryForm(false); setShowSaleForm(false); setShowMedForm(false); }}>+ Order Feed</button>
            </>
          )}
          <button className="btn btn-secondary" onClick={exportFlock}>Export</button>
          {flock.status === 'active' && (
            <button className="btn btn-danger" onClick={() => setShowCloseModal(true)}>Close & Generate Bill</button>
          )}
          {flock.status === 'closed' && (
            <Link to={`/flocks/${id}/bill`} className="btn btn-secondary">View Bill</Link>
          )}
        </div>
      </div>

      {/* Missing price reminder */}
      {cumulative.sales && cumulative.sales.some(s => !s.rate_per_kg) && (
        <div className="alert-banner alert-banner-warning">
          ⚠️ {cumulative.sales.filter(s => !s.rate_per_kg).length} sale(s) missing rate/price — please update to calculate bill correctly
        </div>
      )}

      {error && <div className="error-msg">{error}</div>}
      {notice && <div className="alert-banner alert-banner-success" role="status">{notice}</div>}
      <PendingChanges rows={pendingChanges} onDecided={load} />

      {/* === ALL FORMS — appear right below buttons === */}

      {/* Daily Entry Form */}
      {showEntryForm && (
        <form onSubmit={handleEntry} className="form-card" style={{ marginBottom: '1.5rem' }}>
          <h3>{editingEntry ? 'Edit Daily Entry' : 'Add Daily Entry'}</h3>
          <div className="form-row">
            <div className="form-group"><label>Date *</label><input type="date" value={entryForm.date} onChange={e => setEntryForm({ ...entryForm, date: e.target.value })} required disabled={!!editingEntry} min={flock.placement_date} max={todayISO()} /></div>
            <div className="form-group"><label>Mortality</label><input type="text" inputMode="numeric" pattern="[0-9]*" value={entryForm.mortality_count} onChange={e => setEntryForm({ ...entryForm, mortality_count: e.target.value })} placeholder="0" /></div>
            <div className="form-group"><label>Culls</label><input type="text" inputMode="numeric" pattern="[0-9]*" value={entryForm.cull_count} onChange={e => setEntryForm({ ...entryForm, cull_count: e.target.value })} placeholder="0" /></div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Feed Type</label>
              <select value={entryForm.feed_type || defaultFeed} onChange={e => setEntryForm({ ...entryForm, feed_type: e.target.value })}>
                {feedOptions(entryForm.feed_type)}
              </select>
            </div>
            <div className="form-group"><label>Bags</label><input type="text" inputMode="numeric" pattern="[0-9]*" value={entryForm.feed_bags} onChange={e => setEntryForm({ ...entryForm, feed_bags: e.target.value })} placeholder="0" /><small className="field-hint">1 bag = 50 kg</small></div>
          </div>
          {entryForm.extra_feeds.map((r, i) => (
            <div className="form-row" key={i}>
              <div className="form-group">
                <label htmlFor={`extra-feed-${i}`}>Feed Type {i + 2}</label>
                <select id={`extra-feed-${i}`} value={r.type} onChange={e => setEntryForm({ ...entryForm, extra_feeds: entryForm.extra_feeds.map((x, j) => j === i ? { ...x, type: e.target.value } : x) })}>
                  {feedOptions(r.type)}
                </select>
              </div>
              <div className="form-group"><label htmlFor={`extra-bags-${i}`}>Bags {i + 2}</label>
                <input id={`extra-bags-${i}`} type="text" inputMode="numeric" pattern="[0-9]*" value={r.bags}
                       onChange={e => setEntryForm({ ...entryForm, extra_feeds: entryForm.extra_feeds.map((x, j) => j === i ? { ...x, bags: e.target.value } : x) })} placeholder="0" /></div>
              <div className="form-group form-group-end">
                <button type="button" className="btn-action btn-action-cancel" onClick={() => setEntryForm({ ...entryForm, extra_feeds: entryForm.extra_feeds.filter((_, j) => j !== i) })}>Remove</button>
              </div>
            </div>
          ))}
          {feedTypes.active.length > 1 && (
            <button type="button" className="link-btn" onClick={() => setEntryForm({ ...entryForm, extra_feeds: [...entryForm.extra_feeds, { type: feedTypes.active.find(t => t.key !== (entryForm.feed_type || defaultFeed))?.key || defaultFeed, bags: '' }] })}>
              + Another feed (when two feeds were given this day)</button>
          )}
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
            <div className="form-group"><label>Date *</label><input type="date" value={saleForm.date} onChange={e => setSaleForm({ ...saleForm, date: e.target.value })} required min={flock.placement_date} max={todayISO()} /></div>
            <div className="form-group"><label>Trader / Buyer *</label><input value={saleForm.trader_name} onChange={e => setSaleForm({ ...saleForm, trader_name: e.target.value })} required placeholder="e.g. Raju Traders" /></div>
          </div>
          <div className="form-row">
            <div className="form-group"><label>Birds *</label><input type="text" inputMode="numeric" pattern="[0-9]*" value={saleForm.bird_count} onChange={e => setSaleForm({ ...saleForm, bird_count: e.target.value })} required /></div>
            <div className="form-group"><label>Total Weight (kg) *</label><input type="text" inputMode="decimal" value={saleForm.total_weight_kg} onChange={e => setSaleForm({ ...saleForm, total_weight_kg: e.target.value })} required /></div>
            <div className="form-group"><label>Rate (₹/kg)</label><input type="text" inputMode="decimal" value={saleForm.rate_per_kg} onChange={e => setSaleForm({ ...saleForm, rate_per_kg: e.target.value })} placeholder="Can add later" /></div>
          </div>
          <div className="form-group"><label>Notes</label><input value={saleForm.notes} onChange={e => setSaleForm({ ...saleForm, notes: e.target.value })} /></div>
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
            <div className="form-group"><label>Date *</label><input type="date" value={medForm.date} onChange={e => setMedForm({ ...medForm, date: e.target.value })} required min={flock.placement_date} max={todayISO()} /></div>
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
              {flockTypes.map(t => <FeedBadge key={t.key} type={t.key}>{t.code}: {farmStock.stock[t.key] || 0} bags</FeedBadge>)}
            </div>
          )}
          <div className="form-row">
            <div className="form-group">
              <label>Feed Type *</label>
              <select value={feedOrderForm.feed_type || defaultFeed} onChange={e => setFeedOrderForm({ ...feedOrderForm, feed_type: e.target.value })}>
                {feedOptions(feedOrderForm.feed_type)}
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

      {cumulative.reconciliation && !cumulative.reconciliation.is_balanced && (
        <div className="alert-banner alert-banner-danger">
          ⚠️ Population mismatch: {cumulative.reconciliation.accounted.toLocaleString()} birds accounted
          (mortality {cumulative.reconciliation.mortality} + culls {cumulative.reconciliation.culls} + sold {cumulative.reconciliation.sold})
          exceed the {cumulative.reconciliation.opening.toLocaleString()} placed by {cumulative.reconciliation.overcount.toLocaleString()}.
          Check for an over-counted sale or mortality entry.
        </div>
      )}


      <div className="tabs" role="tablist" aria-label="Flock sections">
        {TABS.map(t => (
          <button key={t.key} type="button" role="tab" id={`tab-${t.key}`} aria-selected={tab === t.key} aria-controls="flock-tabpanel"
                  className={`tab ${tab === t.key ? 'on' : ''}`} onClick={() => showTab(t.key)}>
            {t.label}{counts[t.key] ? <span className="tab-count">{counts[t.key]}</span> : null}
          </button>
        ))}
      </div>

      <div id="flock-tabpanel" role="tabpanel" aria-labelledby={`tab-${tab}`} className="tabpanel">
      {tab === 'overview' && (
        <div className="flock-overview">
          <div className="flock-main">
            <div className="stats-grid tiles tiles-4">
              <StatTile label="Live birds" value={fmtNum(cumulative.live_birds)} note={`of ${fmtNum(flock.chick_count)} placed`} />
              <StatTile label="Mortality" value={fmtNum(flock.total_mortality)} unit={`${flock.mortality_percentage}%`}
                        tone={flock.mortality_percentage > 5 ? 'danger' : undefined}
                        note={flock.total_culls ? `+ ${flock.total_culls} culls (${flock.cull_percentage}%)` : 'No culls'}
                        trend={cumulative.entries.map(e => e.daily_mortality)} trendColor="var(--warning)" />
              <StatTile label="FCR" value={cumulative.fcr ?? '—'} note={cumulative.epef != null ? `EPEF ${cumulative.epef}` : 'feed kg ÷ live kg'} />
              {wvs ? (
                <StatTile label={`Weight vs target (d${wvs.day})`} value={`${wvs.actual_g}`} unit="g"
                          tone={wvs.status === 'below' ? 'danger' : wvs.status === 'above' ? 'ok' : undefined}
                          note={`${wvs.variance_pct > 0 ? '+' : ''}${wvs.variance_pct}% vs ${wvs.standard_g} g`} />
              ) : <StatTile label="Weight vs target" value="—" note="No weight recorded yet" />}
            </div>

            {!hasEntries && (
              <div className="empty-state">
                <p>No entries yet. Click "+ Daily Entry" to start recording.</p>
              </div>
            )}
            {hasEntries && (
              <>
          {/* Body Weight vs Standard Curve */}
          {!cumulative.entries.some(e => e.avg_body_weight_grams) && (
            <p className="note-line">Body weight: none recorded yet. Add a weight in a daily entry to compare with the Cobb 400 standard.</p>
          )}
          {cumulative.entries.some(e => e.avg_body_weight_grams) && (
            <>
              <h2 className="section-h">Body Weight vs Cobb 400 Standard</h2>
              <div className="chart-container">
                <ResponsiveContainer width="100%" height={350}>
                  <LineChart>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E4EAF0" vertical={false} />
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
                      stroke="#8DA2B8"
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
                      stroke="#0F766E"
                      strokeWidth={2.5}
                      dot={{ r: 5, fill: '#0F766E' }}
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
                          const pctNum = (diff / e.standard_weight_grams) * 100;
                          const pct = pctNum.toFixed(1);
                          const status = pctNum > 3 ? 'above' : pctNum < -3 ? 'below' : 'on_track';
                          return (
                            <tr key={i}>
                              <td>{e.day_number}</td>
                              <td>{e.date}</td>
                              <td><strong>{e.avg_body_weight_grams}</strong></td>
                              <td>{e.standard_weight_grams}</td>
                              <td className={status === 'below' ? 'text-danger' : status === 'above' ? 'text-ok' : ''}>
                                {diff > 0 ? '+' : ''}{diff.toFixed(0)} g ({pct}%)
                              </td>
                              <td>
                                <span className={`weight-status weight-${status}`}>
                                  {status === 'above' ? '▲ Above' : status === 'below' ? '▼ Below' : '● On track'}
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
          <h2 className="section-h">Mortality</h2>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={cumulative.entries}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E4EAF0" vertical={false} />
                <XAxis dataKey="day_number" /><YAxis /><Tooltip /><Legend />
                <Line type="monotone" dataKey="cumulative_mortality" name="Cumulative" stroke="#B42318" strokeWidth={2} dot={{ r: 3 }} />
                <Line type="monotone" dataKey="daily_mortality" name="Daily" stroke="#C2410C" strokeWidth={1.5} strokeDasharray="4 4" dot={{ r: 2 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
              </>
            )}
          </div>

          <aside className="flock-aside">
            <Panel title="Summary">
              <dl className="kv kv-panel">
                <dt>Placed</dt><dd>{fmtDate(flock.placement_date)}</dd>
                <dt>Chicks</dt><dd className="num">{fmtNum(flock.chick_count)}</dd>
                <dt>Age</dt><dd className="num">{flock.age_days} days</dd>
                <dt>Sold</dt><dd className="num">{fmtNum(cumulative.total_sold_birds)} · {fmtNum(cumulative.total_sold_weight_kg)} kg</dd>
                <dt>Feed used</dt><dd className="num">{totalBags.toFixed(1)} bags</dd>
                {fr && <><dt>Dispatched vs fed</dt><dd className={`num ${fr.is_balanced ? '' : 'tone-danger'}`}>{fr.dispatched_bags} / {fr.consumed_bags}{fr.is_balanced ? '' : ` (${fr.variance_bags > 0 ? '+' : ''}${fr.variance_bags})`}</dd></>}
                <dt>Current feed</dt><dd>{fs.current_feed_type ? <FeedBadge type={fs.current_feed_type} /> : '—'}</dd>
                <dt>Medicine cost</dt><dd className="num">₹{fmtNum(flock.total_medication_cost)}</dd>
              </dl>
            </Panel>
      {/* Performance scorecard */}
      {cumulative.scorecard && cumulative.scorecard.components.length > 0 && (
        <div className={`scorecard scorecard-${cumulative.scorecard.rating.toLowerCase()}`}>
          <div className="scorecard-head">
            <div>
              <span className="scorecard-label">Performance</span>
              <span className="scorecard-rating">{cumulative.scorecard.rating}</span>
            </div>
            <div className="scorecard-score">
              {cumulative.scorecard.overall_score}<small>/100</small>
              {cumulative.scorecard.farmer_grade && (
                <span className="scorecard-grade">Grade {cumulative.scorecard.farmer_grade}</span>
              )}
            </div>
          </div>
          <div className="scorecard-bars">
            {cumulative.scorecard.components.map((c) => (
              <div className="scorecard-bar" key={c.label}>
                <div className="scorecard-bar-top">
                  <span className="scorecard-bar-label">{c.label}</span>
                  <span className="scorecard-bar-detail">{c.detail}</span>
                </div>
                <div className="scorecard-track">
                  <div className="scorecard-fill" style={{ width: `${Math.max(0, Math.min(100, c.score))}%` }}></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
            <ChickQualityCard flock={flock} canEdit={canEditFarm(flock.farm)} onSaved={load} />
          </aside>
        </div>
      )}

      {tab === 'entries' && (hasEntries ? (
        <>
          <h2 className="section-h">Daily Entries</h2>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Day</th><th>Date</th><th>Mort.</th><th>Cum.M</th><th>M%</th>
                  <th>Feed</th><th>Bags</th><th>Cum (bags)</th><th>Cum (kg)</th><th>Water</th><th>Wt(g)</th><th>Std(g)</th><th>Entered by</th>{flock.status === 'active' && <th>Actions</th>}
                </tr>
              </thead>
              <tbody>
                {cumulative.entries.map((e, i) => {
                  const dayFeeds = Object.keys(e.feed_bags || {});
                  const feedBags = e.daily_feed_bags || 0;
                  return (
                    <tr key={i}>
                      <td>{e.day_number}</td><td>{e.date}</td>
                      <td>{e.daily_mortality}</td><td>{e.cumulative_mortality}</td>
                      <td className={e.mortality_percentage > 5 ? 'text-danger' : ''}>{e.mortality_percentage}%</td>
                      <td>{dayFeeds.length ? dayFeeds.map(k => <FeedBadge key={k} type={k}>{feedTypes.code(k)}{dayFeeds.length > 1 ? ` ${e.feed_bags[k]}` : ''}</FeedBadge>) : '—'}</td>
                      <td>{feedBags || '—'}</td>
                      <td>{e.cumulative_feed_bags}</td><td>{e.cumulative_feed_kg}</td>
                      <td>{e.water_liters}</td><td>{e.avg_body_weight_grams || '—'}</td><td className="text-muted-cell">{e.standard_weight_grams}</td>
                      <td className="cell-by">{e.entered_by_name || <span className="muted">—</span>}{e.edited_by_name && e.edited_by_name !== e.entered_by_name && <span className="cell-sub">edited by {e.edited_by_name}</span>}</td>
                      {flock.status === 'active' && (
                        <td className="entry-actions">
                          <button className="btn-action btn-action-edit" onClick={() => startEditEntry(e)}>Edit</button>
                          <button className="btn-action btn-action-cancel" onClick={() => setConfirm({
                            open: true, danger: true,
                            title: 'Delete Entry',
                            message: `Delete daily entry for ${e.date}? Its mortality, feed and weight data will be removed from this flock. An admin can restore it from the Recycle Bin.`,
                            onConfirm: async () => {
                              setConfirm({ ...confirm, open: false });
                              try {
                                const result = await saveWithApproval(extra => dailyEntryAPI.delete(e.id, extra.change_reason ? extra : null));
                                if (!result.cancelled) {
                                  setNotice(result.pending ? 'Delete sent to an admin for approval — it is outside the edit window.' : '');
                                  load();
                                }
                              } catch (err) { setError(getErrorMessage(err)); }
                            }
                          })}>Delete</button>
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      ) : <div className="empty-state"><p>No entries yet. Click "+ Daily Entry" to start recording.</p></div>)}

      {tab === 'sales' && (
        (cumulative.sales || []).length === 0 ? <div className="empty-state"><p>No sales recorded yet.</p></div> : (
      <>
          <h2 className="section-h">Sales / Liftings</h2>
          <div className="table-wrapper">
            <table>
              <thead><tr><th>Date</th><th>Trader</th><th>Birds</th><th>Weight</th><th>Avg/Bird</th><th>Rate</th><th>Amount</th><th>Notes</th><th>Entered by</th></tr></thead>
              <tbody>
                {cumulative.sales.map(s => (
                  <tr key={s.id} className={!s.rate_per_kg ? 'row-missing-price' : ''}>
                    <td>{s.date}</td>
                    <td>{s.trader_name || '—'}</td>
                    <td>{s.bird_count.toLocaleString()}</td>
                    <td>{parseFloat(s.total_weight_kg).toLocaleString()} kg</td>
                    <td>{s.avg_weight_kg} kg</td>
                    <td>{s.rate_per_kg ? `₹${s.rate_per_kg}` : <span className="text-danger">Missing</span>}</td>
                    <td>{s.rate_per_kg ? `₹${(parseFloat(s.total_weight_kg) * parseFloat(s.rate_per_kg)).toLocaleString()}` : '—'}</td>
                    <td>{s.notes || '—'}</td>
                    <td className="cell-by">{s.entered_by_name || <span className="muted">—</span>}{s.edited_by_name && s.edited_by_name !== s.entered_by_name && <span className="cell-sub">edited by {s.edited_by_name}</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ))}

      {tab === 'feed' && (
        <>
          {flock.status === 'active' && cumulative.flock_feed_stock && (
            <div className="farm-stock-bar">
              <strong>This Flock's Feed Stock:</strong>
              {flockTypes.map(t => (
                <FeedBadge key={t.key} type={t.key} className={(stockByType[t.key] || 0) <= 0 ? 'stock-low' : ''}>{t.code}: {stockByType[t.key] || 0}</FeedBadge>
              ))}
              <span>Total: {cumulative.flock_feed_stock.total} bags</span>
              {cumulative.flock_feed_stock.total <= 0 && <span className="text-danger" style={{ fontSize: '0.8rem' }}>Order feed for this flock</span>}
            </div>
          )}
          <h2 className="section-h">Feed Schedule</h2>
      <div className="feed-progress-grid">
        {(fs.types || []).map(r => (
          <div className="feed-progress-card" key={r.feed_type}>
            <div className="feed-progress-header">
              <FeedBadge type={r.feed_type} />
              <span>{r.estimate_bags != null ? `${r.used_bags} / ~${r.estimate_bags} bags (${r.used_kg} / ~${r.estimate_kg} kg)` : `${r.used_bags} bags (${r.used_kg} kg)`}</span>
            </div>
            {r.estimate_kg != null && (
              <div className="progress-bar"><div className="progress-fill" style={{ width: `${pctUsed(r.used_kg, r.estimate_kg)}%`, background: feedTypes.colour(r.feed_type) }}></div></div>
            )}
            <span className="feed-progress-sub">{r.per_bird_kg != null
              ? `${r.remaining_kg} kg remaining (est.) · ~${r.per_bird_kg} kg/bird`
              : 'No fixed amount — given after the feeds before it'}</span>
          </div>
        ))}
      </div>
          {hasEntries && (
            <>
          <h2 className="section-h">Feed by Type — Cumulative (bags)</h2>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={feedSeries} margin={{ bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E4EAF0" vertical={false} />
                <XAxis dataKey="day_number" tickFormatter={d => `d${d}`} />
                <YAxis /><Tooltip labelFormatter={d => `Day ${d}`} /><Legend wrapperStyle={{ paddingTop: 8 }} />
                {flockTypes.map(t => (
                  <Area key={t.key} type="monotone" dataKey={t.key} name={`${t.code} (bags)`} stackId="1"
                        stroke={t.colour} fill={t.colour} fillOpacity={0.18} />
                ))}
              </AreaChart>
            </ResponsiveContainer>
          </div>
            </>
          )}
      <BagCountSection flock={flock} canEdit={canEditFarm(flock.farm)} isAdmin={isAdmin} />
        </>
      )}

      {tab === 'health' && (
        <>
          {cumulative.water_alerts && cumulative.water_alerts.length > 0 && (
            <div className="alert-banner alert-banner-warning">
              💧 Water:feed ratio out of range on {cumulative.water_alerts.length} day{cumulative.water_alerts.length > 1 ? 's' : ''}:
              {' '}{cumulative.water_alerts.slice(0, 3).map(a => `d${a.day} ${a.ratio}L/kg (${a.status})`).join(', ')}
              {cumulative.water_alerts.length > 3 ? '…' : ''}.
              {' '}Low can signal illness/under-drinking; high can signal heat stress or spillage.
            </div>
          )}
          {(flock.medications || []).length === 0 ? <div className="empty-state"><p>No medicines or vaccines recorded yet.</p></div> : (
      <>
          <h2 className="section-h">Medications / Vaccines <small style={{ fontWeight: 400, color: '#6b6b6b' }}>(Total: ₹{parseFloat(flock.total_medication_cost).toLocaleString()})</small></h2>
          <div className="table-wrapper">
            <table>
              <thead><tr><th>Date</th><th>Day</th><th>Name</th><th>Dose</th><th>Route</th><th>Cost (₹)</th><th>Reason</th><th>Entered by</th></tr></thead>
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
                    <td className="cell-by">{m.entered_by_name || <span className="muted">—</span>}{m.edited_by_name && m.edited_by_name !== m.entered_by_name && <span className="cell-sub">edited by {m.edited_by_name}</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
          )}
        </>
      )}

      {tab === 'documents' && <DocumentsSection flockId={flock.id} canEdit={canEditFarm(flock.farm)} />}
      </div>

      {/* Close Flock Modal */}
      {showCloseModal && (
        <div className="modal-overlay" onClick={() => setShowCloseModal(false)}>
          <div className="modal-card" style={{ maxWidth: 560 }} onClick={e => e.stopPropagation()}>
            <h3 className="modal-title">Close Flock & Generate Bill</h3>
            <p className="modal-message">Review billing settings before generating the bill. This cannot be undone.</p>
            {cumulative.feed_reconciliation && !cumulative.feed_reconciliation.is_balanced && (
              <div className="alert-banner alert-banner-warning" style={{ marginBottom: '1rem' }}>
                ⚠️ Feed variance: {cumulative.feed_reconciliation.dispatched_bags} bags dispatched vs {cumulative.feed_reconciliation.consumed_bags} consumed
                ({cumulative.feed_reconciliation.variance_bags > 0 ? '+' : ''}{cumulative.feed_reconciliation.variance_bags} bags, {cumulative.feed_reconciliation.variance_pct}%).
                {cumulative.feed_reconciliation.status === 'over_dispatched'
                  ? ' More feed was sent than fed here — check for diversion or unused stock.'
                  : ' More feed was fed than recorded as dispatched — check for missing dispatch records.'}
              </div>
            )}

            {isAdmin && <BillCardPicker flockId={id} flags={closeFlags} value={billCard} onChange={setBillCard} />}

            <div style={{ marginBottom: '1rem' }}>
              <label className="bill-flag-title">Medicine Cost Method</label>
              <div className="bill-flag-row">
                <label className="toggle-label">
                  <input type="checkbox" checked={closeFlags.medicine_use_actual} onChange={e => setCloseFlags({ ...closeFlags, medicine_use_actual: e.target.checked })} />
                  Use actual medicine cost
                </label>
                <span className="bill-flag-hint">{closeFlags.medicine_use_actual ? 'Actual cost from records' : 'Chicks × rate on the card (unless the card says actual)'}</span>
              </div>
            </div>

            <div style={{ marginBottom: '1.25rem' }}>
              <label className="bill-flag-title">Recoveries to Apply</label>
              <div className="bill-flags-grid">
                <label className="toggle-label"><input type="checkbox" checked={closeFlags.recovery_excess_mortality} onChange={e => setCloseFlags({ ...closeFlags, recovery_excess_mortality: e.target.checked })} /> 1st Week Excess Mortality</label>
                <label className="toggle-label"><input type="checkbox" checked={closeFlags.recovery_negligence} onChange={e => setCloseFlags({ ...closeFlags, recovery_negligence: e.target.checked })} /> Farmer Negligence</label>
                <label className="toggle-label"><input type="checkbox" checked={closeFlags.recovery_shortage} onChange={e => setCloseFlags({ ...closeFlags, recovery_shortage: e.target.checked })} /> Bird Shortage</label>
                <label className="toggle-label"><input type="checkbox" checked={closeFlags.recovery_fcr} onChange={e => setCloseFlags({ ...closeFlags, recovery_fcr: e.target.checked })} /> FCR Recovery</label>
                <label className="toggle-label"><input type="checkbox" checked={closeFlags.recovery_ifft} onChange={e => setCloseFlags({ ...closeFlags, recovery_ifft: e.target.checked })} /> IFFT Charges</label>
                <label className="toggle-label"><input type="checkbox" checked={closeFlags.fcr_benchmark_enabled} onChange={e => setCloseFlags({ ...closeFlags, fcr_benchmark_enabled: e.target.checked })} /> FCR Benchmark (premium/deduction)</label>
              </div>
            </div>

            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setShowCloseModal(false)}>Cancel</button>
              <button className="btn btn-danger" onClick={async () => {
                setShowCloseModal(false);
                try {
                  await billAPI.closeAndBill(id, { ...closeFlags, ...(isAdmin && billCard ? { rate_card: billCard } : {}) });
                  navigate(`/flocks/${id}/bill`);
                } catch (err) {
                  alert(getErrorMessage(err));
                }
              }}>Generate Bill</button>
            </div>
          </div>
        </div>
      )}

      <ReasonDialog {...reasonDialog} />
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
