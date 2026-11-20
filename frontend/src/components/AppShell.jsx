import { useState } from 'react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import AlertBell from './AlertBell';
import Icon from './Icon';
import '../styles/shell.css';

/** Initials for the logo mark ("Sai Ram Feeds" → "SR") unless the brand logo is an image URL. */
function LogoMark({ name, logo }) {
  if (logo && /^(https?:)?\/|^data:image\//.test(logo)) {
    return <img className="side-logo side-logo-img" src={logo} alt="" />;
  }
  const initials = (name || '').split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0]).join('').toUpperCase();
  return <span className="side-logo" aria-hidden="true">{initials || '•'}</span>;
}

/**
 * The application frame: a dark sidebar with grouped navigation and the user's menu,
 * a slim top bar (search + alerts), and the page. On phones the sidebar slides in from
 * the menu button.
 *
 * groups: [{ label, links: [{ to, label, icon, end }] }]  (already filtered for the user's role)
 */
export default function AppShell({ brandName, logo, home, groups, showSearch, showAlerts, children }) {
  const { user, logout, isAdmin } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [userMenu, setUserMenu] = useState(false);

  const close = () => setOpen(false);

  const handleLogout = () => { logout(); navigate('/login', { replace: true }); };
  const search = (e) => {
    e.preventDefault();
    const q = query.trim();
    navigate(q ? `/farms?q=${encodeURIComponent(q)}` : '/farms', { state: { searchId: Date.now() } });   // Farms list adopts it
  };

  return (
    <div className={`app-layout ${open ? 'app-layout-open' : ''}`}>
      <nav aria-label="Main" className="sidebar">
        <Link to={home} className="side-brand" onClick={close}>
          <LogoMark name={brandName} logo={logo} />
          <span className="side-brand-name">{brandName}</span>
        </Link>
        <div className="side-groups">
          {groups.filter(g => g.links.length).map(g => (
            <div className="side-group" key={g.label}>
              <span className="side-group-label">{g.label}</span>
              {g.links.map(l => (
                <NavLink key={l.to} to={l.to} end={l.end} onClick={close} className={({ isActive }) => `side-link ${isActive ? 'active' : ''}`}>
                  <Icon name={l.icon} />{l.label}
                </NavLink>
              ))}
            </div>
          ))}
        </div>
        <div className={`nav-user-menu side-user ${userMenu ? 'open' : ''}`} onMouseLeave={() => setUserMenu(false)}>
          <button type="button" className="nav-user-trigger" aria-haspopup="true" aria-expanded={userMenu} onClick={() => setUserMenu(!userMenu)}>
            <span className="side-avatar" aria-hidden="true">{(user.first_name || user.username || '?')[0].toUpperCase()}</span>
            <span className="side-user-text">
              <span className="side-user-name">{user.first_name || user.username}</span>
              <span className={`side-user-role role-${user.role}`}>{user.role}</span>
            </span>
          </button>
          <div className="nav-dropdown">
            {isAdmin && <Link to="/settings" className="nav-dropdown-item" onClick={close}><Icon name="settings" size={16} />Settings</Link>}
            <Link to="/change-password" className="nav-dropdown-item" onClick={close}><Icon name="key" size={16} />Change Password</Link>
            <button type="button" className="nav-dropdown-item nav-dropdown-logout" onClick={handleLogout}><Icon name="logout" size={16} />Logout</button>
          </div>
        </div>
      </nav>
      {open && <div className="side-overlay" onClick={() => setOpen(false)} aria-hidden="true" />}

      <div className="app-body">
        <header className="topbar">
          <button type="button" className="hamburger topbar-menu" aria-label="Menu" aria-expanded={open} onClick={() => setOpen(!open)}>
            <Icon name={open ? 'close' : 'menu'} size={22} />
          </button>
          <Link to={home} className="topbar-brand">{brandName}</Link>
          {showSearch && (
            <form role="search" className="topbar-search" onSubmit={search}>
              <Icon name="search" size={16} />
              <input aria-label="Search farms" placeholder="Search farms, growers, regions…" value={query}
                     onChange={e => setQuery(e.target.value)} />
            </form>
          )}
          {showAlerts && <div className="topbar-alerts"><AlertBell /></div>}
        </header>
        <main className="main-content">{children}</main>
      </div>
    </div>
  );
}
