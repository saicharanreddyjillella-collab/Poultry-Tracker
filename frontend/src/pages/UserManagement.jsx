import { useState, useEffect } from 'react';
import { authAPI, farmAPI } from '../api/client';
import { useAuth } from '../context/AuthContext';
import ConfirmModal from '../components/ConfirmModal';

export default function UserManagement() {
  const { isAdmin } = useAuth();
  const [users, setUsers] = useState([]);
  const [farms, setFarms] = useState([]);
  const [regions, setRegions] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [confirm, setConfirm] = useState({ open: false, title: '', message: '', onConfirm: null });
  const [showForm, setShowForm] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
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
      } else {
        if (!form.password) { setError('Password is required'); return; }
        await authAPI.createUser(form);
      }
      resetForm();
      load();
    } catch (err) {
      setError(err.response?.data?.error || JSON.stringify(err.response?.data) || 'Failed');
    }
  };

  const handleDelete = (u) => {
    setConfirm({
      open: true, title: 'Delete User',
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
        <form onSubmit={handleSubmit} className="form-card" style={{ marginBottom: '1.5rem' }}>
          <h3>{editingUser ? `Edit: ${editingUser.username}` : 'New User'}</h3>
          {error && <div className="error-msg">{error}</div>}
          <div className="form-row">
            <div className="form-group">
              <label>Username *</label>
              <input value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} required disabled={!!editingUser} />
            </div>
            <div className="form-group">
              <label>{editingUser ? 'New Password (leave blank to keep)' : 'Password *'}</label>
              <input type="password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} />
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

      <div className="table-wrapper">
        <table>
          <thead>
            <tr><th>Username</th><th>Name</th><th>Role</th><th>Phone</th><th>Regions</th><th></th></tr>
          </thead>
          <tbody>
            {users.map(u => (
              <tr key={u.id}>
                <td><strong>{u.username}</strong></td>
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
        danger
        confirmText="Delete"
        onConfirm={confirm.onConfirm}
        onCancel={() => setConfirm({ ...confirm, open: false })}
      />
    </div>
  );
}
