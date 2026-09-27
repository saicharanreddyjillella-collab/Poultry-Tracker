import { useState } from 'react';
import { BrowserRouter, Routes, Route, Link, Navigate, useNavigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import AlertBell from './components/AlertBell';
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
import BillView from './pages/BillView';
import Landing from './pages/Landing';
import ChickenDashboard from './pages/ChickenDashboard';
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

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="loading">Loading...</div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
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
      <Link to={isPlant ? '/feed' : '/feeds'} className="nav-brand" onClick={closeMenu}>🐔 Sai Ram Feeds</Link>
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
        {isAdmin && <Link to="/users" onClick={closeMenu}>Users</Link>}
        {!isPlant && <Link to="/" onClick={closeMenu}>Switch Business</Link>}
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
      <Link to="/chicken" className="nav-brand" onClick={closeMenu}>🛒 Chicken Center</Link>
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

function AppRoutes() {
  const location = useLocation();
  const { user } = useAuth();
  const path = location.pathname;
  const isChicken = path.startsWith('/chicken');
  const isLanding = path === '/';
  const isAuthPage = path === '/login' || path === '/setup';
  // Feeds nav shows on feeds routes; chicken nav on chicken routes; none on
  // landing/auth pages.
  const showFeedsNav = user && !isChicken && !isLanding && !isAuthPage;

  return (
    <>
      {showFeedsNav && <NavBar />}
      {user && isChicken && <ChickenNav />}
      <main className="main-content">
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/setup" element={<Setup />} />
          <Route path="/" element={<ProtectedRoute><Landing /></ProtectedRoute>} />

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
          <Route path="/reports/monthly" element={<ProtectedRoute><Reports /></ProtectedRoute>} />
          <Route path="/reports/region" element={<ProtectedRoute><Reports /></ProtectedRoute>} />
          <Route path="/reports/till-date" element={<ProtectedRoute><Reports /></ProtectedRoute>} />
          <Route path="/users" element={<ProtectedRoute><UserManagement /></ProtectedRoute>} />
          <Route path="/change-password" element={<ProtectedRoute><ChangePassword /></ProtectedRoute>} />

          {/* Sai Charan Chicken Center */}
          <Route path="/chicken" element={<ProtectedRoute><ChickenDashboard /></ProtectedRoute>} />
          <Route path="/chicken/new" element={<ProtectedRoute><ChickenNewEntry /></ProtectedRoute>} />
          <Route path="/chicken/parties" element={<ProtectedRoute><ChickenParties /></ProtectedRoute>} />
          <Route path="/chicken/parties/:id" element={<ProtectedRoute><ChickenPartyStatement /></ProtectedRoute>} />
          <Route path="/chicken/items" element={<ProtectedRoute><ChickenItems /></ProtectedRoute>} />
          <Route path="/chicken/outstanding" element={<ProtectedRoute><ChickenOutstanding /></ProtectedRoute>} />
          <Route path="/chicken/reports" element={<ProtectedRoute><ChickenReports /></ProtectedRoute>} />
          <Route path="/chicken/transactions" element={<ProtectedRoute><ChickenTransactions /></ProtectedRoute>} />
          <Route path="/chicken/pending-bills" element={<ProtectedRoute><ChickenPendingBills /></ProtectedRoute>} />
          <Route path="/chicken/invoice/:id" element={<ProtectedRoute><ChickenInvoice /></ProtectedRoute>} />
          <Route path="/chicken/day-close" element={<ProtectedRoute><ChickenDayClose /></ProtectedRoute>} />
          <Route path="/chicken/opening" element={<ProtectedRoute><ChickenOpening /></ProtectedRoute>} />
          <Route path="/chicken/ledgers" element={<ProtectedRoute><ChickenLedgers /></ProtectedRoute>} />
          <Route path="/chicken/daybook" element={<ProtectedRoute><ChickenDaybook /></ProtectedRoute>} />
          <Route path="/chicken/sales-summary" element={<ProtectedRoute><ChickenSalesSummary /></ProtectedRoute>} />
        </Routes>
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
