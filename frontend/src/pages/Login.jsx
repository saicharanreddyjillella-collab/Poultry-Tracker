import { useState, useEffect } from 'react';
import { useNavigate, Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { authAPI } from '../api/client';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [needsSetup, setNeedsSetup] = useState(null);
  const { login, user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    authAPI.checkSetup().then(res => {
      setNeedsSetup(res.data.needs_setup);
    }).catch(() => setNeedsSetup(false));
  }, []);

  if (user) return <Navigate to={user.role === 'plant' ? '/feed' : '/'} replace />;
  if (needsSetup === true) return <Navigate to="/setup" replace />;
  if (needsSetup === null) return <div className="loading">Loading...</div>;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const u = await login(username, password);
      navigate(u.role === 'plant' ? '/feed' : '/', { replace: true });
    } catch {
      setError('Invalid username or password');
    }
    setLoading(false);
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-header">
          <span style={{ fontSize: '2rem' }}>🐔</span>
          <h1>Sai Ram Feeds</h1>
          <p>Sign in to your account</p>
        </div>
        {error && <div className="error-msg">{error}</div>}
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Username</label>
            <input value={username} onChange={e => setUsername(e.target.value)} required autoFocus placeholder="Enter username" />
          </div>
          <div className="form-group">
            <label>Password</label>
            <input type="password" value={password} onChange={e => setPassword(e.target.value)} required placeholder="Enter password" />
          </div>
          <button type="submit" className="btn btn-primary login-btn" disabled={loading}>
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  );
}
