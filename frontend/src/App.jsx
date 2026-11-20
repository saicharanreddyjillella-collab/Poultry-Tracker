import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
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
import HeatStress from './pages/HeatStress';
import Hatcheries from './pages/Hatcheries';
import LiftPlanner from './pages/LiftPlanner';
import Settings from './pages/Settings';
import RateCards from './pages/RateCards';
import GrowerRanking from './pages/GrowerRanking';
import SystemHealth from './pages/SystemHealth';
import OwnerDashboard from './pages/OwnerDashboard';
import BreakEven from './pages/BreakEven';
import BillView from './pages/BillView';
import RecycleBin from './pages/RecycleBin';
import './App.css';
import './styles/print.css';
import './styles/bill.css';
import './styles/components.css';
import './styles/business.css';
import './styles/theme.css';
import AppShell from './components/AppShell';
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

function FeedsShell({ children }) {
  const { isAdmin, isPlant } = useAuth();
  const ops = isPlant ? [] : [
    { to: '/feeds', label: 'Today', icon: 'today', end: true },
    { to: '/farms', label: 'Farms', icon: 'farms' },
  ];
  ops.push({ to: '/feed', label: 'Feed', icon: 'feed', end: true });
  const analysis = isPlant ? [] : [{ to: '/reports', label: 'Reports', icon: 'reports' }];
  if (isAdmin) analysis.push({ to: '/insights', label: 'Insights', icon: 'insights' });
  const admin = !isAdmin ? [] : [
    { to: '/users', label: 'Users', icon: 'users' },
    { to: '/settings', label: 'Settings', icon: 'settings' },
    { to: '/trash', label: 'Recycle Bin', icon: 'trash' },
  ];
  return (
    <AppShell brandName={brand.feedsName} logo={brand.feedsLogo} home={isPlant ? '/feed' : '/feeds'}
              showSearch={!isPlant} showAlerts={!isPlant}
              groups={[{ label: 'Operations', links: ops }, { label: 'Analysis', links: analysis }, { label: 'Admin', links: admin }]}>
      {children}
    </AppShell>
  );
}

function AppRoutes() {
  const location = useLocation();
  const { user } = useAuth();
  const path = location.pathname;
  const isAuthPage = path === '/login' || path === '/setup';
  const showNav = user && !isAuthPage;

  const routes = (
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
          <Route path="/heat-stress" element={<ProtectedRoute><HeatStress /></ProtectedRoute>} />
          <Route path="/hatcheries" element={<AdminRoute><Hatcheries /></AdminRoute>} />
          <Route path="/lift-planner" element={<AdminRoute><LiftPlanner /></AdminRoute>} />
          <Route path="/settings" element={<AdminRoute><Settings /></AdminRoute>} />
          <Route path="/settings/rate-cards" element={<AdminRoute><RateCards /></AdminRoute>} />
          <Route path="/grower-ranking" element={<AdminRoute><GrowerRanking /></AdminRoute>} />
          <Route path="/system-health" element={<AdminRoute><SystemHealth /></AdminRoute>} />
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
  );

  if (showNav) return <FeedsShell>{routes}</FeedsShell>;
  return <main className="main-content main-plain">{routes}</main>;
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
