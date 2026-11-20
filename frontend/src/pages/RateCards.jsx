import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { rateCardAPI, getErrorMessage } from '../api/client';
import { Chip, Panel } from '../components/ui';
import { fmtDate } from '../utils/format';
import { growingCharge } from '../utils/rateCard';

const METHODS = {
  standard: 'Standard charge ± % of the gap from standard cost',
  margin_grade: 'Selling price − cost, ± % by grade',
};

// The card's fields, grouped the way the printed rate card is laid out.
const GROUPS = [
  { title: 'Production cost', fields: [
    ['feed_cost_per_kg', 'Feed cost (₹ per kg)'],
    ['chick_cost_per_bird', 'Chick cost (₹ per chick)'],
    ['admin_cost_per_chick', 'Administration cost (₹ per chick)'],
    ['medicine_cost_per_chick', 'Medicine (₹ per chick, when not at actual)', { hideIf: c => c.medicine_always_actual }],
    ['standard_fcr', 'Standard FCR'],
    ['standard_avg_weight_kg', 'Standard average body weight (kg)'],
    ['standard_mortality_pct', 'Standard mortality (%)'],
  ] },
  { title: 'Growing charge', fields: [
    ['standard_production_cost', 'Standard production cost (₹/kg)'],
    ['standard_growing_charges', 'Standard growing charge (₹/kg)', { showIf: c => c.growing_method === 'standard' }],
    ['min_growing_charges', 'Minimum growing charge (₹/kg)'],
    ['max_growing_charges', 'Maximum growing charge (₹/kg, optional)', { showIf: c => c.growing_method === 'standard', optional: true }],
    ['gc_increase_pct', 'Increase per ₹1 below standard (%)', { showIf: c => c.growing_method === 'standard' }],
    ['gc_decrease_pct', 'Decrease per ₹1 above standard (%)', { showIf: c => c.growing_method === 'standard' }],
    ['grade_incentive_pct', 'Grade increase / decrease (%)', { showIf: c => c.growing_method === 'margin_grade' }],
    ['grade_a_plus_max', 'Grade A+ up to (₹/kg cost)', { showIf: c => c.growing_method === 'margin_grade' }],
    ['grade_a_max', 'Grade A up to', { showIf: c => c.growing_method === 'margin_grade' }],
    ['grade_b_max', 'Grade B up to', { showIf: c => c.growing_method === 'margin_grade' }],
    ['grade_c_max', 'Grade C up to', { showIf: c => c.growing_method === 'margin_grade' }],
    ['grade_d_max', 'Grade D up to (above = Z)', { showIf: c => c.growing_method === 'margin_grade' }],
  ] },
  { title: 'Rate incentive on average selling price', fields: [
    ['incentive_threshold_1', 'Tier 1 starts above (₹/kg)'],
    ['incentive_rate_1', 'Tier 1: ₹ per kg for every ₹1 (0.05 = 5 paise)'],
    ['incentive_threshold_2', 'Tier 2 starts above (₹/kg)'],
    ['incentive_rate_2', 'Tier 2: ₹ per kg for every ₹1 (0.10 = 10 paise)'],
    ['max_rate_incentive', 'Maximum rate incentive (₹/kg)'],
  ] },
  { title: 'Recoveries', fields: [
    ['first_week_mortality_limit_pct', 'First-week mortality allowed (%)'],
    ['first_week_recovery_per_chick', 'First-week excess: ₹ per chick'],
    ['negligence_rate_1_15', 'Negligence: ₹ per bird, days 1–15'],
    ['negligence_rate_16_20', 'Negligence: days 16–20'],
    ['negligence_rate_21_35', 'Negligence: days 21–35'],
    ['negligence_rate_above_35', 'Negligence: above day 35'],
    ['ifft_per_bag', 'IFFT charge (₹ per bag)'],
  ] },
  { title: 'FCR benchmark (premium / deduction)', fields: [
    ['fcr_benchmark', 'Benchmark FCR'],
    ['fcr_benchmark_tolerance_pct', 'No-change band (± %)'],
    ['fcr_premium_per_kg_per_step', 'Premium ₹/kg per 0.1 better'],
    ['fcr_deduction_per_kg_per_step', 'Deduction ₹/kg per 0.1 worse'],
    ['fcr_benchmark_max_adjustment_per_kg', 'Maximum ₹/kg either way'],
  ] },
  { title: 'TDS (Section 194C)', fields: [
    ['tds_single_payment_limit', 'Single payment limit (₹)', { showIf: c => c.apply_tds && c.apply_tds_thresholds }],
    ['tds_annual_limit', 'Yearly limit per grower (₹)', { showIf: c => c.apply_tds && c.apply_tds_thresholds }],
  ] },
];
const NUMBER_FIELDS = GROUPS.flatMap(g => g.fields.map(f => f[0])).concat('feed_reconciliation_tolerance_pct');
const SAMPLE_COSTS = [90, 93, 95, 98, 102];

