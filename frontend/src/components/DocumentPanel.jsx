import { useState, useRef, useCallback } from 'react';
import {
  Upload, FileText, Trash2, CheckCircle, Clock, AlertCircle,
  X, Loader2, FilePlus, ChevronDown
} from 'lucide-react';
import { api } from '../api/client';

export default function DocumentPanel({ conversationId, documents, onDocumentsChange }) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadErr, setUploadErr] = useState('');
  const fileRef = useRef();

  const upload = async (files) => {
    if (!files.length || !conversationId) return;
    setUploading(true);
    setUploadErr('');
    try {
      const fd = new FormData();
      fd.append('conversation_id', conversationId);
      Array.from(files).forEach(f => fd.append('files', f));
      const res = await api.uploadDocuments(fd);
      if (res?.rejected_files?.length > 0) {
        setUploadErr(`Warning: Some files were rejected (non-medical): ${res.rejected_files.join(', ')}`);
      }
      const updated = await api.listDocuments(conversationId);
      onDocumentsChange(updated);
    } catch (err) {
      setUploadErr(err.message);
    } finally {
      setUploading(false);
    }
  };

  const onDrop = useCallback((e) => {
    e.preventDefault();
    setDragging(false);
    upload(e.dataTransfer.files);
  }, [conversationId]);

  const statusIcon = (s) => {
    if (s === 'ready') return <CheckCircle size={13} style={{ color: '#1B7A6E' }} />;
    if (s === 'error') return <AlertCircle size={13} style={{ color: 'var(--danger)' }} />;
    return <Loader2 size={13} className="animate-spin" style={{ color: 'var(--warning)' }} />;
  };

  const statusLabel = (s) => {
    if (s === 'ready') return { label: 'Ready', bg: 'var(--accent-light)', color: 'var(--accent)' };
    if (s === 'error') return { label: 'Error', bg: '#FEF2F0', color: 'var(--danger)' };
    return { label: 'Processing', bg: '#FEF9EC', color: 'var(--warning)' };
  };

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 pt-5 pb-4 border-b" style={{ borderColor: 'var(--border)' }}>
        <h3 className="font-semibold text-sm" style={{ color: 'var(--text-primary)', fontFamily: 'Cormorant Garamond, serif', fontSize: 18 }}>
          Knowledge Base
        </h3>
        <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
          {documents.length} document{documents.length !== 1 ? 's' : ''} · PDF, DOCX, TXT
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {/* Drop zone */}
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => fileRef.current?.click()}
          className="relative flex flex-col items-center justify-center gap-2 rounded-xl p-6 mb-4 cursor-pointer text-center"
          style={{
            border: `2px dashed ${dragging ? 'var(--accent)' : 'var(--border)'}`,
            background: dragging ? 'var(--accent-light)' : 'var(--bg-secondary)',
          }}>
          <input ref={fileRef} type="file" multiple accept=".pdf,.docx,.txt" className="hidden"
            onChange={(e) => upload(e.target.files)} />
          {uploading ? (
            <Loader2 size={22} className="animate-spin" style={{ color: 'var(--accent)' }} />
          ) : (
            <Upload size={22} style={{ color: dragging ? 'var(--accent)' : 'var(--text-muted)' }} />
          )}
          <p className="text-xs font-medium" style={{ color: dragging ? 'var(--accent)' : 'var(--text-secondary)' }}>
            {uploading ? 'Uploading…' : dragging ? 'Drop to upload' : 'Drop files or click to upload'}
          </p>
        </div>

        {uploadErr && (
          <div className="flex items-start gap-2 rounded-xl px-3 py-2.5 mb-3 text-xs"
            style={{ background: '#FEF2F0', border: '1px solid #FCD5CD', color: 'var(--danger)' }}>
            <AlertCircle size={13} className="mt-0.5 shrink-0" />
            <span>{uploadErr}</span>
          </div>
        )}

        {/* Document list */}
        <div className="space-y-2">
          {documents.map((doc) => {
            const s = statusLabel(doc.status);
            return (
              <div key={doc.id}
                className="flex items-start gap-3 rounded-xl p-3 group"
                style={{ background: 'white', border: '1px solid var(--border)' }}>
                <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
                  style={{ background: 'var(--bg-tertiary)' }}>
                  <FileText size={15} style={{ color: 'var(--accent)' }} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium truncate" style={{ color: 'var(--text-primary)' }}>
                    {doc.title || doc.filename}
                  </p>
                  <p className="text-xs mt-0.5 truncate" style={{ color: 'var(--text-muted)' }}>
                    {doc.chunk_count} chunks · {new Date(doc.created_at).toLocaleDateString()}
                  </p>
                  <span className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded-full mt-1 font-medium"
                    style={{ background: s.bg, color: s.color }}>
                    {statusIcon(doc.status)}
                    {s.label}
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        {documents.length === 0 && !uploading && (
          <div className="text-center py-6">
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
              Upload documents to enable RAG queries
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
