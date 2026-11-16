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
import MonthlyReport from './pages/MonthlyReport';
import TillDateReport from './pages/TillDateReport';
import RegionPerformance from './pages/RegionPerformance';
import Reports from './pages/Reports';
import UserManagement from './pages/UserManagement';
import ChangePassword from './pages/ChangePassword';
import FeedStock from './pages/FeedStock';
import FeedForecast from './pages/FeedForecast';
import OwnerDashboard from './pages/OwnerDashboard';
import BreakEven from './pages/BreakEven';
import BillView from './pages/BillView';
import RecycleBin from './pages/RecycleBin';
import Landing from './pages/Landing';
import ChickenDashboard from './pages/ChickenDashboard';
import LayerDashboard from './pages/LayerDashboard';
import LayerFlocks from './pages/LayerFlocks';
import LayerFlockDetail from './pages/LayerFlockDetail';
import LayerNewEntry from './pages/LayerNewEntry';
import LayerFeedMill from './pages/LayerFeedMill';
import LayerTransactions from './pages/LayerTransactions';
import LayerMasters from './pages/LayerMasters';
import LayerReports from './pages/LayerReports';
import LayerDayClose from './pages/LayerDayClose';
import ChickenNewEntry from './pages/ChickenNewEntry';
import ChickenParties from './pages/ChickenParties';
import ChickenPartyStatement from './pages/ChickenPartyStatement';
import ChickenItems from './pages/ChickenItems';
import ChickenOutstanding from './pages/ChickenOutstanding';
import ChickenReports from './pages/ChickenReports';
import ChickenTransactions from './pages/ChickenTransactions';
import ChickenPendingBills from './pages/ChickenPendingBills';
import ChickenInvoice from './pages/ChickenInvoice';
import ChickenDayClose from './pages/ChickenDayClose';
import ChickenOpening from './pages/ChickenOpening';
import ChickenLedgers from './pages/ChickenLedgers';
import ChickenDaybook from './pages/ChickenDaybook';
import ChickenSalesSummary from './pages/ChickenSalesSummary';
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

