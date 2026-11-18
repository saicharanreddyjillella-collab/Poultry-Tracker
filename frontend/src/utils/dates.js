// Calendar dates in the user's own time zone (India), as YYYY-MM-DD.
// Never use toISOString() for this: it gives the UTC date, which is still
// "yesterday" in India between midnight and 5:30 AM.
const pad = (n) => String(n).padStart(2, '0');

export function localISO(d = new Date()) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export const todayISO = () => localISO(new Date());

export function monthStartISO(d = new Date()) {
  return localISO(new Date(d.getFullYear(), d.getMonth(), 1));
}
