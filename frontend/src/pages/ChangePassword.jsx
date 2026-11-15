import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authAPI, getErrorMessage } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { PASSWORD_HINT } from '../utils/password';
import UnsavedPrompt from '../components/UnsavedPrompt';

export default function ChangePassword() {
  const [form, _setForm] = useState({ current_password: '', new_password: '', confirm_password: '' });
  const [dirty, setDirty] = useState(false);
  const setForm = (v) => { _setForm(v); setDirty(true); };
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const { user, updateUser } = useAuth();
  const navigate = useNavigate();
  const firstLogin = !!user?.must_change_password;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (form.new_password !== form.confirm_password) {
      setError('New passwords do not match');
      return;
    }
    if (form.new_password.length < 8) {
      setError('New password must be at least 8 characters');
      return;
    }
    if (form.new_password === form.current_password) {
      setError('Choose a new password different from the current one');
      return;
    }

    setLoading(true);
    try {
      const res = await authAPI.changePassword(form.current_password, form.new_password);
      // Server signs out other sessions and returns fresh tokens for this one.
      if (res.data.access) localStorage.setItem('access_token', res.data.access);
      if (res.data.refresh) localStorage.setItem('refresh_token', res.data.refresh);
      setDirty(false);
      setForm({ current_password: '', new_password: '', confirm_password: '' });
      if (res.data.user) updateUser(res.data.user);
      if (firstLogin) {
        navigate(res.data.user?.role === 'plant' ? '/feed' : '/', { replace: true });
        return;
      }
      setSuccess('Password changed. You have been signed out on other devices.');
    } catch (err) {
      setError(getErrorMessage(err));
    }
    setLoading(false);
  };

  return (
    <div className="page">
      <UnsavedPrompt when={dirty} message="You have unsaved password changes. Discard?" />
      <h1>{firstLogin ? 'Set your password' : 'Change Password'}</h1>
      {firstLogin && (
        <div className="alert-banner alert-banner-warning" role="status" style={{ maxWidth: 400 }}>
          Welcome{user?.first_name ? `, ${user.first_name}` : ''}! Your password was set by an administrator.
          Please choose your own password to continue.
        </div>
      )}
      <form onSubmit={handleSubmit} className="form-card" style={{ maxWidth: 400 }}>
        {error && <div className="error-msg">{error}</div>}
        {success && <div className="success-msg">{success}</div>}
        <div className="form-group">
          <label>{firstLogin ? 'Password you were given *' : 'Current Password *'}</label>
          <input type="password" value={form.current_password} onChange={e => setForm({ ...form, current_password: e.target.value })} required />
        </div>
        <div className="form-group">
          <label>New Password *</label>
          <input type="password" value={form.new_password} onChange={e => setForm({ ...form, new_password: e.target.value })} required autoComplete="new-password" />
          <small className="farm-meta">{PASSWORD_HINT}</small>
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
