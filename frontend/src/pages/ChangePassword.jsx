import { useState } from 'react';
import { authAPI } from '../api/client';

export default function ChangePassword() {
  const [form, setForm] = useState({ current_password: '', new_password: '', confirm_password: '' });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (form.new_password !== form.confirm_password) {
      setError('New passwords do not match');
      return;
    }
    if (form.new_password.length < 6) {
      setError('New password must be at least 6 characters');
      return;
    }

    setLoading(true);
    try {
      const res = await authAPI.changePassword(form.current_password, form.new_password);
      // Update tokens
      localStorage.setItem('access_token', res.data.access);
      localStorage.setItem('refresh_token', res.data.refresh);
      setSuccess('Password changed successfully');
      setForm({ current_password: '', new_password: '', confirm_password: '' });
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to change password');
    }
    setLoading(false);
  };

  return (
    <div className="page">
      <h1>Change Password</h1>
      <form onSubmit={handleSubmit} className="form-card" style={{ maxWidth: 400 }}>
        {error && <div className="error-msg">{error}</div>}
        {success && <div className="success-msg">{success}</div>}
        <div className="form-group">
          <label>Current Password *</label>
          <input type="password" value={form.current_password} onChange={e => setForm({ ...form, current_password: e.target.value })} required />
        </div>
        <div className="form-group">
          <label>New Password *</label>
          <input type="password" value={form.new_password} onChange={e => setForm({ ...form, new_password: e.target.value })} required placeholder="At least 6 characters" />
        </div>
        <div className="form-group">
          <label>Confirm New Password *</label>
          <input type="password" value={form.confirm_password} onChange={e => setForm({ ...form, confirm_password: e.target.value })} required />
        </div>
        <div className="form-actions">
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? 'Changing...' : 'Change Password'}
          </button>
        </div>
      </form>
    </div>
  );
}
