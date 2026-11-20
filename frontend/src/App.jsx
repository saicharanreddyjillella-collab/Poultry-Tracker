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
import MonthlyReport from './pages/MonthlyReport';
import TillDateReport from './pages/TillDateReport';
import RegionPerformance from './pages/RegionPerformance';
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
    { to: '/', label: 'Switch Business', icon: 'switch', end: true },
  ];
  return (
    <AppShell brandName={brand.feedsName} logo={brand.feedsLogo} home={isPlant ? '/feed' : '/feeds'}
              showSearch={!isPlant} showAlerts={!isPlant}
              groups={[{ label: 'Operations', links: ops }, { label: 'Analysis', links: analysis }, { label: 'Admin', links: admin }]}>
      {children}
    </AppShell>
  );
}

function ChickenShell({ children }) {
  const groups = [
    { label: 'Trading', links: [
      { to: '/chicken', label: 'Home', icon: 'today', end: true },
      { to: '/chicken/new', label: 'New Entry', icon: 'plus' },
      { to: '/chicken/transactions', label: 'Transactions', icon: 'entry' },
      { to: '/chicken/parties', label: 'Parties', icon: 'users' },
      { to: '/chicken/items', label: 'Items', icon: 'feed' },
    ] },
    { label: 'Accounts', links: [
      { to: '/chicken/ledgers', label: 'Ledgers', icon: 'ledger' },
      { to: '/chicken/outstanding', label: 'Outstanding', icon: 'sale' },
      { to: '/chicken/pending-bills', label: 'Receivables', icon: 'sale' },
      { to: '/chicken/daybook', label: 'Daybook', icon: 'ledger' },
      { to: '/chicken/sales-summary', label: 'Sales Summary', icon: 'reports' },
      { to: '/chicken/reports', label: 'Reports', icon: 'reports' },
    ] },
    { label: 'Close', links: [
      { to: '/chicken/opening', label: 'Opening', icon: 'entry' },
      { to: '/chicken/day-close', label: 'Day Close', icon: 'entry' },
      { to: '/', label: 'Switch Business', icon: 'switch', end: true },
    ] },
  ];
  return <AppShell brandName={brand.chickenName} logo={brand.chickenLogo} home="/chicken" groups={groups}>{children}</AppShell>;
}

function LayerShell({ children }) {
  const groups = [
    { label: 'Farm', links: [
      { to: '/layer', label: 'Home', icon: 'today', end: true },
      { to: '/layer/new', label: 'New Entry', icon: 'plus' },
      { to: '/layer/flocks', label: 'Flocks', icon: 'egg' },
      { to: '/layer/feed', label: 'Feed Mill', icon: 'feed' },
    ] },
    { label: 'Accounts', links: [
      { to: '/layer/transactions', label: 'Transactions', icon: 'entry' },
      { to: '/layer/masters', label: 'Masters', icon: 'ledger' },
      { to: '/layer/reports', label: 'Reports', icon: 'reports' },
      { to: '/layer/day-close', label: 'Day Close', icon: 'entry' },
      { to: '/', label: 'Switch Business', icon: 'switch', end: true },
    ] },
  ];
  return <AppShell brandName={brand.layerName} logo={brand.layerLogo} home="/layer" groups={groups}>{children}</AppShell>;
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

  const routes = (
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
  );

  if (showFeedsNav) return <FeedsShell>{routes}</FeedsShell>;
  if (user && isChicken) return <ChickenShell>{routes}</ChickenShell>;
  if (user && isLayer) return <LayerShell>{routes}</LayerShell>;
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
