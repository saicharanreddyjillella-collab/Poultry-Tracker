import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { insightsAPI } from '../api/client';

/** Dashboard notice when any of the user's farms faces danger-level heat in the next 3 days. */
export default function HeatBanner({ scope }) {
  const [summary, setSummary] = useState(null);
  useEffect(() => {
    insightsAPI.heatStress(scope).then(r => setSummary(r.data?.summary)).catch(() => {});
  }, [scope]);
  const n = summary?.at_risk_next_3_days || 0;
  if (!n) return null;
  const emergency = summary.emergency_next_3_days || 0;
  return (
    <div className={`alert-banner ${emergency ? 'alert-banner-danger' : 'alert-banner-warning'}`} role="status">
      🌡 Heat alert: {n} farm{n > 1 ? 's' : ''} at danger level or worse in the next 3 days
      {emergency ? ` (${emergency} at emergency)` : ''}. <Link to="/heat-stress">See what to do →</Link>
    </div>
  );
}