// "/" is the business switcher (Feeds / Chicken Center / Layer Farm) — the other
// businesses are admin-only, so everyone else goes straight to Feeds.
function HomeRoute() {
  const { isAdmin } = useAuth();
  return isAdmin ? <Landing /> : <Navigate to="/feeds" replace />;
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
      <Link to={isPlant ? '/feed' : '/feeds'} className="nav-brand" onClick={closeMenu}>{brand.feedsLogo} {brand.feedsName}</Link>
      <button className="hamburger" onClick={() => setMenuOpen(!menuOpen)} aria-label="Menu">
        <span className={`hamburger-line ${menuOpen ? 'open' : ''}`}></span>
        <span className={`hamburger-line ${menuOpen ? 'open' : ''}`}></span>
        <span className={`hamburger-line ${menuOpen ? 'open' : ''}`}></span>
      </button>
      <div className={`nav-links ${menuOpen ? 'nav-links-open' : ''}`}>
        {!isPlant && (
          <>
            <Link to="/feeds" onClick={closeMenu}>Today</Link>
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
            <Link to="/feed-forecast" onClick={closeMenu}>Feed Forecast</Link>
            <Link to="/owner-dashboard" onClick={closeMenu}>Owner View</Link>
            <Link to="/break-even" onClick={closeMenu}>Break-even</Link>
          </>
        )}
        {isAdmin && <Link to="/users" onClick={closeMenu}>Users</Link>}
        {isAdmin && <Link to="/trash" onClick={closeMenu}>Recycle Bin</Link>}
        {isAdmin && <Link to="/" onClick={closeMenu}>Switch Business</Link>}
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

function ChickenNav() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  if (!user) return null;
  const closeMenu = () => setMenuOpen(false);
  const handleLogout = () => { logout(); closeMenu(); navigate('/login', { replace: true }); };
  return (
    <nav className="navbar navbar-chicken">
      <Link to="/chicken" className="nav-brand" onClick={closeMenu}>{brand.chickenLogo} {brand.chickenName}</Link>
      <button className="hamburger" onClick={() => setMenuOpen(!menuOpen)} aria-label="Menu">
        <span className={`hamburger-line ${menuOpen ? 'open' : ''}`}></span>
        <span className={`hamburger-line ${menuOpen ? 'open' : ''}`}></span>
        <span className={`hamburger-line ${menuOpen ? 'open' : ''}`}></span>
      </button>
      <div className={`nav-links ${menuOpen ? 'nav-links-open' : ''}`}>
        <Link to="/chicken" onClick={closeMenu}>Home</Link>
        <Link to="/chicken/new" onClick={closeMenu}>New Entry</Link>
        <Link to="/chicken/transactions" onClick={closeMenu}>Transactions</Link>
        <Link to="/chicken/parties" onClick={closeMenu}>Parties</Link>
        <Link to="/chicken/ledgers" onClick={closeMenu}>Ledgers</Link>
        <Link to="/chicken/outstanding" onClick={closeMenu}>Outstanding</Link>
        <Link to="/chicken/pending-bills" onClick={closeMenu}>Receivables</Link>
        <Link to="/chicken/reports" onClick={closeMenu}>Reports</Link>
        <Link to="/chicken/daybook" onClick={closeMenu}>Daybook</Link>
        <Link to="/chicken/sales-summary" onClick={closeMenu}>Sales Summary</Link>
        <Link to="/chicken/items" onClick={closeMenu}>Items</Link>
        <Link to="/chicken/opening" onClick={closeMenu}>Opening</Link>
        <Link to="/chicken/day-close" onClick={closeMenu}>Day Close</Link>
        <Link to="/" onClick={closeMenu}>Switch Business</Link>
        <div className="nav-mobile-user">
          <span className={`role-badge role-badge-${user.role}`}>{user.role}</span>
          {user.first_name || user.username}
        </div>
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

function LayerNav() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  if (!user) return null;
  const closeMenu = () => setMenuOpen(false);
  const handleLogout = () => { logout(); closeMenu(); navigate('/login', { replace: true }); };
  return (
    <nav className="navbar navbar-layer">
      <Link to="/layer" className="nav-brand" onClick={closeMenu}>{brand.layerLogo} {brand.layerName}</Link>
      <button className="hamburger" onClick={() => setMenuOpen(!menuOpen)} aria-label="Menu">
        <span className={`hamburger-line ${menuOpen ? 'open' : ''}`}></span>
        <span className={`hamburger-line ${menuOpen ? 'open' : ''}`}></span>
        <span className={`hamburger-line ${menuOpen ? 'open' : ''}`}></span>
      </button>
      <div className={`nav-links ${menuOpen ? 'nav-links-open' : ''}`}>
        <Link to="/layer" onClick={closeMenu}>Home</Link>
        <Link to="/layer/new" onClick={closeMenu}>New Entry</Link>
        <Link to="/layer/flocks" onClick={closeMenu}>Flocks</Link>
        <Link to="/layer/feed" onClick={closeMenu}>Feed Mill</Link>
        <Link to="/layer/transactions" onClick={closeMenu}>Transactions</Link>
        <Link to="/layer/masters" onClick={closeMenu}>Masters</Link>
        <Link to="/layer/reports" onClick={closeMenu}>Reports</Link>
        <Link to="/layer/day-close" onClick={closeMenu}>Day Close</Link>
        <Link to="/" onClick={closeMenu}>Switch Business</Link>
        <div className="nav-mobile-user">
          <span className={`role-badge role-badge-${user.role}`}>{user.role}</span>
          {user.first_name || user.username}
        </div>
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
  const isChicken = path.startsWith('/chicken');
  const isLayer = path.startsWith('/layer');
  const isLanding = path === '/';
  const isAuthPage = path === '/login' || path === '/setup';
  // Feeds nav shows on feeds routes; chicken nav on chicken routes; none on
  // landing/auth pages.
  const showFeedsNav = user && !isChicken && !isLayer && !isLanding && !isAuthPage;

  return (
    <>
      {showFeedsNav && <NavBar />}
      {user && isChicken && <ChickenNav />}
      {user && isLayer && <LayerNav />}
      <main className="main-content">
        <ErrorBoundary resetKey={location.pathname}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/setup" element={<Setup />} />
          <Route path="/" element={<ProtectedRoute><HomeRoute /></ProtectedRoute>} />

          {/* Sai Ram Feeds */}
          <Route path="/feeds" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
          <Route path="/farms" element={<ProtectedRoute><FarmsList /></ProtectedRoute>} />
          <Route path="/farms/new" element={<ProtectedRoute><FarmForm /></ProtectedRoute>} />
          <Route path="/farms/:id/edit" element={<ProtectedRoute><FarmForm /></ProtectedRoute>} />
          <Route path="/farms/:id" element={<ProtectedRoute><FarmDetail /></ProtectedRoute>} />
          <Route path="/feed" element={<ProtectedRoute><FeedStock /></ProtectedRoute>} />
          <Route path="/flocks/:id" element={<ProtectedRoute><FlockDetail /></ProtectedRoute>} />
          <Route path="/flocks/:flockId/bill" element={<ProtectedRoute><BillView /></ProtectedRoute>} />
          <Route path="/reports" element={<ProtectedRoute><Reports /></ProtectedRoute>} />
          <Route path="/feed-forecast" element={<AdminRoute><FeedForecast /></AdminRoute>} />
          <Route path="/owner-dashboard" element={<AdminRoute><OwnerDashboard /></AdminRoute>} />
          <Route path="/break-even" element={<AdminRoute><BreakEven /></AdminRoute>} />
          <Route path="/reports/monthly" element={<ProtectedRoute><Reports /></ProtectedRoute>} />
          <Route path="/reports/region" element={<ProtectedRoute><Reports /></ProtectedRoute>} />
          <Route path="/reports/till-date" element={<ProtectedRoute><Reports /></ProtectedRoute>} />
          <Route path="/users" element={<ProtectedRoute><UserManagement /></ProtectedRoute>} />
          <Route path="/trash" element={<ProtectedRoute><RecycleBin /></ProtectedRoute>} />
          <Route path="/change-password" element={<ProtectedRoute><ChangePassword /></ProtectedRoute>} />

          {/* Sai Charan Chicken Center */}
          <Route path="/chicken" element={<AdminRoute><ChickenDashboard /></AdminRoute>} />
          <Route path="/chicken/new" element={<AdminRoute><ChickenNewEntry /></AdminRoute>} />
          <Route path="/chicken/parties" element={<AdminRoute><ChickenParties /></AdminRoute>} />
          <Route path="/chicken/parties/:id" element={<AdminRoute><ChickenPartyStatement /></AdminRoute>} />
          <Route path="/chicken/items" element={<AdminRoute><ChickenItems /></AdminRoute>} />
          <Route path="/chicken/outstanding" element={<AdminRoute><ChickenOutstanding /></AdminRoute>} />
          <Route path="/chicken/reports" element={<AdminRoute><ChickenReports /></AdminRoute>} />
          <Route path="/chicken/transactions" element={<AdminRoute><ChickenTransactions /></AdminRoute>} />
          <Route path="/chicken/pending-bills" element={<AdminRoute><ChickenPendingBills /></AdminRoute>} />
          <Route path="/chicken/invoice/:id" element={<AdminRoute><ChickenInvoice /></AdminRoute>} />
          <Route path="/chicken/day-close" element={<AdminRoute><ChickenDayClose /></AdminRoute>} />
          <Route path="/chicken/opening" element={<AdminRoute><ChickenOpening /></AdminRoute>} />
          <Route path="/chicken/ledgers" element={<AdminRoute><ChickenLedgers /></AdminRoute>} />
          <Route path="/chicken/daybook" element={<AdminRoute><ChickenDaybook /></AdminRoute>} />
          <Route path="/chicken/sales-summary" element={<AdminRoute><ChickenSalesSummary /></AdminRoute>} />

          {/* Sai Ram Layer Farm */}
          <Route path="/layer" element={<AdminRoute><LayerDashboard /></AdminRoute>} />
          <Route path="/layer/flocks" element={<AdminRoute><LayerFlocks /></AdminRoute>} />
          <Route path="/layer/flocks/:id" element={<AdminRoute><LayerFlockDetail /></AdminRoute>} />
          <Route path="/layer/new" element={<AdminRoute><LayerNewEntry /></AdminRoute>} />
          <Route path="/layer/feed" element={<AdminRoute><LayerFeedMill /></AdminRoute>} />
          <Route path="/layer/transactions" element={<AdminRoute><LayerTransactions /></AdminRoute>} />
          <Route path="/layer/masters" element={<AdminRoute><LayerMasters /></AdminRoute>} />
          <Route path="/layer/reports" element={<AdminRoute><LayerReports /></AdminRoute>} />
          <Route path="/layer/day-close" element={<AdminRoute><LayerDayClose /></AdminRoute>} />
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
