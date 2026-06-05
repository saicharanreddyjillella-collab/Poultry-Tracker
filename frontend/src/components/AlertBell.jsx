import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { dashboardAPI } from '../api/client';

export default function AlertBell() {
  const [alerts, setAlerts] = useState([]);
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  const load = () => {
    dashboardAPI.get().then(res => {
      setAlerts(res.data.alerts || []);
    }).catch(() => {});
  };

  useEffect(() => {
    load();
    const interval = setInterval(load, 60000); // refresh every minute
    return () => clearInterval(interval);
  }, []);

  // Close on outside click
  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const dangerCount = alerts.filter(a => a.type === 'danger').length;
  const warningCount = alerts.filter(a => a.type === 'warning').length;

  return (
    <div className="alert-bell" ref={ref}>
      <button className="alert-bell-btn" onClick={() => setOpen(!open)}>
        🔔
        {alerts.length > 0 && (
          <span className={`alert-bell-count ${dangerCount > 0 ? 'alert-bell-danger' : ''}`}>
            {alerts.length}
          </span>
        )}
      </button>
      {open && (
        <div className="alert-bell-dropdown">
          <div className="alert-bell-header">
            <strong>Alerts</strong>
            {alerts.length > 0 && <span className="alert-bell-summary">
              {dangerCount > 0 && <span className="text-danger">{dangerCount} critical</span>}
              {dangerCount > 0 && warningCount > 0 && ' · '}
              {warningCount > 0 && <span className="text-warning">{warningCount} warning</span>}
            </span>}
          </div>
          {alerts.length === 0 ? (
            <div className="alert-bell-empty">No alerts — all good! ✅</div>
          ) : (
            <div className="alert-bell-list">
              {alerts.map((a, i) => (
                <Link
                  key={i}
                  to={a.flock_id ? `/flocks/${a.flock_id}` : `/farms`}
                  className={`alert-bell-item alert-bell-item-${a.type}`}
                  onClick={() => setOpen(false)}
                >
                  <span className="alert-bell-icon">
                    {a.type === 'danger' ? '🔴' : a.type === 'warning' ? '🟡' : 'ℹ️'}
                  </span>
                  <div className="alert-bell-content">
                    <span className="alert-bell-farm">{a.farm_code} — {a.farm_name}</span>
                    <span className="alert-bell-msg">{a.message}</span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
