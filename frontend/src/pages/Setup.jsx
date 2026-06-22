import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authAPI } from '../api/client';
import { useAuth } from '../context/AuthContext';

export default function Setup() {
  const [form, setForm] = useState({ username: '', password: '', confirm_password: '', first_name: '', last_name: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (form.password !== form.confirm_password) {
      setError('Passwords do not match');
      return;
    }
    if (form.password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }

    setLoading(true);
    try {
      const res = await authAPI.setup({
        username: form.username,
        password: form.password,
        first_name: form.first_name,
        last_name: form.last_name,
      });
      localStorage.setItem('access_token', res.data.access);
      localStorage.setItem('refresh_token', res.data.refresh);
      localStorage.setItem('user', JSON.stringify(res.data.user));
      window.location.href = '/';
    } catch (err) {
      setError(err.response?.data?.error || 'Setup failed');
    }
    setLoading(false);
  };

  return (
    <div className="login-page">
      <div className="login-card" style={{ maxWidth: 480 }}>
        <div className="login-header">
          <span style={{ fontSize: '2rem' }}>🐔</span>
          <h1>Sai Ram Feeds</h1>
          <p>First Time Setup — Create Admin Account</p>
        </div>
        {error && <div className="error-msg">{error}</div>}
        <form onSubmit={handleSubmit}>
          <div className="form-row">
            <div className="form-group">
              <label>First Name</label>
              <input value={form.first_name} onChange={e => setForm({ ...form, first_name: e.target.value })} placeholder="e.g. Sai" />
            </div>
            <div className="form-group">
              <label>Last Name</label>
              <input value={form.last_name} onChange={e => setForm({ ...form, last_name: e.target.value })} placeholder="e.g. Charan" />
            </div>
          </div>
          <div className="form-group">
            <label>Username *</label>
            <input value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} required placeholder="Choose a username" />
          </div>
          <div className="form-group">
            <label>Password *</label>
            <input type="password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} required placeholder="At least 8 characters" />
          </div>
          <div className="form-group">
            <label>Confirm Password *</label>
            <input type="password" value={form.confirm_password} onChange={e => setForm({ ...form, confirm_password: e.target.value })} required />
          </div>
          <button type="submit" className="btn btn-primary login-btn" disabled={loading}>
            {loading ? 'Creating...' : 'Create Admin & Start'}
          </button>
        </form>
      </div>
    </div>
  );
}
