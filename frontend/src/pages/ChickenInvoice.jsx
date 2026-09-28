import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { chickenAPI } from '../api/client';

// Seller details — edit here to change what prints on every invoice.
const SELLER = {
  name: 'Sai Charan Chicken Center',
  line1: 'Nagaram, Jangaon',
  line2: 'Telangana - 506167',
  phone: '',
};

export default function ChickenInvoice() {
  const { id } = useParams();
  const [s, setS] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    chickenAPI.sale(id).then(r => { setS(r.data); setLoading(false); }).catch(() => setLoading(false));
  }, [id]);

  const fmt = (n) => n != null ? Number(n).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '0.00';

  const shareWhatsApp = () => {
    if (!s) return;
    const msg = `*${SELLER.name}*\nInvoice #${s.id} — ${s.date}\n${s.item_name}: ${fmt(s.weight_kg)} kg × ₹${fmt(s.rate_per_kg)}\nAmount: ₹${fmt(s.amount)}\nDue on this bill: ₹${fmt(s.amount_due)}\nTotal outstanding: ₹${fmt(s.party_overall_balance)}\nThank you!`;
    const phone = (s.party_phone || '').replace(/\D/g, '');
    const wa = phone.length >= 10 ? `https://wa.me/91${phone.slice(-10)}?text=${encodeURIComponent(msg)}` : `https://wa.me/?text=${encodeURIComponent(msg)}`;
    window.open(wa, '_blank');
  };

  if (loading) return <div className="loading">Loading…</div>;
  if (!s) return <div className="empty-state"><p>Invoice not found.</p></div>;

  return (
    <div className="page bill-page">
      <div className="bill-no-print">
        <button className="back-link" onClick={() => navigate('/chicken/transactions')}>&larr; Transactions</button>
        <div style={{ float: 'right', display: 'flex', gap: '0.5rem' }}>
          <button className="btn btn-secondary" onClick={shareWhatsApp}>Share on WhatsApp</button>
          <button className="btn btn-primary" onClick={() => window.print()}>Print</button>
        </div>
      </div>

      <div className="bill-a4" style={{ maxWidth: 640 }}>
        {s.is_reversed && <div className="error-msg" style={{ marginBottom: '1rem' }}>This bill has been reversed.</div>}

        <div className="bill-top">
          <div className="bill-company">
            <h2>{SELLER.name}</h2>
            <p>{SELLER.line1}<br />{SELLER.line2}{SELLER.phone ? <><br />{SELLER.phone}</> : null}</p>
          </div>
          <div className="bill-top-right">
            <span className="bill-date"><strong>Invoice #{s.id}</strong></span>
            <span className="bill-date">{s.date}</span>
            <span className={`wa-badge ${s.status === 'PAID' ? 'wa-sent' : s.status === 'PARTLY' ? 'wa-pending' : 'wa-failed'}`}>{s.status}</span>
          </div>
        </div>

        <div className="bill-info-row">
          <span><strong>Bill To:</strong> {s.party_name}</span>
          {s.party_phone && <span>{s.party_phone}</span>}
          {s.party_address && <span>{s.party_address}</span>}
        </div>

        <table className="bill-t" style={{ marginTop: '1rem' }}>
          <thead>
            <tr><th>Item</th><th>Weight</th><th>Rate</th><th style={{ textAlign: 'right' }}>Amount</th></tr>
          </thead>
          <tbody>
            {(s.lines && s.lines.length ? s.lines : [{ id: 0, item_name: s.item_name, weight_kg: s.weight_kg, rate_per_kg: s.rate_per_kg, amount: s.amount }]).map(l => (
              <tr key={l.id}>
                <td>{l.item_name}</td>
                <td>{fmt(l.weight_kg)} kg</td>
                <td>₹{fmt(l.rate_per_kg)}/kg</td>
                <td style={{ textAlign: 'right' }}>₹{fmt(l.amount)}</td>
              </tr>
            ))}
            <tr className="bill-t-total">
              <td colSpan={3}>Total</td>
              <td style={{ textAlign: 'right' }}>₹{fmt(s.amount)}</td>
            </tr>
          </tbody>
        </table>

        <div className="bill-final-compact" style={{ marginTop: '1rem' }}>
          <div className="bill-final-line"><span>Received on this bill</span><span>₹{fmt(s.amount_received)}</span></div>
          <div className="bill-final-line"><span>Due on this bill</span><span className={s.amount_due > 0 ? 'text-danger' : ''}>₹{fmt(s.amount_due)}</span></div>
          <div className="bill-final-line bill-final-net"><span>Total Outstanding</span><span>₹{fmt(s.party_overall_balance)}</span></div>
        </div>

        <p className="farm-meta" style={{ marginTop: '1.5rem', textAlign: 'center' }}>Thank you for your business!</p>
      </div>
    </div>
  );
}
