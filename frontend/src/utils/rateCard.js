// Growing charge (₹/kg) a rate card gives at a production cost — same rule as backend core/billing.py.
// Margin & grade cards depend on the selling price and grade; for a quick check we use ₹110.

const n = (v) => (v === '' || v == null ? null : Number(v));

function grade(card, cost) {
  const bands = [['A+', card.grade_a_plus_max], ['A', card.grade_a_max], ['B', card.grade_b_max],
    ['C', card.grade_c_max], ['D', card.grade_d_max]];
  const hit = bands.find(([, max]) => cost <= n(max));
  return hit ? hit[0] : 'Z';
}

export function growingCharge(card, cost, sellingPrice = 110) {
  const min = n(card.min_growing_charges);
  if (min == null) return null;
  if (card.growing_method === 'standard') {
    const std = n(card.standard_growing_charges), stdCost = n(card.standard_production_cost);
    if (std == null || stdCost == null) return null;
    const gap = stdCost - cost;
    const pct = n(gap >= 0 ? card.gc_increase_pct : card.gc_decrease_pct) ?? 0;
    let gc = std + gap * pct / 100;
    const max = n(card.max_growing_charges);
    if (max != null) gc = Math.min(gc, max);
    return Math.max(gc, min);
  }
  const f = (n(card.grade_incentive_pct) ?? 0) / 100;
  const gc = Math.max(sellingPrice - cost, min);
  return ['A+', 'A'].includes(grade(card, cost)) ? gc * (1 + f) : gc * (1 - f);
}
