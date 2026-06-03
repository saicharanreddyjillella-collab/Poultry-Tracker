import { useState, useEffect } from 'react';
import { feedOrderAPI, feedStockAPI, farmAPI } from '../api/client';
import { useAuth } from '../context/AuthContext';

export default function FeedStock() {
  const { isAdmin, isPlant, canEditFarm } = useAuth();
  const [stock, setStock] = useState([]);
  const [orders, setOrders] = useState([]);
  const [farms, setFarms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showOrderForm, setShowOrderForm] = useState(false);
  const [orderForm, setOrderForm] = useState({ farm: '', feed_type: 'BPSC', quantity_bags: '', notes: '' });
  const [filter, setFilter] = useState('all'); // all, pending, sent, delivered
  const [error, setError] = useState('');

  const load = async () => {
    try {
      const [stockRes, ordersRes, farmsRes] = await Promise.all([
        feedStockAPI.list(),
        feedOrderAPI.list({ status: filter !== 'all' ? filter : undefined }),
        farmAPI.list(),
      ]);
      setStock(stockRes.data);
      setOrders(ordersRes.data);
      setFarms(farmsRes.data);
    } catch {}
    setLoading(false);
  };

  useEffect(() => { load(); }, [filter]);

  const handleOrder = async (e) => {
    e.preventDefault();
    setError('');
    try {
      await feedOrderAPI.create({
        farm: parseInt(orderForm.farm),
        feed_type: orderForm.feed_type,
        quantity_bags: parseInt(orderForm.quantity_bags),
        notes: orderForm.notes,
      });
      setShowOrderForm(false);
      setOrderForm({ farm: '', feed_type: 'BPSC', quantity_bags: '', notes: '' });
      load();
    } catch (err) {
      setError(err.response?.data ? JSON.stringify(err.response.data) : 'Failed to place order');
    }
  };

  const handleAction = async (orderId, action) => {
    try {
      if (action === 'sent') await feedOrderAPI.markSent(orderId);
      else if (action === 'delivered') await feedOrderAPI.markDelivered(orderId);
      else if (action === 'cancel') await feedOrderAPI.cancel(orderId);
      load();
    } catch (err) {
      alert(err.response?.data?.error || 'Action failed');
    }
  };

  const fmtDec = (n) => Number(n).toLocaleString('en-IN', { minimumFractionDigits: 1, maximumFractionDigits: 1 });

  if (loading) return <div className="loading">Loading...</div>;

  return (
    <div className="page">
      <div className="page-header">
        <h1>Feed Stock & Orders</h1>
        {!isPlant && <button className="btn btn-primary" onClick={() => setShowOrderForm(!showOrderForm)}>+ Order Feed</button>}
      </div>

      {/* STOCK TABLE */}
      <h2 className="section-title">Current Stock (bags at farm)</h2>
      <div className="table-wrapper" style={{ marginBottom: '2rem' }}>
        <table>
          <thead>
            <tr>
              <th>Farm</th>
              <th className="stock-col-bpsc">BPSC</th>
              <th className="stock-col-bsc">BSC</th>
              <th className="stock-col-bfp">BFP</th>
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

      {/* ORDER FORM */}
      {showOrderForm && (
        <form onSubmit={handleOrder} className="form-card" style={{ marginBottom: '1.5rem' }}>
          <h3>Place Feed Order</h3>
          {error && <div className="error-msg">{error}</div>}
          <div className="form-row">
            <div className="form-group">
              <label>Farm *</label>
              <select value={orderForm.farm} onChange={e => setOrderForm({ ...orderForm, farm: e.target.value })} required>
                <option value="">Select farm...</option>
                {farms.map(f => (
                  <option key={f.id} value={f.id}>{f.farm_code} — {f.name}</option>
                ))}
              </select>
            </div>
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
              <input type="number" step="1" min="1" value={orderForm.quantity_bags} onChange={e => setOrderForm({ ...orderForm, quantity_bags: e.target.value })} required placeholder="e.g. 10" />
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
    </div>
  );
}
