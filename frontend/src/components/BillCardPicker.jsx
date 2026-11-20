import { useEffect, useState } from 'react';
import { billAPI, rateCardAPI, getErrorMessage } from '../api/client';
import { fmtNum } from '../utils/format';

const rs = (v, d = 2) => (v == null ? '—' : `₹${fmtNum(v, d)}`);

/** Admin: choose the rate card for this bill and see what it comes to before generating it.
 *  `value` is the chosen card id (null = the card for the placement date). */
export default function BillCardPicker({ flockId, flags, value, onChange }) {
  const [cards, setCards] = useState([]);
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => { rateCardAPI.list().then(r => setCards(r.data)).catch(() => {}); }, []);

  useEffect(() => {
    let live = true;
    billAPI.preview(flockId, { ...flags, ...(value ? { rate_card: value } : {}) })
      .then(r => { if (live) { setPreview(r.data); setError(''); } })
      .catch(err => { if (live) setError(getErrorMessage(err)); });
    return () => { live = false; };
  }, [flockId, flags, value]);

  const chosen = value ?? preview?.suggested_card ?? '';
  return (
    <div className="card-picker">
      <label className="bill-flag-title" htmlFor="bill-card">Rate card</label>
      <select id="bill-card" value={chosen} onChange={e => onChange(Number(e.target.value))}>
        {cards.map(c => (
          <option key={c.id} value={c.id}>
            {c.label}{c.effective_from ? ` (from ${c.effective_from})` : ''}{c.id === preview?.suggested_card ? ' — for this placement date' : ''}
          </option>
        ))}
      </select>
      {error && <p className="error-msg">{error}</p>}
      {preview && !error && (
        <dl className="kv bill-preview" aria-label="Bill preview">
          <dt>Production cost</dt><dd className="num">{rs(preview.production_cost_per_kg)}/kg · grade {preview.farmer_grade}</dd>
          <dt>Growing charge</dt><dd className="num">{rs(preview.growing_charges_per_kg)}/kg = {rs(preview.growing_charges_total, 0)}</dd>
          <dt>Rate incentive</dt><dd className="num">{rs(preview.rate_incentive_per_kg)}/kg = {rs(preview.rate_incentive_total, 0)}</dd>
          <dt>Recoveries</dt><dd className="num">− {rs(preview.total_recoveries, 0)}</dd>
          <dt>Net payable</dt><dd className="num strong">{rs(preview.net_payable, 0)}</dd>
          {Number(preview.tds_amount) > 0 && <><dt>After TDS</dt><dd className="num">{rs(preview.amount_paid, 0)}</dd></>}
        </dl>
      )}
    </div>
  );
}
