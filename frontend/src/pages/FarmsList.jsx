import { useState, useEffect } from 'react';
import { FarmsListSkeleton } from '../components/Skeletons';
import { Link, useSearchParams } from 'react-router-dom';
import { farmAPI } from '../api/client';
import { Chip, Panel } from '../components/ui';
import { fmtNum } from '../utils/format';

const STATUSES = [['all', 'All'], ['running', 'Running'], ['empty', 'Empty']];

/** Farms as a table: filter by status, region and search; one row per farm. */
export default function FarmsList() {
  const [farms, setFarms] = useState([]);
  const [loading, setLoading] = useState(true);
  // Filters live in the address (?q=…&status=…&region=…) so the top bar's search can open them.
  const [params, setParams] = useSearchParams();
  const search = params.get('q') || '';
  const status = params.get('status') || 'all';
  const region = params.get('region') || '';
  const setParam = (key, v) => {
    const next = new URLSearchParams(params);
    if (v && v !== 'all') next.set(key, v); else next.delete(key);
    setParams(next, { replace: true });
  };

  useEffect(() => {
    farmAPI.list().then(res => {
      setFarms(res.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) return <FarmsListSkeleton />;

  const regions = [...new Set(farms.map(f => f.region).filter(Boolean))].sort();
  const q = search.toLowerCase();
  const matches = farms.filter(f => (
    !q || [f.farm_code, f.name, f.owner_name, f.region, f.location, f.supervisor_names]
      .some(v => (v || '').toLowerCase().includes(q))
  ) && (!region || f.region === region));
  const counts = {
    all: matches.length,
    running: matches.filter(f => f.active_flocks.length > 0).length,
    empty: matches.filter(f => f.active_flocks.length === 0).length,
  };
  const shown = matches.filter(f => status === 'all' || (status === 'running') === (f.active_flocks.length > 0));

  return (
    <div className="page">
      <div className="page-header">
        <h1>Farms ({farms.length})</h1>
        <Link to="/farms/new" className="btn btn-primary">+ Add Farm</Link>
      </div>

      <Panel
        label="Farm list"
        actions={<>
          <span className="seg" role="group" aria-label="Status">
          {STATUSES.map(([k, label]) => (
            <button key={k} type="button" className={`seg-btn ${status === k ? 'on' : ''}`} aria-pressed={status === k}
                    onClick={() => setParam('status', k)}>
              {label} <span className="seg-count">{counts[k]}</span>
            </button>
          ))}
          </span>
          <span className="head-spacer" />
          {regions.length > 1 && (
            <select className="filter-select" aria-label="Region" value={region} onChange={e => setParam('region', e.target.value)}>
              <option value="">All regions</option>
              {regions.map(r => <option key={r} value={r}>{r}</option>)}
            </select>
          )}
          <div className="search-bar filter-search">
            <input type="text" placeholder="Search code, name, owner, region…" aria-label="Search farms"
                   value={search} onChange={e => setParam('q', e.target.value)} />
            {search && <button className="search-clear" aria-label="Clear search" onClick={() => setParam('q', '')}>&times;</button>}
          </div>
        </>}
      >
        {farms.length === 0 ? (
          <div className="panel-body empty-inline">
            <p>No farms yet.</p>
            <Link to="/farms/new" className="btn btn-primary">+ Add Farm</Link>
          </div>
        ) : shown.length === 0 ? (
          <p className="panel-body muted">{search ? `No farms match "${search}"` : 'No farms here.'}</p>
        ) : (
          <div className="table-wrapper">
            <table className="data-table cards-on-phone">
              <thead>
                <tr><th>Farm</th><th>Region</th><th>Shed</th><th className="r">Capacity</th><th>Status</th>
                  <th className="r">Live birds</th><th className="r">Mort %</th><th className="r">Batches</th><th>Supervisor</th></tr>
              </thead>
              <tbody>
                {shown.map(f => {
                  const fl = f.active_flocks[0];
                  const batches = f.active_flocks.length + (f.closed_flocks?.length || 0);
                  return (
                    <tr key={f.id}>
                      <td className="cell-main">
                        <Link to={`/farms/${f.id}`} className="cell-title">{f.name}</Link> <span className="muted">{f.farm_code}</span>
                        <div className="cell-sub">{f.owner_name}{f.location ? ` · ${f.location}` : ''}</div>
                      </td>
                      <td data-label="Region">{f.region || '—'}</td>
                      <td data-label="Shed">{f.shed_type === 'EC' ? 'EC' : 'Open'}</td>
                      <td data-label="Capacity" className="r num">{fmtNum(f.capacity)}</td>
                      <td className="cell-action">
                        {fl ? <Link to={`/flocks/${fl.id}`} className="action-link">
                          {fl.live_birds <= 0 ? <Chip tone="info">Sold out · bill due</Chip> : <Chip tone="ok">Running · day {fl.age_days}</Chip>}</Link>
                          : <Chip>Empty</Chip>}
                      </td>
                      <td data-label="Live birds" className="r num">{fl ? fmtNum(fl.live_birds) : '—'}</td>
                      <td data-label="Mort %" className={`r num ${fl && fl.mortality_percentage > 5 ? 'tone-danger' : ''}`}>{fl ? fl.mortality_percentage : '—'}</td>
                      <td data-label="Batches" className="r num">{batches}</td>
                      <td data-label="Supervisor">{f.supervisor_names || <span className="muted">—</span>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}