/** Billing rate cards (admin): one card per rate change; bills record the card they used. */
export default function RateCards() {
  const [cards, setCards] = useState(null);
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');
  const [edit, setEdit] = useState(null);          // form values for the card being edited
  const [busy, setBusy] = useState(false);

  const load = () => rateCardAPI.list().then(r => setCards(r.data)).catch(err => setError(getErrorMessage(err)));
  useEffect(() => { load(); }, []);

  const act = async (fn, done) => {
    setBusy(true); setError(''); setMsg('');
    try { await fn(); if (done) setMsg(done); await load(); } catch (err) { setError(getErrorMessage(err)); }
    setBusy(false);
  };

  const newCard = (from) => act(async () => {
    const r = await rateCardAPI.create({ copy_from: from.id, name: '', effective_from: null });
    setEdit({ ...r.data, isNew: true });
  });

  const save = (e) => {
    e.preventDefault();
    const data = { name: edit.name, effective_from: edit.effective_from || null, notes: edit.notes || '',
      growing_method: edit.growing_method, medicine_always_actual: edit.medicine_always_actual,
      apply_tds: edit.apply_tds, apply_tds_thresholds: edit.apply_tds_thresholds };
    NUMBER_FIELDS.forEach(k => { data[k] = edit[k] === '' ? null : edit[k]; });
    act(async () => { await rateCardAPI.update(edit.id, data); setEdit(null); }, `Saved ${edit.name || 'the card'}.`);
  };

  const cancel = () => {
    if (edit?.isNew) act(async () => { await rateCardAPI.remove(edit.id); setEdit(null); });
    else setEdit(null);
  };

  const set = (k) => (e) => setEdit({ ...edit, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value });

  return (
    <div className="page">
      <nav className="crumbs" aria-label="Breadcrumb"><Link to="/settings">Settings</Link><span aria-hidden="true">/</span><span>Billing rates</span></nav>
      <div className="page-header">
        <div>
          <h1>Billing Rates</h1>
          <p className="farm-meta">One card per rate change. A flock is billed with the card in effect on its placement date
            unless you pick another when closing it. Bills keep the card they used.</p>
        </div>
        {cards && cards.length > 0 && !edit && (
          <button className="btn btn-primary" disabled={busy} onClick={() => newCard(cards[0])}>+ New rate card</button>
        )}
      </div>
      {error && <div className="alert-banner alert-banner-danger" role="alert">{error}</div>}
      {msg && <div className="alert-banner alert-banner-success" role="status">{msg}</div>}
      {!cards && !error && <p className="muted">Loading…</p>}

      {edit && (
        <form className="panel rate-form" onSubmit={save} aria-label="Rate card">
          <div className="panel-head"><h2>{edit.isNew ? 'New rate card' : `Edit: ${edit.label}`}</h2>
            {edit.bills_count > 0 && <span className="muted small">Used by {edit.bills_count} bill{edit.bills_count > 1 ? 's' : ''}. Those bills keep their amounts; changes apply to new bills.</span>}
          </div>
          <div className="panel-body">
            <div className="rate-grid">
              <div className="form-group"><label htmlFor="rc-name">Card name *</label>
                <input id="rc-name" required value={edit.name} onChange={set('name')} placeholder="e.g. Jangaon Nov 2026" /></div>
              <div className="form-group"><label htmlFor="rc-from">Effective from</label>
                <input id="rc-from" type="date" value={edit.effective_from || ''} onChange={set('effective_from')} /></div>
              <div className="form-group rate-wide"><label htmlFor="rc-method">Growing charge method</label>
                <select id="rc-method" value={edit.growing_method} onChange={set('growing_method')}>
                  {Object.entries(METHODS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select></div>
            </div>

            {GROUPS.map(g => (
              <fieldset key={g.title} className="rate-group">
                <legend>{g.title}</legend>
                {g.title === 'Production cost' && (
                  <label className="toggle-label"><input type="checkbox" checked={!!edit.medicine_always_actual} onChange={set('medicine_always_actual')} />
                    Medicine at actual use for every farm</label>
                )}
                {g.title.startsWith('TDS') && (<>
                  <label className="toggle-label"><input type="checkbox" checked={!!edit.apply_tds} onChange={set('apply_tds')} /> Deduct TDS</label>
                  {edit.apply_tds && <label className="toggle-label"><input type="checkbox" checked={!!edit.apply_tds_thresholds} onChange={set('apply_tds_thresholds')} /> Skip TDS under the limits</label>}
                </>)}
                <div className="rate-grid">
                  {g.fields.filter(([, , o = {}]) => (!o.showIf || o.showIf(edit)) && !(o.hideIf && o.hideIf(edit))).map(([k, label, o = {}]) => (
                    <div className="form-group" key={k}>
                      <label htmlFor={`rc-${k}`}>{label}</label>
                      <input id={`rc-${k}`} type="number" step="any" inputMode="decimal" required={!o.optional}
                             value={edit[k] ?? ''} onChange={set(k)} />
                    </div>
                  ))}
                </div>
                {g.title === 'Growing charge' && (
                  <div className="rate-check" aria-label="Growing charge check">
                    <span className="muted small">Check:</span>
                    {SAMPLE_COSTS.map(c => {
                      const gc = growingCharge(edit, c);
                      return <span key={c} className="rate-check-item">cost ₹{c} → <strong className="num">{gc == null ? '—' : `₹${gc.toFixed(2)}`}</strong></span>;
                    })}
                    {edit.growing_method === 'margin_grade' && <span className="muted small">(at a ₹110 selling price)</span>}
                  </div>
                )}
              </fieldset>
            ))}
            <div className="form-group"><label htmlFor="rc-notes">Notes</label>
              <textarea id="rc-notes" rows={2} value={edit.notes || ''} onChange={set('notes')} /></div>
            <div className="form-actions">
              <button type="submit" className="btn btn-primary" disabled={busy}>Save card</button>
              <button type="button" className="btn btn-secondary" disabled={busy} onClick={cancel}>Cancel</button>
            </div>
          </div>
        </form>
      )}

      {cards && !edit && (
        <Panel label="Rate cards">
          <div className="table-wrapper">
            <table className="data-table cards-on-phone">
              <thead><tr><th>Card</th><th>Effective from</th><th>Method</th><th className="r">Feed ₹/kg</th><th className="r">Std cost</th>
                <th className="r">Std / min charge</th><th className="r">Bills</th><th></th></tr></thead>
              <tbody>
                {cards.map(c => (
                  <tr key={c.id}>
                    <td className="cell-main"><strong>{c.label}</strong> {c.is_active && <Chip tone="ok">Default</Chip>}</td>
                    <td data-label="Effective from">{c.effective_from ? fmtDate(c.effective_from) : <span className="muted">—</span>}</td>
                    <td data-label="Method">{c.growing_method === 'standard' ? 'Standard ± %' : 'Margin & grade'}</td>
                    <td data-label="Feed ₹/kg" className="r num">{c.feed_cost_per_kg}</td>
                    <td data-label="Std cost" className="r num">{c.standard_production_cost}</td>
                    <td data-label="Std / min charge" className="r num">{c.growing_method === 'standard' ? c.standard_growing_charges : '—'} / {c.min_growing_charges}</td>
                    <td data-label="Bills" className="r num">{c.bills_count}</td>
                    <td className="row-actions">
                      <button className="btn btn-secondary btn-sm" disabled={busy} onClick={() => setEdit({ ...c })}>Edit</button>
                      <button className="btn btn-secondary btn-sm" disabled={busy} onClick={() => newCard(c)}>Copy</button>
                      {!c.is_active && <button className="btn btn-secondary btn-sm" disabled={busy}
                        onClick={() => act(() => rateCardAPI.makeDefault(c.id), `${c.label} is now the default card.`)}>Make default</button>}
                      {!c.is_active && c.bills_count === 0 && <button className="btn btn-danger btn-sm" disabled={busy}
                        onClick={() => act(() => rateCardAPI.remove(c.id), `Deleted ${c.label}.`)}>Delete</button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </div>
  );
}
