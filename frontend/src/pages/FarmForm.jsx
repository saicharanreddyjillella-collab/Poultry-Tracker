import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { farmAPI } from '../api/client';
import { useAuth } from '../context/AuthContext';
import UnsavedPrompt from '../components/UnsavedPrompt';

export default function FarmForm() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { isAdmin, user } = useAuth();
  const isEdit = Boolean(id);
  const [error, setError] = useState('');
  const [myRegions, setMyRegions] = useState([]);
  const [dirty, setDirty] = useState(false);

  const [form, _setForm] = useState({
    farm_code: '', name: '', owner_name: '', shed_type: 'OPEN', region: '', location: '', capacity: 5000,
    pan: '', entity_type: 'individual',
  });
  const setForm = (v) => { _setForm(v); setDirty(true); };

  useEffect(() => {
    if (isEdit) {
      farmAPI.get(id).then(res => setForm(res.data));
    }
    // For supervisors, get their assigned regions
    if (!isAdmin && user) {
      farmAPI.list().then(res => {
        const assignedFarms = res.data.filter(f => user.assigned_farm_ids?.includes(f.id));
        // Assigned regions count even before they contain any farm.
        const regions = [...new Set([...(user.assigned_regions || []), ...assignedFarms.map(f => f.region)].filter(Boolean))].sort();
        setMyRegions(regions);
        // Auto-select first region if only one
        if (regions.length === 1 && !isEdit) {
          setForm(prev => ({ ...prev, region: regions[0] }));
        }
      });
    }
  }, [id, isAdmin]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    try {
      const submitData = { ...form, capacity: parseInt(form.capacity) || 0 };
      if (isEdit) {
        await farmAPI.update(id, submitData);
      } else {
        await farmAPI.create(submitData);
      }
      setDirty(false);
      navigate('/farms');
    } catch (err) {
      if (err.response?.data?.farm_code) {
        setError('Farm code already exists. Please use a unique code.');
      } else if (err.response?.data?.region) {
        setError(Array.isArray(err.response.data.region) ? err.response.data.region[0] : err.response.data.region);
      } else if (err.response?.data) {
        setError(typeof err.response.data === 'string' ? err.response.data : JSON.stringify(err.response.data));
      } else {
        setError('Failed to save farm');
      }
    }
  };

  return (
    <div className="page">
      <UnsavedPrompt when={dirty} message="You have unsaved farm details. Discard changes?" />
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
            <label>Grower Entity Type</label>
            <select value={form.entity_type} onChange={e => setForm({ ...form, entity_type: e.target.value })}>
              <option value="individual">Individual</option>
              <option value="huf">HUF</option>
              <option value="firm">Partnership / Firm</option>
              <option value="company">Company</option>
              <option value="llp">LLP</option>
              <option value="fpo">FPO</option>
              <option value="other">Other</option>
            </select>
            <small className="field-hint">1% TDS for Individual/HUF, 2% otherwise</small>
          </div>
          <div className="form-group">
            <label>PAN</label>
            <input value={form.pan || ''} onChange={e => setForm({ ...form, pan: e.target.value.toUpperCase() })} placeholder="ABCDE1234F" maxLength={10} style={{ textTransform: 'uppercase' }} />
            <small className="field-hint">Used for TDS reporting (optional)</small>
          </div>
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
            <label>Region *</label>
            {isAdmin ? (
              <input value={form.region} onChange={e => setForm({ ...form, region: e.target.value })} required placeholder="e.g. Medchal, Ranga Reddy" />
            ) : (
              <select value={form.region} onChange={e => setForm({ ...form, region: e.target.value })} required>
                <option value="">Select region...</option>
                {myRegions.map(r => <option key={r} value={r}>{r}</option>)}
              </select>
            )}
            {!isAdmin && <small className="field-hint">You can only create farms in your assigned regions</small>}
          </div>
          <div className="form-group">
            <label>Location</label>
            <input value={form.location} onChange={e => setForm({ ...form, location: e.target.value })} placeholder="e.g. Village name, landmark" />
          </div>
          <div className="form-group">
            <label>Capacity (birds) *</label>
            <input type="text" inputMode="numeric" pattern="[0-9]*" value={form.capacity} onChange={e => setForm({ ...form, capacity: e.target.value })} required />
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
