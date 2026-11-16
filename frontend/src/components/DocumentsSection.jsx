import { useState, useEffect, useRef } from 'react';
import { documentAPI, getErrorMessage } from '../api/client';

const DOC_TYPES = [
  ['agreement', 'Farmer Agreement'],
  ['kyc', 'KYC / ID Proof'],
  ['bank', 'Bank Proof'],
  ['vet_certificate', 'Vet / Cull Certificate'],
  ['invoice', 'Invoice / Bill Copy'],
  ['other', 'Other'],
];

/**
 * Documents attached to a farm or a flock. Pass exactly one of farmId / flockId.
 * canEdit controls whether upload/delete are shown.
 */
export default function DocumentsSection({ farmId, flockId, canEdit = true }) {
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [docType, setDocType] = useState('agreement');
  const [title, setTitle] = useState('');
  const [notes, setNotes] = useState('');
  const [file, setFile] = useState(null);
  const [error, setError] = useState('');
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef(null);

  const params = farmId ? { farm: farmId } : { flock: flockId };

  const load = () => {
    setLoading(true);
    documentAPI.list(params)
      .then(r => setDocs(r.data))
      .catch(() => setDocs([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [farmId, flockId]);

  const resetForm = () => {
    setDocType('agreement'); setTitle(''); setNotes(''); setFile(null);
    if (fileRef.current) fileRef.current.value = '';
    setShowForm(false); setError('');
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    setError('');
    if (!file) { setError('Choose a file to upload.'); return; }
    if (file.size > 10 * 1024 * 1024) { setError('File is larger than 10 MB.'); return; }
    const fd = new FormData();
    if (farmId) fd.append('farm', farmId);
    if (flockId) fd.append('flock', flockId);
    fd.append('doc_type', docType);
    fd.append('title', title);
    fd.append('notes', notes);
    fd.append('file', file);
    setUploading(true);
    try {
      await documentAPI.upload(fd);
      resetForm();
      load();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this document? An admin can restore it from the Recycle Bin.')) return;
    try { await documentAPI.delete(id); load(); } catch { /* ignore */ }
  };

  return (
    <div className="documents-section">
      <div className="documents-head">
        <h3>Documents</h3>
        {canEdit && !showForm && (
          <button className="btn btn-secondary btn-sm" onClick={() => setShowForm(true)}>+ Add Document</button>
        )}
      </div>

      {showForm && (
        <form className="document-form" onSubmit={handleUpload}>
          {error && <div className="alert-banner alert-banner-danger">{error}</div>}
          <div className="form-row">
            <div className="form-group">
              <label>Type</label>
              <select value={docType} onChange={e => setDocType(e.target.value)}>
                {DOC_TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>Title (optional)</label>
              <input value={title} onChange={e => setTitle(e.target.value)} placeholder="e.g. 2026 agreement" />
            </div>
          </div>
          <div className="form-group">
            <label>File (max 10 MB)</label>
            <input ref={fileRef} type="file" onChange={e => setFile(e.target.files[0] || null)} />
          </div>
          <div className="form-group">
            <label>Notes (optional)</label>
            <input value={notes} onChange={e => setNotes(e.target.value)} />
          </div>
          <div className="modal-actions">
            <button type="button" className="btn btn-secondary" onClick={resetForm} disabled={uploading}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={uploading}>{uploading ? 'Uploading…' : 'Upload'}</button>
          </div>
        </form>
      )}

      {loading ? (
        <p className="muted">Loading documents…</p>
      ) : docs.length === 0 ? (
        <p className="muted">No documents yet.</p>
      ) : (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr><th>Type</th><th>Title</th><th>Uploaded</th><th>By</th><th></th></tr>
            </thead>
            <tbody>
              {docs.map(d => (
                <tr key={d.id}>
                  <td>{d.doc_type_display}</td>
                  <td>{d.title || d.original_name}</td>
                  <td>{new Date(d.uploaded_at).toLocaleDateString('en-IN')}</td>
                  <td>{d.uploaded_by_name || '—'}</td>
                  <td style={{ whiteSpace: 'nowrap' }}>
                    <a href={d.file_url} target="_blank" rel="noreferrer" className="link-action">View</a>
                    {canEdit && (
                      <button className="link-action link-danger" onClick={() => handleDelete(d.id)}>Delete</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
