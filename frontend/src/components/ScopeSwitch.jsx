/** "My regions | All farms" for supervisors who have regions; nothing for everyone else.
 *  `info` is the server's answer: { scope, has_home }. */
export default function ScopeSwitch({ info, onChange }) {
  if (!info?.has_home) return null;
  const opts = [['mine', 'My regions'], ['all', 'All farms']];
  return (
    <span className="seg scope-switch" role="group" aria-label="Show farms">
      {opts.map(([k, label]) => (
        <button key={k} type="button" className={`seg-btn ${info.scope === k ? 'on' : ''}`} aria-pressed={info.scope === k}
                onClick={() => onChange(k)}>{label}</button>
      ))}
    </span>
  );
}
