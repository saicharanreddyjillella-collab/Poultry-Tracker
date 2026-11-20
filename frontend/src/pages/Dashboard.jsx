import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { DashboardSkeleton } from '../components/Skeletons';
import { dashboardAPI } from '../api/client';
import { useAuth } from '../context/AuthContext';
import HeatBanner from '../components/HeatBanner';
import ScopeSwitch from '../components/ScopeSwitch';
import { useScope } from '../utils/useScope';
import { Chip, Meter, Panel, StatTile } from '../components/ui';
import { fmtDate, fmtNum } from '../utils/format';

const ACTION_TONE = { danger: 'danger', warn: 'warn', info: 'info', ok: 'ok' };
const ALERT_TONE = { danger: 'danger', warning: 'warn', info: 'info' };

/** Control room: what needs doing today, across the farms this user can see. */
export default function Dashboard() {
  const { isAdmin } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [scope, setScope] = useScope();          // supervisors: their regions unless they pick All farms

  useEffect(() => {
    dashboardAPI.get(scope).then(res => { setData(res.data); setLoading(false); }).catch(() => setLoading(false));
  }, [scope]);

  if (loading) return <DashboardSkeleton />;
  if (!data) return <div className="empty-state">Could not load the dashboard. Check the connection and refresh.</div>;

  const feedToday = data.feed_today || {};
  const todayBags = (feedToday.bpsc_bags || 0) + (feedToday.bsc_bags || 0) + (feedToday.bfp_bags || 0);
  const entries = data.entries_today || { done: 0, due: 0 };
  const left = Math.max(entries.due - entries.done, 0);
  const trend = data.trend || { mortality: [], feed_bags: [] };
  const mort14 = trend.mortality.reduce((a, b) => a + b, 0);
  const rows = data.flock_rows || [];
  const regions = data.regions || [];
  const alerts = data.alerts || [];
  const rates = data.latest_feed_rates || {};
  const actionLink = (r) => (r.next_action.code === 'feed' ? '/feed' : `/flocks/${r.flock_id}`);

  return (
    <div className="page dashboard">
      <div className="page-header">
        <div>
          <h1>Today's Dashboard</h1>
          <p className="farm-meta">
            {new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
            {entries.due > 0 && <> · {entries.done} of {entries.due} daily entries done</>}
          </p>
        </div>
        <div className="header-actions">
          <ScopeSwitch info={data} onChange={setScope} />
          <Link to="/farms/new" className="btn btn-primary">+ Add Farm</Link>
        </div>
      </div>

      <HeatBanner scope={data.scope} />

      <div className="stats-grid tiles">
        <StatTile label="Live birds" value={fmtNum(data.total_live_birds)}
                  note={`${data.total_active_flocks} active flocks · ${data.total_farms} farms`} />
        <StatTile label="Mortality today" value={fmtNum(data.mortality_today)}
                  note={`${fmtNum(mort14)} in the last 14 days`} trend={trend.mortality} trendColor="var(--warning)" />
        <StatTile label="Daily entries" value={entries.done} unit={`of ${entries.due}`}
                  note={left ? `${left} still to enter` : 'All entered'} tone={left ? 'warn' : 'ok'} />
        <StatTile label="Feed used today" value={fmtNum(todayBags, 1)} unit="bags"
                  note={`${fmtNum(todayBags * 50)} kg`} trend={trend.feed_bags} />
        <StatTile label="Feed on farms" value={fmtNum(data.feed_on_farms_bags)} unit="bags"
                  note={data.pending_orders?.count ? `${data.pending_orders.count} orders pending · ${fmtNum(data.pending_orders.bags)} bags` : 'No orders pending'}>
          {isAdmin && Object.keys(rates).length > 0 && (
            <span className="stat-sub">Rates ₹/kg: {['BPSC', 'BSC', 'BFP'].filter(t => rates[t]).map(t => `${t} ${Number(rates[t])}`).join(' · ')}</span>
          )}
        </StatTile>
      </div>

      <div className="dash-grid">
        <Panel title="Regions" actions={<Link to="/reports" className="panel-link">Reports →</Link>}>
          {regions.length === 0 ? <p className="panel-body muted">No active flocks.</p> : (
            <div className="region-grid">
              {regions.map(r => (
                <div key={r.region} className="region-cell">
                  <div className="region-name">{r.region}</div>
                  <dl className="kv">
                    <dt>Farms</dt><dd className="num">{r.farms}</dd>
                    <dt>Live birds</dt><dd className="num">{fmtNum(r.live_birds)}</dd>
                    <dt>Mortality</dt><dd className="num">{r.mortality_pct}%</dd>
                    <dt>Entries due</dt><dd className={`num ${r.entries_due ? 'tone-warn' : ''}`}>{r.entries_due}</dd>
                  </dl>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Alerts" actions={<span className="muted small">{alerts.length || 'none'}</span>}>
          {alerts.length === 0 ? <p className="panel-body muted">Nothing needs attention.</p> : (
            <ul className="alert-list">
              {alerts.slice(0, 8).map((a, i) => (
                <li key={i}>
                  <span className={`dot dot-${ALERT_TONE[a.type] || 'info'}`} aria-hidden="true" />
                  <div>
                    {a.link ? <Link to={a.link} className="alert-farm">{a.farm_name}</Link>
                      : a.flock_id ? <Link to={`/flocks/${a.flock_id}`} className="alert-farm">{a.farm_name}</Link> : <span className="alert-farm">{a.farm_name}</span>}
                    <span className="alert-msg">{a.message}</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <Panel title="Flocks on the ground" actions={<Link to="/farms" className="panel-link">All farms →</Link>}>
        {rows.length === 0 ? (
          <div className="panel-body empty-inline">
            <p>No active flocks.</p>
            <Link to="/farms" className="btn btn-secondary">Go to farms</Link>
          </div>
        ) : (
          <div className="table-wrapper">
            <table className="data-table cards-on-phone">
              <thead>
                <tr><th>Farm</th><th>Region</th><th className="r">Age</th><th className="r">Live</th><th className="r">Mort %</th>
                  <th>Weight vs std</th><th className="r">Feed (bags)</th><th>Last entry</th><th>Next action</th></tr>
              </thead>
              <tbody>
                {rows.map(r => (
                  <tr key={r.flock_id}>
                    <td className="cell-main"><Link to={`/flocks/${r.flock_id}`} className="cell-title">{r.farm_name}</Link> <span className="muted">{r.farm_code}</span></td>
                    <td data-label="Region">{r.region}</td>
                    <td data-label="Age" className="r num">{r.age_days}</td>
                    <td data-label="Live" className="r num">{fmtNum(r.live_birds)}</td>
                    <td data-label="Mort %" className="r num">{r.mortality_pct}</td>
                    <td data-label="Weight vs std"><Meter pct={r.weight_pct} /></td>
                    <td data-label="Feed (bags)" className="r num">{fmtNum(r.feed_bags)}</td>
                    <td data-label="Last entry">{r.last_entry ? <>{fmtDate(r.last_entry, true)}{r.last_entry_by && <span className="cell-sub">by {r.last_entry_by}</span>}</> : <span className="muted">none</span>}</td>
                    <td className="cell-action"><Link to={actionLink(r)} className="action-link"><Chip tone={ACTION_TONE[r.next_action.severity]}>{r.next_action.label}</Chip></Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {(data.idle_farms || []).length > 0 && (
          <p className="panel-foot">
            Empty farms: {data.idle_farms.map((f, i) => (
              <span key={f.id}>{i > 0 && ', '}<Link to={`/farms/${f.id}`}>{f.name}</Link></span>
            ))}
          </p>
        )}
      </Panel>
    </div>
  );
}
