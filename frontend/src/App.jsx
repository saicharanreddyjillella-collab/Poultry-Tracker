import { useState } from 'react';
import { BrowserRouter, Routes, Route, Link, Navigate, useNavigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import FarmsList from './pages/FarmsList';
import FarmForm from './pages/FarmForm';
import FarmDetail from './pages/FarmDetail';
import FlockDetail from './pages/FlockDetail';
import MonthlyReport from './pages/MonthlyReport';
import TillDateReport from './pages/TillDateReport';
import RegionPerformance from './pages/RegionPerformance';
import UserManagement from './pages/UserManagement';
import ChangePassword from './pages/ChangePassword';
import FeedStock from './pages/FeedStock';
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
      <Link to={isPlant ? '/feed' : '/'} className="nav-brand" onClick={closeMenu}>🐔 PoultryTrack</Link>
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
            <Link to="/reports/monthly" onClick={closeMenu}>Monthly</Link>
            <Link to="/reports/region" onClick={closeMenu}>Region</Link>
            <Link to="/reports/till-date" onClick={closeMenu}>Till Date</Link>
          </>
        )}
        {isAdmin && <Link to="/users" onClick={closeMenu}>Users</Link>}
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
  return (
    <>
      <NavBar />
      <main className="main-content">
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
          <Route path="/farms" element={<ProtectedRoute><FarmsList /></ProtectedRoute>} />
          <Route path="/farms/new" element={<ProtectedRoute><FarmForm /></ProtectedRoute>} />
          <Route path="/farms/:id/edit" element={<ProtectedRoute><FarmForm /></ProtectedRoute>} />
          <Route path="/farms/:id" element={<ProtectedRoute><FarmDetail /></ProtectedRoute>} />
          <Route path="/feed" element={<ProtectedRoute><FeedStock /></ProtectedRoute>} />
          <Route path="/flocks/:id" element={<ProtectedRoute><FlockDetail /></ProtectedRoute>} />
          <Route path="/reports/monthly" element={<ProtectedRoute><MonthlyReport /></ProtectedRoute>} />
          <Route path="/reports/region" element={<ProtectedRoute><RegionPerformance /></ProtectedRoute>} />
          <Route path="/reports/till-date" element={<ProtectedRoute><TillDateReport /></ProtectedRoute>} />
          <Route path="/users" element={<ProtectedRoute><UserManagement /></ProtectedRoute>} />
          <Route path="/change-password" element={<ProtectedRoute><ChangePassword /></ProtectedRoute>} />
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
