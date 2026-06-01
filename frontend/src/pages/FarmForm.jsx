import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { farmAPI } from '../api/client';

export default function FarmForm() {
  const { id } = useParams();
  const navigate = useNavigate();
  const isEdit = Boolean(id);

  const [form, setForm] = useState({
    name: '', owner_name: '', location: '', house_count: 1,
  });

  useEffect(() => {
    if (isEdit) {
      farmAPI.get(id).then(res => setForm(res.data));
    }
  }, [id]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isEdit) {
      await farmAPI.update(id, form);
    } else {
      await farmAPI.create(form);
    }
    navigate('/');
  };

  return (
    <div className="page">
      <h1>{isEdit ? 'Edit Farm' : 'Add New Farm'}</h1>
      <form onSubmit={handleSubmit} className="form-card">
        <div className="form-group">
          <label>Farm Name *</label>
          <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required />
        </div>
        <div className="form-group">
          <label>Owner / Farmer Name *</label>
          <input value={form.owner_name} onChange={e => setForm({ ...form, owner_name: e.target.value })} required />
        </div>
        <div className="form-group">
          <label>Location</label>
          <input value={form.location} onChange={e => setForm({ ...form, location: e.target.value })} />
        </div>
        <div className="form-group">
          <label>Number of Houses</label>
          <input type="number" min="1" value={form.house_count} onChange={e => setForm({ ...form, house_count: parseInt(e.target.value) || 1 })} />
        </div>
        <div className="form-actions">
          <button type="button" className="btn btn-secondary" onClick={() => navigate(-1)}>Cancel</button>
          <button type="submit" className="btn btn-primary">{isEdit ? 'Update' : 'Create'} Farm</button>
        </div>
      </form>
    </div>
  );
}
