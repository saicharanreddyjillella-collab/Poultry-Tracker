import { useState } from 'react';
import { BrowserRouter, Routes, Route, Link, Navigate, useNavigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import AlertBell from './components/AlertBell';
import ErrorBoundary from './components/ErrorBoundary';
import Login from './pages/Login';
import Setup from './pages/Setup';
import Dashboard from './pages/Dashboard';
import FarmsList from './pages/FarmsList';
import FarmForm from './pages/FarmForm';
import FarmDetail from './pages/FarmDetail';
import FlockDetail from './pages/FlockDetail';
import Reports from './pages/Reports';
import UserManagement from './pages/UserManagement';
import ChangePassword from './pages/ChangePassword';
import FeedStock from './pages/FeedStock';
import FeedForecast from './pages/FeedForecast';
import Insights from './pages/Insights';
import FeedAudit from './pages/FeedAudit';
import OwnerDashboard from './pages/OwnerDashboard';
import BreakEven from './pages/BreakEven';
import BillView from './pages/BillView';
import RecycleBin from './pages/RecycleBin';
import './App.css';
import './styles/print.css';
import './styles/bill.css';
import './styles/components.css';
import './styles/business.css';
import brand from './config/brand';

const PLANT_PATHS = ['/feed', '/change-password'];

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <div className="loading">Loading...</div>;
  if (!user) return <Navigate to="/login" replace />;
  // Password set by an admin → must choose their own before anything else.
  if (user.must_change_password && location.pathname !== '/change-password') {
    return <Navigate to="/change-password" replace />;
  }
  // Feed-mill users only have the Feed screens (the API refuses the rest).
  if (user.role === 'plant' && !PLANT_PATHS.includes(location.pathname)) {
    return <Navigate to="/feed" replace />;
  }
  return children;
}

// Business-sensitive pages (owner P&L, break-even, feed forecast): admin only.
function AdminRoute({ children }) {
  const { user, isAdmin } = useAuth();
  if (user && !isAdmin) return <Navigate to={user.role === 'plant' ? '/feed' : '/feeds'} replace />;
  return <ProtectedRoute>{children}</ProtectedRoute>;
}

function NavBar() {
  const { user, logout, isAdmin, isPlant } = useAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);

  if (!user) return null;

  const handleLogout = () => {
    logout();
    setMenuOpen(false);
    navigate('/login', { replace: true });
  };

  const closeMenu = () => setMenuOpen(false);

  return (
    <nav className="navbar">
      <Link to={isPlant ? '/feed' : '/'} className="nav-brand" onClick={closeMenu}>{brand.feedsLogo} {brand.feedsName}</Link>
      <button className="hamburger" onClick={() => setMenuOpen(!menuOpen)} aria-label="Menu">
        <span className={`hamburger-line ${menuOpen ? 'open' : ''}`}></span>
        <span className={`hamburger-line ${menuOpen ? 'open' : ''}`}></span>
        <span className={`hamburger-line ${menuOpen ? 'open' : ''}`}></span>
      </button>
      <div className={`nav-links ${menuOpen ? 'nav-links-open' : ''}`}>
        {!isPlant && (
          <>
            <Link to="/" onClick={closeMenu}>Today</Link>
            <Link to="/farms" onClick={closeMenu}>Farms</Link>
          </>
        )}
        <Link to="/feed" onClick={closeMenu}>Feed</Link>
        {!isPlant && (
          <>
            <Link to="/reports" onClick={closeMenu}>Reports</Link>
          </>
        )}
        {isAdmin && (
          <>
            <Link to="/insights" onClick={closeMenu}>Insights</Link>
          </>
        )}
        {isAdmin && <Link to="/users" onClick={closeMenu}>Users</Link>}
        {isAdmin && <Link to="/trash" onClick={closeMenu}>Recycle Bin</Link>}
        {!isPlant && <AlertBell />}
        <div className="nav-mobile-user">
          <span className={`role-badge role-badge-${user.role}`}>{user.role}</span>
          {user.first_name || user.username}
        </div>
        <Link to="/change-password" className="nav-mobile-link" onClick={closeMenu}>Change Password</Link>
        <button className="nav-mobile-logout" onClick={handleLogout}>Logout</button>
        <div className="nav-user-menu">
          <span className="nav-user-trigger">
            <span className={`role-badge role-badge-${user.role}`}>{user.role}</span>
            {user.first_name || user.username} ▾
          </span>
          <div className="nav-dropdown">
            <Link to="/change-password" className="nav-dropdown-item" onClick={closeMenu}>Change Password</Link>
            <button className="nav-dropdown-item nav-dropdown-logout" onClick={handleLogout}>Logout</button>
          </div>
        </div>
      </div>
      {menuOpen && <div className="nav-overlay" onClick={closeMenu}></div>}
    </nav>
  );
}

function AppRoutes() {
  const location = useLocation();
  const { user } = useAuth();
  const path = location.pathname;
  const isAuthPage = path === '/login' || path === '/setup';
  const showNav = user && !isAuthPage;

  return (
    <>
      {showNav && <NavBar />}
      <main className="main-content">
        <ErrorBoundary resetKey={location.pathname}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/setup" element={<Setup />} />

          {/* Sai Ram Feeds */}
          <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
          <Route path="/feeds" element={<Navigate to="/" replace />} />
          <Route path="/farms" element={<ProtectedRoute><FarmsList /></ProtectedRoute>} />
          <Route path="/farms/new" element={<ProtectedRoute><FarmForm /></ProtectedRoute>} />
          <Route path="/farms/:id/edit" element={<ProtectedRoute><FarmForm /></ProtectedRoute>} />
          <Route path="/farms/:id" element={<ProtectedRoute><FarmDetail /></ProtectedRoute>} />
          <Route path="/feed" element={<ProtectedRoute><FeedStock /></ProtectedRoute>} />
          <Route path="/flocks/:id" element={<ProtectedRoute><FlockDetail /></ProtectedRoute>} />
          <Route path="/flocks/:flockId/bill" element={<ProtectedRoute><BillView /></ProtectedRoute>} />
          <Route path="/reports" element={<ProtectedRoute><Reports /></ProtectedRoute>} />
          <Route path="/feed-forecast" element={<AdminRoute><FeedForecast /></AdminRoute>} />
          <Route path="/insights" element={<AdminRoute><Insights /></AdminRoute>} />
          <Route path="/feed-audit" element={<AdminRoute><FeedAudit /></AdminRoute>} />
          <Route path="/owner-dashboard" element={<AdminRoute><OwnerDashboard /></AdminRoute>} />
          <Route path="/break-even" element={<AdminRoute><BreakEven /></AdminRoute>} />
          <Route path="/reports/monthly" element={<ProtectedRoute><Reports /></ProtectedRoute>} />
          <Route path="/reports/region" element={<ProtectedRoute><Reports /></ProtectedRoute>} />
          <Route path="/reports/till-date" element={<ProtectedRoute><Reports /></ProtectedRoute>} />
          <Route path="/users" element={<ProtectedRoute><UserManagement /></ProtectedRoute>} />
          <Route path="/trash" element={<ProtectedRoute><RecycleBin /></ProtectedRoute>} />
          <Route path="/change-password" element={<ProtectedRoute><ChangePassword /></ProtectedRoute>} />
        </Routes>
        </ErrorBoundary>
      </main>
    </>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
