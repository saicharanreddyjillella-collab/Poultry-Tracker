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
import './App.css';

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="loading">Loading...</div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function NavBar() {
  const { user, logout, isAdmin } = useAuth();
  const navigate = useNavigate();

  if (!user) return null;

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  return (
    <nav className="navbar">
      <Link to="/" className="nav-brand">🐔 PoultryTrack</Link>
      <div className="nav-links">
        <Link to="/">Today</Link>
        <Link to="/farms">Farms</Link>
        <Link to="/reports/monthly">Monthly</Link>
        <Link to="/reports/region">Region</Link>
        <Link to="/reports/till-date">Till Date</Link>
        {isAdmin && <Link to="/users">Users</Link>}
        <div className="nav-user-menu">
          <span className="nav-user-trigger">
            <span className={`role-badge role-badge-${user.role}`}>{user.role}</span>
            {user.first_name || user.username} ▾
          </span>
          <div className="nav-dropdown">
            <Link to="/change-password" className="nav-dropdown-item">Change Password</Link>
            <button className="nav-dropdown-item nav-dropdown-logout" onClick={handleLogout}>Logout</button>
          </div>
        </div>
      </div>
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
