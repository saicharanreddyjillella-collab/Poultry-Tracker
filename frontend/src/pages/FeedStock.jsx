import { useState, useEffect } from 'react';
import { ReportSkeleton } from '../components/Skeletons';
import { feedOrderAPI, feedStockAPI, feedRateAPI, feedTransferAPI, farmAPI } from '../api/client';
import { useAuth } from '../context/AuthContext';

export default function FeedStock() {
  const { isAdmin, isPlant, canEditFarm } = useAuth();
  const [stock, setStock] = useState([]);
  const [orders, setOrders] = useState([]);
  const [transfers, setTransfers] = useState([]);
  const [farms, setFarms] = useState([]);
  const [feedRates, setFeedRates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showOrderForm, setShowOrderForm] = useState(false);
  const [showRateForm, setShowRateForm] = useState(false);
  const [showTransferForm, setShowTransferForm] = useState(false);
  const [orderForm, setOrderForm] = useState({ farm: '', flock: '', feed_type: 'BPSC', quantity_bags: '', notes: '' });
  const [rateForm, setRateForm] = useState({ week_start_date: new Date().toISOString().split('T')[0], feed_type: 'BFP', rate_per_kg: '', notes: '' });
  const [transferForm, setTransferForm] = useState({ from_farm: '', to_farm: '', feed_type: 'BFP', quantity_bags: '', date: new Date().toISOString().split('T')[0], notes: '' });
  const [filter, setFilter] = useState('all');
  const [error, setError] = useState('');

  const load = async () => {
    try {
      const [stockRes, ordersRes, farmsRes, ratesRes, transfersRes] = await Promise.all([
        feedStockAPI.list(),
        feedOrderAPI.list({ status: filter !== 'all' ? filter : undefined }),
        farmAPI.list(),
        feedRateAPI.list(),
        feedTransferAPI.list(),
      ]);
      setStock(stockRes.data);
      setOrders(ordersRes.data);
      setFarms(farmsRes.data);
      setFeedRates(ratesRes.data);
      setTransfers(transfersRes.data);
    } catch {}
    setLoading(false);
  };

  useEffect(() => { load(); }, [filter]);

  const handleOrder = async (e) => {
    e.preventDefault(); setError('');
    try {
      await feedOrderAPI.create({
        farm: parseInt(orderForm.farm),
        flock: orderForm.flock ? parseInt(orderForm.flock) : null,
        feed_type: orderForm.feed_type,
        quantity_bags: parseInt(orderForm.quantity_bags),
        notes: orderForm.notes,
      });
      setShowOrderForm(false);
      setOrderForm({ farm: '', flock: '', feed_type: 'BPSC', quantity_bags: '', notes: '' });
      load();
    } catch (err) { setError(err.response?.data ? JSON.stringify(err.response.data) : 'Failed'); }
  };

  const handleRate = async (e) => {
    e.preventDefault(); setError('');
    try {
      await feedRateAPI.create(rateForm);
      setShowRateForm(false);
      setRateForm({ week_start_date: new Date().toISOString().split('T')[0], feed_type: 'BFP', rate_per_kg: '', notes: '' });
      load();
    } catch (err) { setError(err.response?.data ? JSON.stringify(err.response.data) : 'Failed'); }
  };

  const handleTransfer = async (e) => {
    e.preventDefault(); setError('');
    try {
      await feedTransferAPI.create({
        from_farm: parseInt(transferForm.from_farm),
        to_farm: parseInt(transferForm.to_farm),
        feed_type: transferForm.feed_type,
        quantity_bags: parseInt(transferForm.quantity_bags),
        date: transferForm.date,
        notes: transferForm.notes,
      });
      setShowTransferForm(false);
      setTransferForm({ from_farm: '', to_farm: '', feed_type: 'BFP', quantity_bags: '', date: new Date().toISOString().split('T')[0], notes: '' });
      load();
    } catch (err) { setError(err.response?.data ? JSON.stringify(err.response.data) : 'Failed'); }
  };

  const handleAction = async (orderId, action) => {
    try {
      if (action === 'sent') await feedOrderAPI.markSent(orderId);
      else if (action === 'delivered') await feedOrderAPI.markDelivered(orderId);
      else if (action === 'cancel') await feedOrderAPI.cancel(orderId);
      load();
    } catch (err) { alert(err.response?.data?.error || 'Action failed'); }
  };

  const fmtDec = (n) => Number(n).toLocaleString('en-IN', { minimumFractionDigits: 1, maximumFractionDigits: 1 });

  // Get latest rate per type
  const latestRates = {};
  feedRates.forEach(r => { if (!latestRates[r.feed_type]) latestRates[r.feed_type] = r; });

  if (loading) return <ReportSkeleton />;

  return (
    <div className="page">
      <div className="page-header">
        <h1>Feed Stock & Orders</h1>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          {isAdmin && <button className="btn btn-secondary" onClick={() => { setShowRateForm(!showRateForm); setShowOrderForm(false); setShowTransferForm(false); }}>Update Rate</button>}
          {!isPlant && <button className="btn btn-secondary" onClick={() => { setShowTransferForm(!showTransferForm); setShowOrderForm(false); setShowRateForm(false); }}>Transfer Feed</button>}
          {!isPlant && <button className="btn btn-primary" onClick={() => { setShowOrderForm(!showOrderForm); setShowRateForm(false); setShowTransferForm(false); }}>+ Order Feed</button>}
        </div>
      </div>

      {error && <div className="error-msg">{error}</div>}

      {/* RATE FORM */}
      {showRateForm && (
        <form onSubmit={handleRate} className="form-card" style={{ marginBottom: '1.5rem' }}>
          <h3>Update Feed Rate</h3>
          <div className="form-row">
            <div className="form-group">
              <label>Week Start Date *</label>
              <input type="date" value={rateForm.week_start_date} onChange={e => setRateForm({ ...rateForm, week_start_date: e.target.value })} required />
            </div>
            <div className="form-group">
              <label>Feed Type *</label>
              <select value={rateForm.feed_type} onChange={e => setRateForm({ ...rateForm, feed_type: e.target.value })}>
                <option value="BPSC">BPSC (Pre-Starter)</option>
                <option value="BSC">BSC (Starter)</option>
                <option value="BFP">BFP (Finisher)</option>
              </select>
            </div>
            <div className="form-group">
              <label>Rate per kg (₹) *</label>
              <input type="text" inputMode="decimal" value={rateForm.rate_per_kg} onChange={e => setRateForm({ ...rateForm, rate_per_kg: e.target.value })} required placeholder="e.g. 32.50" />
            </div>
          </div>
          <div className="form-group">
            <label>Notes</label>
            <input value={rateForm.notes} onChange={e => setRateForm({ ...rateForm, notes: e.target.value })} placeholder="Optional" />
          </div>
          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={() => setShowRateForm(false)}>Cancel</button>
            <button type="submit" className="btn btn-primary">Save Rate</button>
          </div>
        </form>
      )}

      {/* ORDER FORM */}
      {showOrderForm && (
        <form onSubmit={handleOrder} className="form-card" style={{ marginBottom: '1.5rem' }}>
          <h3>Place Feed Order</h3>
          <div className="form-row">
            <div className="form-group">
              <label>Farm *</label>
              <select value={orderForm.farm} onChange={e => setOrderForm({ ...orderForm, farm: e.target.value, flock: '' })} required>
                <option value="">Select farm...</option>
                {farms.map(f => (
                  <option key={f.id} value={f.id}>{f.farm_code} — {f.name}</option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label>Flock *</label>
              <select value={orderForm.flock} onChange={e => setOrderForm({ ...orderForm, flock: e.target.value })} required>
                <option value="">Select flock...</option>
                {orderForm.farm && farms.find(f => String(f.id) === String(orderForm.farm))?.active_flocks?.map(fl => (
                  <option key={fl.id} value={fl.id}>Placed {fl.placement_date} — {fl.chick_count?.toLocaleString()} chicks (Day {fl.age_days})</option>
                ))}
              </select>
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Feed Type *</label>
              <select value={orderForm.feed_type} onChange={e => setOrderForm({ ...orderForm, feed_type: e.target.value })}>
                <option value="BPSC">BPSC (Pre-Starter)</option>
                <option value="BSC">BSC (Starter)</option>
                <option value="BFP">BFP (Finisher)</option>
              </select>
            </div>
            <div className="form-group">
              <label>Quantity (bags) *</label>
              <input type="text" inputMode="numeric" pattern="[0-9]*" value={orderForm.quantity_bags} onChange={e => setOrderForm({ ...orderForm, quantity_bags: e.target.value })} required placeholder="e.g. 10" />
            </div>
          </div>
          <div className="form-group">
            <label>Notes</label>
            <input value={orderForm.notes} onChange={e => setOrderForm({ ...orderForm, notes: e.target.value })} placeholder="Optional" />
          </div>
          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={() => setShowOrderForm(false)}>Cancel</button>
            <button type="submit" className="btn btn-primary">Place Order</button>
          </div>
        </form>
      )}

      {/* TRANSFER FORM */}
      {showTransferForm && (
        <form onSubmit={handleTransfer} className="form-card" style={{ marginBottom: '1.5rem' }}>
          <h3>Transfer Feed Between Farms</h3>
          <div className="form-row">
            <div className="form-group">
              <label>From Farm *</label>
              <select value={transferForm.from_farm} onChange={e => setTransferForm({ ...transferForm, from_farm: e.target.value })} required>
                <option value="">Select...</option>
                {farms.map(f => {
                  const s = stock.find(st => st.farm_id === f.id);
                  return <option key={f.id} value={f.id}>{f.farm_code} — {f.name} {s ? `(${s.stock.total} bags)` : ''}</option>;
                })}
              </select>
            </div>
            <div className="form-group">
              <label>To Farm *</label>
              <select value={transferForm.to_farm} onChange={e => setTransferForm({ ...transferForm, to_farm: e.target.value })} required>
                <option value="">Select...</option>
                {farms.filter(f => String(f.id) !== String(transferForm.from_farm)).map(f => (
                  <option key={f.id} value={f.id}>{f.farm_code} — {f.name}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Feed Type *</label>
              <select value={transferForm.feed_type} onChange={e => setTransferForm({ ...transferForm, feed_type: e.target.value })}>
                <option value="BPSC">BPSC</option>
                <option value="BSC">BSC</option>
                <option value="BFP">BFP</option>
              </select>
            </div>
            <div className="form-group">
              <label>Bags *</label>
              <input type="text" inputMode="numeric" pattern="[0-9]*" value={transferForm.quantity_bags} onChange={e => setTransferForm({ ...transferForm, quantity_bags: e.target.value })} required placeholder="e.g. 5" />
            </div>
            <div className="form-group">
              <label>Date *</label>
              <input type="date" value={transferForm.date} onChange={e => setTransferForm({ ...transferForm, date: e.target.value })} required />
            </div>
          </div>
          <div className="form-group">
            <label>Notes</label>
            <input value={transferForm.notes} onChange={e => setTransferForm({ ...transferForm, notes: e.target.value })} placeholder="e.g. Flock closed, leftover feed" />
          </div>
          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={() => setShowTransferForm(false)}>Cancel</button>
            <button type="submit" className="btn btn-primary">Transfer</button>
          </div>
        </form>
      )}

      {/* CURRENT RATES */}
      <h2 className="section-title">Current Feed Rates</h2>
      <div className="stats-grid" style={{ marginBottom: '1.5rem' }}>
        <div className="stat-card feed-card-bpsc">
          <span className="stat-label">BPSC</span>
          <span className="stat-value">{latestRates.BPSC ? `₹${latestRates.BPSC.rate_per_kg}/kg` : 'Not set'}</span>
          {latestRates.BPSC && <span className="stat-sub">from {latestRates.BPSC.week_start_date}</span>}
        </div>
        <div className="stat-card feed-card-bsc">
          <span className="stat-label">BSC</span>
          <span className="stat-value">{latestRates.BSC ? `₹${latestRates.BSC.rate_per_kg}/kg` : 'Not set'}</span>
          {latestRates.BSC && <span className="stat-sub">from {latestRates.BSC.week_start_date}</span>}
        </div>
        <div className="stat-card feed-card-bfp">
          <span className="stat-label">BFP</span>
          <span className="stat-value">{latestRates.BFP ? `₹${latestRates.BFP.rate_per_kg}/kg` : 'Not set'}</span>
          {latestRates.BFP && <span className="stat-sub">from {latestRates.BFP.week_start_date}</span>}
        </div>
      </div>

      {/* RATE HISTORY */}
      {feedRates.length > 0 && (
        <details className="feed-history" style={{ marginBottom: '1.5rem' }}>
          <summary>Feed Rate History ({feedRates.length} entries)</summary>
          <div className="table-wrapper" style={{ marginTop: '0.5rem' }}>
            <table>
              <thead><tr><th>Week Start</th><th>Type</th><th>Rate (₹/kg)</th><th>Notes</th></tr></thead>
              <tbody>
                {feedRates.map(r => (
                  <tr key={r.id}>
                    <td>{r.week_start_date}</td>
                    <td><span className={`feed-badge feed-badge-${r.feed_type.toLowerCase()}`}>{r.feed_type}</span></td>
                    <td>₹{r.rate_per_kg}</td>
                    <td>{r.notes || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}

      {/* STOCK TABLE */}
      <h2 className="section-title">Current Stock (bags at farm)</h2>
      <div className="table-wrapper" style={{ marginBottom: '2rem' }}>
        <table>
          <thead>
            <tr>
              <th>Farm</th>
              <th>BPSC</th>
              <th>BSC</th>
              <th>BFP</th>
              <th>Total</th>
              <th>Pending Orders</th>
            </tr>
          </thead>
          <tbody>
            {stock.map(s => {
              const totalPending = (s.pending_orders.bpsc || 0) + (s.pending_orders.bsc || 0) + (s.pending_orders.bfp || 0);
              return (
                <tr key={s.farm_id}>
                  <td><span className="farm-code-badge-sm">{s.farm_code}</span> {s.farm_name}</td>
                  <td className={s.stock.bpsc < 0 ? 'text-danger' : s.stock.bpsc <= 2 ? 'text-warning' : ''}>{fmtDec(s.stock.bpsc)}</td>
                  <td className={s.stock.bsc < 0 ? 'text-danger' : s.stock.bsc <= 2 ? 'text-warning' : ''}>{fmtDec(s.stock.bsc)}</td>
                  <td className={s.stock.bfp < 0 ? 'text-danger' : s.stock.bfp <= 2 ? 'text-warning' : ''}>{fmtDec(s.stock.bfp)}</td>
                  <td><strong>{fmtDec(s.stock.total)}</strong></td>
                  <td>{totalPending > 0 ? <span className="order-pending-badge">{fmtDec(totalPending)} bags</span> : '—'}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* ORDERS TABLE */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
        <h2 className="section-title" style={{ margin: 0 }}>Orders</h2>
        <div className="order-filters">
          {['all', 'pending', 'sent', 'delivered'].map(f => (
            <button key={f} className={`order-filter-btn ${filter === f ? 'order-filter-active' : ''}`} onClick={() => setFilter(f)}>
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
      </div>
      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Date</th><th>Farm</th><th>Type</th><th>Bags</th><th>Status</th><th>Ordered By</th><th>Sent</th><th>Delivered</th><th>Notes</th><th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {orders.length === 0 ? (
              <tr><td colSpan={10} style={{ textAlign: 'center', color: '#999', padding: '2rem' }}>No orders found</td></tr>
            ) : orders.map(o => (
              <tr key={o.id}>
                <td>{new Date(o.order_date).toLocaleDateString('en-IN')}</td>
                <td><span className="farm-code-badge-sm">{o.farm_code}</span> {o.farm_name}</td>
                <td><span className={`feed-badge feed-badge-${o.feed_type.toLowerCase()}`}>{o.feed_type}</span></td>
                <td><strong>{o.quantity_bags}</strong></td>
                <td><span className={`order-status order-status-${o.status}`}>{o.status}</span></td>
                <td>{o.ordered_by_name}</td>
                <td>{o.sent_date ? new Date(o.sent_date).toLocaleDateString('en-IN') : '—'}</td>
                <td>{o.delivered_date ? new Date(o.delivered_date).toLocaleDateString('en-IN') : '—'}</td>
                <td>{o.notes || '—'}</td>
                <td className="order-actions">
                  {o.status === 'pending' && (isPlant || isAdmin) && (
                    <button className="btn-action btn-action-send" onClick={() => handleAction(o.id, 'sent')}>Mark Sent</button>
                  )}
                  {o.status === 'sent' && !isPlant && (
                    <button className="btn-action btn-action-deliver" onClick={() => handleAction(o.id, 'delivered')}>Confirm Delivery</button>
                  )}
                  {(o.status === 'pending' || o.status === 'sent') && !isPlant && (
                    <button className="btn-action btn-action-cancel" onClick={() => handleAction(o.id, 'cancel')}>Cancel</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* TRANSFERS */}
      {transfers.length > 0 && (
        <>
          <h2 className="section-title" style={{ marginTop: '2rem' }}>Feed Transfers</h2>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr><th>Date</th><th>From</th><th>To</th><th>Type</th><th>Bags</th><th>By</th><th>Notes</th></tr>
              </thead>
              <tbody>
                {transfers.map(t => (
                  <tr key={t.id}>
                    <td>{t.date}</td>
                    <td><span className="farm-code-badge-sm">{t.from_farm_code}</span> {t.from_farm_name}</td>
                    <td><span className="farm-code-badge-sm">{t.to_farm_code}</span> {t.to_farm_name}</td>
                    <td><span className={`feed-badge feed-badge-${t.feed_type.toLowerCase()}`}>{t.feed_type}</span></td>
                    <td><strong>{t.quantity_bags}</strong></td>
                    <td>{t.transferred_by_name}</td>
                    <td>{t.notes || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
