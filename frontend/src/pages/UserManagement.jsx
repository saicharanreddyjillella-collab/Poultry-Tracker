import { useState, useEffect } from 'react';
import { authAPI, farmAPI } from '../api/client';
import { useAuth } from '../context/AuthContext';

export default function UserManagement() {
  const { isAdmin } = useAuth();
  const [users, setUsers] = useState([]);
  const [farms, setFarms] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [form, setForm] = useState({
    username: '', password: '', first_name: '', last_name: '',
    role: 'supervisor', phone: '', assigned_farm_ids: [],
  });
  const [error, setError] = useState('');

  const load = async () => {
    const [usersRes, farmsRes] = await Promise.all([authAPI.listUsers(), farmAPI.list()]);
    setUsers(usersRes.data);
    setFarms(farmsRes.data);
  };

  useEffect(() => { load(); }, []);

  if (!isAdmin) return <div className="empty-state"><p>Admin access required.</p></div>;

  const resetForm = () => {
    setForm({ username: '', password: '', first_name: '', last_name: '', role: 'supervisor', phone: '', assigned_farm_ids: [] });
    setEditingUser(null);
    setShowForm(false);
    setError('');
  };

  const startEdit = (u) => {
    setForm({
      username: u.username, password: '', first_name: u.first_name, last_name: u.last_name,
      role: u.role, phone: u.phone, assigned_farm_ids: u.assigned_farm_ids,
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

  const handleDelete = async (u) => {
    if (window.confirm(`Delete user ${u.username}?`)) {
      await authAPI.deleteUser(u.id);
      load();
    }
  };

  const toggleFarm = (farmId) => {
    const ids = form.assigned_farm_ids.includes(farmId)
      ? form.assigned_farm_ids.filter(id => id !== farmId)
      : [...form.assigned_farm_ids, farmId];
    setForm({ ...form, assigned_farm_ids: ids });
  };

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
              <label>Assigned Farms</label>
              <div className="farm-checkbox-grid">
                {farms.map(f => (
                  <label key={f.id} className={`farm-checkbox ${form.assigned_farm_ids.includes(f.id) ? 'farm-checkbox-active' : ''}`}>
                    <input type="checkbox" checked={form.assigned_farm_ids.includes(f.id)} onChange={() => toggleFarm(f.id)} />
                    <span className="farm-code-badge-sm">{f.farm_code}</span> {f.name}
                  </label>
                ))}
                {farms.length === 0 && <span className="farm-meta">No farms created yet</span>}
              </div>
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
            <tr><th>Username</th><th>Name</th><th>Role</th><th>Phone</th><th>Assigned Farms</th><th></th></tr>
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
                    <span className="farm-meta">All farms</span>
                  ) : u.assigned_farm_ids.length > 0 ? (
                    u.assigned_farm_ids.map(fid => {
                      const farm = farms.find(f => f.id === fid);
                      return farm ? <span key={fid} className="farm-code-badge-sm" style={{ marginRight: '0.3rem' }}>{farm.farm_code}</span> : null;
                    })
                  ) : (
                    <span className="farm-meta">None</span>
                  )}
                </td>
                <td>
                  <button className="btn-delete" onClick={() => startEdit(u)} title="Edit" style={{ marginRight: '0.25rem' }}>✎</button>
                  <button className="btn-delete" onClick={() => handleDelete(u)} title="Delete">&times;</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
