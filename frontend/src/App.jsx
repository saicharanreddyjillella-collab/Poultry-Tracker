import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import FarmForm from './pages/FarmForm';
import FarmDetail from './pages/FarmDetail';
import FlockDetail from './pages/FlockDetail';
import MonthlyReport from './pages/MonthlyReport';
import TillDateReport from './pages/TillDateReport';
import './App.css';

function App() {
  return (
    <BrowserRouter>
      <nav className="navbar">
        <Link to="/" className="nav-brand">🐔 PoultryTrack</Link>
        <div className="nav-links">
          <Link to="/">Today</Link>
          <Link to="/reports/monthly">Monthly</Link>
          <Link to="/reports/till-date">Till Date</Link>
          <Link to="/farms/new">+ Farm</Link>
        </div>
      </nav>
      <main className="main-content">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/farms/new" element={<FarmForm />} />
          <Route path="/farms/:id/edit" element={<FarmForm />} />
          <Route path="/farms/:id" element={<FarmDetail />} />
          <Route path="/flocks/:id" element={<FlockDetail />} />
          <Route path="/reports/monthly" element={<MonthlyReport />} />
          <Route path="/reports/till-date" element={<TillDateReport />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}

export default App;
