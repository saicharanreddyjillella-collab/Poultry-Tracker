import { useState, useEffect } from 'react';
import { authAPI, farmAPI, getErrorMessage } from '../api/client';
import { generatePassword, PASSWORD_HINT } from '../utils/password';
import { useAuth } from '../context/AuthContext';
import ConfirmModal from '../components/ConfirmModal';

export default function UserManagement() {
  const { isAdmin } = useAuth();
  const [users, setUsers] = useState([]);
  const [farms, setFarms] = useState([]);
  const [regions, setRegions] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [confirm, setConfirm] = useState({ open: false, title: '', message: '', onConfirm: null, confirmText: 'Delete', danger: true });
  // Login details to hand to the user — shown once after create / reset.
  const [credentials, setCredentials] = useState(null);
  const [showPassword, setShowPassword] = useState(false);
  const [copied, setCopied] = useState(false);
  const [form, setForm] = useState({
    username: '', password: '', first_name: '', last_name: '',
    role: 'supervisor', phone: '', assigned_regions: [],
  });
  const [newRegion, setNewRegion] = useState('');
  const [error, setError] = useState('');

  const load = async () => {
    const [usersRes, farmsRes, regionsRes] = await Promise.all([
      authAPI.listUsers(), farmAPI.list(), authAPI.listRegions(),
    ]);
    setUsers(usersRes.data);
    setFarms(farmsRes.data);
    setRegions(regionsRes.data);
  };

  useEffect(() => { load(); }, []);

  if (!isAdmin) return <div className="empty-state"><p>Admin access required.</p></div>;

  const resetForm = () => {
    setForm({ username: '', password: '', first_name: '', last_name: '', role: 'supervisor', phone: '', assigned_regions: [] });
    setEditingUser(null);
    setShowForm(false);
    setError('');
    setNewRegion('');
    setShowPassword(false);
  };

  const startEdit = (u) => {
    setForm({
      username: u.username, password: '', first_name: u.first_name, last_name: u.last_name,
      role: u.role, phone: u.phone, assigned_regions: u.assigned_regions || [],
    });
    setEditingUser(u);
    setShowForm(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    try {
      if (editingUser) {
        const data = { ...form };
        if (!data.password) delete data.password;
        await authAPI.updateUser(editingUser.id, data);
        if (form.password) setCredentials({ username: editingUser.username, password: form.password, reset: true });
      } else {
        if (!form.password) { setError('Set a password (or click Generate) — the user needs it to log in.'); return; }
        await authAPI.createUser(form);
        setCredentials({ username: form.username, password: form.password, reset: false });
      }
      setCopied(false);
      resetForm();
      load();
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };

  const resetPassword = (u) => {
    setConfirm({
      open: true, title: 'Reset password', danger: false, confirmText: 'Reset password',
      message: `Give "${u.username}" a new temporary password? They will be signed out and asked to choose their own password at next login.`,
      onConfirm: async () => {
        setConfirm(c => ({ ...c, open: false }));
        const password = generatePassword();
        try {
          await authAPI.updateUser(u.id, { password });
          setCredentials({ username: u.username, password, reset: true });
          setCopied(false);
          load();
        } catch (err) {
          setError(getErrorMessage(err));
        }
      },
    });
  };

  const copyCredentials = async () => {
    const text = `Poultry app login\nUsername: ${credentials.username}\nPassword: ${credentials.password}\n(You'll be asked to set your own password after logging in.)`;
    try { await navigator.clipboard.writeText(text); setCopied(true); } catch { setCopied(false); }
  };

  const handleDelete = (u) => {
    setConfirm({
      open: true, title: 'Delete User', danger: true, confirmText: 'Delete',
      message: `Are you sure you want to delete "${u.username}"? This cannot be undone.`,
      onConfirm: async () => {
        setConfirm({ ...confirm, open: false });
        await authAPI.deleteUser(u.id);
        load();
      }
    });
  };

  const toggleRegion = (region) => {
    const rs = form.assigned_regions.includes(region)
      ? form.assigned_regions.filter(r => r !== region)
      : [...form.assigned_regions, region];
    setForm({ ...form, assigned_regions: rs });
  };

  const addNewRegion = () => {
    const r = newRegion.trim();
    if (r && !form.assigned_regions.includes(r)) {
      setForm({ ...form, assigned_regions: [...form.assigned_regions, r] });
      if (!regions.includes(r)) setRegions([...regions, r].sort());
    }
    setNewRegion('');
  };

  // Get farms count per region for display
  const farmsByRegion = {};
  farms.forEach(f => {
    if (f.region) {
      farmsByRegion[f.region] = (farmsByRegion[f.region] || 0) + 1;
    }
  });

  return (
    <div className="page">
      <div className="page-header">
        <h1>User Management</h1>
        <button className="btn btn-primary" onClick={() => { resetForm(); setShowForm(!showForm); }}>
          + Add User
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="form-card" style={{ marginBottom: '1.5rem' }} autoComplete="off">
          <h3>{editingUser ? `Edit: ${editingUser.username}` : 'New User'}</h3>
          {error && <div className="error-msg">{error}</div>}
          <div className="form-row">
            <div className="form-group">
              <label>Username *</label>
              {/* autoComplete off: stop the browser filling in the ADMIN's own saved login here */}
              <input name="new-user-username" autoComplete="off" value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} required disabled={!!editingUser} />
            </div>
            <div className="form-group">
              <label>{editingUser ? 'Reset password (leave blank to keep)' : 'Password *'}</label>
              <div style={{ display: 'flex', gap: '0.35rem' }}>
                <input
                  name="new-user-password" autoComplete="new-password" type={showPassword ? 'text' : 'password'}
                  value={form.password} onChange={e => setForm({ ...form, password: e.target.value })}
                  placeholder={editingUser ? 'Unchanged' : 'Type or generate'} style={{ flex: 1, minWidth: 0 }}
                />
                <button type="button" className="btn btn-secondary" style={{ padding: '0 0.6rem' }}
                  onClick={() => setShowPassword(v => !v)} aria-label={showPassword ? 'Hide password' : 'Show password'}>
                  {showPassword ? 'Hide' : 'Show'}
                </button>
                <button type="button" className="btn btn-secondary" style={{ padding: '0 0.6rem' }}
                  onClick={() => { setForm({ ...form, password: generatePassword() }); setShowPassword(true); }}>
                  Generate
                </button>
              </div>
              <small className="farm-meta">{PASSWORD_HINT} They'll choose their own password at first login.</small>
            </div>
            <div className="form-group">
              <label>Role *</label>
              <select value={form.role} onChange={e => setForm({ ...form, role: e.target.value })}>
                <option value="admin">Admin</option>
                <option value="supervisor">Supervisor</option>
                <option value="plant">Feed Plant</option>
              </select>
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>First Name</label>
              <input value={form.first_name} onChange={e => setForm({ ...form, first_name: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Last Name</label>
              <input value={form.last_name} onChange={e => setForm({ ...form, last_name: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Phone</label>
              <input value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} />
            </div>
          </div>

          {form.role === 'supervisor' && (
            <div className="form-group">
              <label>Assigned Regions</label>
              <p className="form-hint">Every supervisor can open and enter data for every farm (to cover when someone is on leave).
                Regions decide what their dashboard and reports show first, and which farms' details they can change.</p>
              <div className="region-checkbox-grid">
                {regions.map(r => (
                  <label key={r} className={`farm-checkbox ${form.assigned_regions.includes(r) ? 'farm-checkbox-active' : ''}`}>
                    <input type="checkbox" checked={form.assigned_regions.includes(r)} onChange={() => toggleRegion(r)} />
                    {r} <small className="region-farm-count">({farmsByRegion[r] || 0} farms)</small>
                  </label>
                ))}
              </div>
              <div className="add-region-row">
                <input value={newRegion} onChange={e => setNewRegion(e.target.value)} placeholder="New region name..." onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addNewRegion(); } }} />
                <button type="button" className="btn btn-secondary" onClick={addNewRegion}>+ Add Region</button>
              </div>
              {form.assigned_regions.length > 0 && (
                <div className="selected-regions">
                  Selected: {form.assigned_regions.map(r => (
                    <span key={r} className="region-tag">{r} <button type="button" onClick={() => toggleRegion(r)}>&times;</button></span>
                  ))}
                </div>
              )}
            </div>
          )}

          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={resetForm}>Cancel</button>
            <button type="submit" className="btn btn-primary">{editingUser ? 'Update' : 'Create'} User</button>
          </div>
        </form>
      )}

      {credentials && (
        <div className="form-card" role="status" style={{ marginBottom: '1.5rem', borderLeft: '4px solid #2e7d32' }}>
          <h3 style={{ marginTop: 0 }}>
            {credentials.reset ? `New password for ${credentials.username}` : `User ${credentials.username} created`}
          </h3>
          <p style={{ margin: '0.25rem 0 0.75rem', color: '#555' }}>
            Share these login details with them. This password is shown only now — they'll be asked to choose
            their own the first time they log in.
          </p>
          <div style={{ fontFamily: 'monospace', fontSize: '1.05rem', lineHeight: 1.7 }}>
            <div>Username: <strong>{credentials.username}</strong></div>
            <div>Password: <strong data-testid="shared-password">{credentials.password}</strong></div>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem' }}>
            <button className="btn btn-primary" onClick={copyCredentials}>{copied ? 'Copied ✓' : 'Copy login details'}</button>
            <button className="btn btn-secondary" onClick={() => setCredentials(null)}>Done</button>
          </div>
        </div>
      )}

      {!showForm && error && <div className="error-msg">{error}</div>}

      <div className="table-wrapper">
        <table>
          <thead>
            <tr><th>Username</th><th>Name</th><th>Role</th><th>Phone</th><th>Regions</th><th></th></tr>
          </thead>
          <tbody>
            {users.map(u => (
              <tr key={u.id}>
                <td>
                  <strong>{u.username}</strong>
                  {u.must_change_password && (
                    <span className="farm-meta" title="Using a password set by an admin" style={{ display: 'block', fontSize: '0.75rem' }}>
                      temporary password
                    </span>
                  )}
                </td>
                <td>{u.first_name} {u.last_name}</td>
                <td><span className={`role-badge role-badge-${u.role}`}>{u.role}</span></td>
                <td>{u.phone || '—'}</td>
                <td>
                  {u.role === 'admin' ? (
                    <span className="farm-meta">All regions</span>
                  ) : u.role === 'plant' ? (
                    <span className="farm-meta">Feed only</span>
                  ) : (u.assigned_regions || []).length > 0 ? (
                    (u.assigned_regions || []).map(r => (
                      <span key={r} className="region-tag-sm">{r}</span>
                    ))
                  ) : (
                    <span className="farm-meta">None</span>
                  )}
                </td>
                <td>
                  <button className="btn-action btn-action-edit" onClick={() => startEdit(u)}>Edit</button>
                  {u.role !== 'admin' && (
                    <button className="btn-action btn-action-edit" onClick={() => resetPassword(u)} style={{ marginLeft: '0.25rem' }}>Reset password</button>
                  )}
                  <button className="btn-action btn-action-cancel" onClick={() => handleDelete(u)} style={{ marginLeft: '0.25rem' }}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ConfirmModal
        open={confirm.open}
        title={confirm.title}
        message={confirm.message}
        danger={confirm.danger}
        confirmText={confirm.confirmText}
        onConfirm={confirm.onConfirm}
        onCancel={() => setConfirm({ ...confirm, open: false })}
      />
    </div>
  );
}
