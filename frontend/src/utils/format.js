// Number and date formatting for the Indian locale.

export const fmtNum = (n, digits = 0) => (n == null || Number.isNaN(Number(n)) ? '—'
  : Number(n).toLocaleString('en-IN', { minimumFractionDigits: digits, maximumFractionDigits: digits }));

/** 2026-11-19 → 19 Nov 2026 (or "19 Nov" with short). */
export function fmtDate(iso, short = false) {
  if (!iso) return '—';
  const d = new Date(`${String(iso).slice(0, 10)}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('en-IN', short ? { day: 'numeric', month: 'short' } : { day: 'numeric', month: 'short', year: 'numeric' });
}

/** Bill payment state → chip tone and words. */
export const PAY_TONE = { unpaid: 'danger', part: 'warn', paid: 'ok' };
export const PAY_LABEL = { unpaid: 'Unpaid', part: 'Part paid', paid: 'Paid' };
