import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { farmAPI } from '../api/client';

export default function FarmForm() {
  const { id } = useParams();
  const navigate = useNavigate();
  const isEdit = Boolean(id);
  const [error, setError] = useState('');

  const [form, setForm] = useState({
    farm_code: '', name: '', owner_name: '', shed_type: 'OPEN', region: '', location: '', capacity: 5000,
  });

  useEffect(() => {
    if (isEdit) {
      farmAPI.get(id).then(res => setForm(res.data));
    }
  }, [id]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    try {
      if (isEdit) {
        await farmAPI.update(id, form);
      } else {
        await farmAPI.create(form);
      }
      navigate('/farms');
    } catch (err) {
      if (err.response?.data?.farm_code) {
        setError('Farm code already exists. Please use a unique code.');
      } else if (err.response?.data) {
        setError(JSON.stringify(err.response.data));
      } else {
        setError('Failed to save farm');
      }
    }
  };

  return (
    <div className="page">
      <h1>{isEdit ? 'Edit Farm' : 'Add New Farm'}</h1>
      <form onSubmit={handleSubmit} className="form-card">
        {error && <div className="error-msg">{error}</div>}
        <div className="form-row">
          <div className="form-group">
            <label>Farm Code *</label>
            <input value={form.farm_code} onChange={e => setForm({ ...form, farm_code: e.target.value.toUpperCase() })} required placeholder="e.g. F001, HYD-12" style={{ textTransform: 'uppercase' }} />
            <small className="field-hint">Unique identifier for this farm</small>
          </div>
          <div className="form-group">
            <label>Farm Name *</label>
            <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required placeholder="e.g. Sai Poultry Farm" />
          </div>
        </div>
        <div className="form-group">
          <label>Owner / Farmer Name *</label>
          <input value={form.owner_name} onChange={e => setForm({ ...form, owner_name: e.target.value })} required />
        </div>
        <div className="form-row">
          <div className="form-group">
            <label>Shed Type *</label>
            <select value={form.shed_type} onChange={e => setForm({ ...form, shed_type: e.target.value })}>
              <option value="OPEN">Open Shed</option>
              <option value="EC">EC (Environmentally Controlled)</option>
            </select>
          </div>
          <div className="form-group">
            <label>Region</label>
            <input value={form.region} onChange={e => setForm({ ...form, region: e.target.value })} placeholder="e.g. Medchal, Ranga Reddy, North" />
            <small className="field-hint">Used for grouping farms in region reports</small>
          </div>
          <div className="form-group">
            <label>Location</label>
            <input value={form.location} onChange={e => setForm({ ...form, location: e.target.value })} placeholder="e.g. Village name, landmark" />
          </div>
          <div className="form-group">
            <label>Capacity (birds) *</label>
            <input type="number" min="100" value={form.capacity} onChange={e => setForm({ ...form, capacity: parseInt(e.target.value) || 0 })} required placeholder="e.g. 5000" />
            <small className="field-hint">Max birds this farm can hold. Flock size must be within ±5%</small>
          </div>
        </div>
        <div className="form-actions">
          <button type="button" className="btn btn-secondary" onClick={() => navigate(-1)}>Cancel</button>
          <button type="submit" className="btn btn-primary">{isEdit ? 'Update' : 'Create'} Farm</button>
        </div>
      </form>
    </div>
  );
}
