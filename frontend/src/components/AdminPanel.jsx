import { useState, useEffect } from 'react';
import {
  ShieldCheck, Users, FileText, Database, Cpu, Activity,
  ToggleLeft, ToggleRight, X, Loader2, CheckCircle, AlertCircle,
  TrendingUp, Layers, ChevronLeft
} from 'lucide-react';
import { api } from '../api/client';

export default function AdminPanel({ onClose }) {
  const [tab, setTab] = useState('overview');
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [toggling, setToggling] = useState(null);

  useEffect(() => {
    Promise.all([api.adminStats(), api.listUsers()])
      .then(([s, u]) => { setStats(s); setUsers(u); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const toggleUser = async (userId) => {
    setToggling(userId);
    try {
      const res = await api.toggleUser(userId);
      setUsers(prev => prev.map(u => u.id === userId ? { ...u, is_active: res.is_active } : u));
    } catch (e) {
      setError(e.message);
    } finally {
      setToggling(null);
    }
  };

  const updateRole = async (userId, role) => {
    try {
      await api.updateRole(userId, role);
      setUsers(prev => prev.map(u => u.id === userId ? { ...u, role } : u));
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden" style={{ background: 'var(--bg-primary)' }}>
      {/* Header */}
      <div className="flex items-center gap-4 px-8 py-5 border-b"
        style={{ borderColor: 'var(--border)', background: 'white' }}>
        <button onClick={onClose}
          className="flex items-center gap-2 text-sm font-medium px-3 py-1.5 rounded-lg"
          style={{ color: 'var(--text-secondary)', background: 'var(--bg-secondary)' }}
          onMouseEnter={e => { e.currentTarget.style.background = 'var(--bg-tertiary)'; }}
          onMouseLeave={e => { e.currentTarget.style.background = 'var(--bg-secondary)'; }}>
          <ChevronLeft size={15} />
          Back to Chat
        </button>
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center"
            style={{ background: 'var(--accent-light)' }}>
            <ShieldCheck size={16} style={{ color: 'var(--accent)' }} />
          </div>
          <div>
            <h2 style={{ fontFamily: 'Cormorant Garamond, serif', fontSize: 20 }}
              className="font-semibold leading-none" style={{ color: 'var(--text-primary)', fontFamily: 'Cormorant Garamond, serif', fontSize: 20 }}>
              Admin Panel
            </h2>
            <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>System administration</p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 px-8 pt-4 pb-0 border-b" style={{ borderColor: 'var(--border)' }}>
        {[
          { id: 'overview', label: 'Overview', icon: Activity },
          { id: 'users', label: 'Users', icon: Users },
        ].map(({ id, label, icon: Icon }) => (
          <button key={id} onClick={() => setTab(id)}
            className="flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px"
            style={{
              borderColor: tab === id ? 'var(--accent)' : 'transparent',
              color: tab === id ? 'var(--accent)' : 'var(--text-muted)',
            }}>
            <Icon size={14} />
            {label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto px-8 py-6">
        {loading && (
          <div className="flex items-center justify-center py-20">
            <Loader2 size={24} className="animate-spin" style={{ color: 'var(--accent)' }} />
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 rounded-xl px-4 py-3 mb-4 text-sm"
            style={{ background: '#FEF2F0', border: '1px solid #FCD5CD', color: 'var(--danger)' }}>
            <AlertCircle size={15} />
            {error}
          </div>
        )}

        {!loading && tab === 'overview' && stats && (
          <div className="max-w-3xl space-y-6 animate-fade-in">
            {/* Stat cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { label: 'Total Users', value: stats.total_users, icon: Users, color: 'var(--accent)' },
                { label: 'Documents', value: stats.total_documents, icon: FileText, color: '#8B6FAE' },
                { label: 'Ready Docs', value: stats.ready_documents, icon: CheckCircle, color: '#2A7A3B' },
                { label: 'Chunks Indexed', value: stats.total_chunks_indexed?.toLocaleString() || 0, icon: Layers, color: '#C48A1A' },
              ].map((s) => (
                <div key={s.label} className="rounded-2xl p-4"
                  style={{ background: 'white', border: '1px solid var(--border)', boxShadow: '0 1px 6px rgba(0,0,0,0.05)' }}>
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center mb-3"
                    style={{ background: `${s.color}18` }}>
                    <s.icon size={16} style={{ color: s.color }} />
                  </div>
                  <p className="text-2xl font-semibold" style={{ fontFamily: 'Cormorant Garamond, serif', color: 'var(--text-primary)' }}>
                    {s.value}
                  </p>
                  <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>{s.label}</p>
                </div>
              ))}
            </div>

            {/* System status */}
            <div className="rounded-2xl p-5"
              style={{ background: 'white', border: '1px solid var(--border)' }}>
              <h3 className="font-semibold mb-4 text-sm" style={{ color: 'var(--text-primary)' }}>
                System Status
              </h3>
              <div className="space-y-3">
                {[
                  { label: 'Qdrant Vector Store', status: stats.qdrant_status },
                  { label: 'RAG Pipeline', status: stats.ready_documents > 0 ? 'ok' : 'degraded' },
                ].map((s) => (
                  <div key={s.label} className="flex items-center justify-between">
                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{s.label}</p>
                    <span className="flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full"
                      style={{
                        background: s.status === 'ok' ? 'var(--accent-light)' : '#FEF2F0',
                        color: s.status === 'ok' ? 'var(--accent)' : 'var(--danger)',
                      }}>
                      <div className="w-1.5 h-1.5 rounded-full"
                        style={{ background: s.status === 'ok' ? 'var(--accent)' : 'var(--danger)' }} />
                      {s.status === 'ok' ? 'Operational' : 'Degraded'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {!loading && tab === 'users' && (
          <div className="max-w-3xl animate-fade-in">
            <div className="rounded-2xl overflow-hidden"
              style={{ border: '1px solid var(--border)', background: 'white' }}>
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border)' }}>
                    {['User', 'Role', 'Status', 'Joined', 'Actions'].map((h) => (
                      <th key={h} className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wide"
                        style={{ color: 'var(--text-muted)' }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {users.map((u, i) => (
                    <tr key={u.id}
                      style={{ borderBottom: i < users.length - 1 ? '1px solid var(--border-light)' : 'none' }}>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2.5">
                          <div className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold shrink-0"
                            style={{ background: 'var(--accent-light)', color: 'var(--accent)' }}>
                            {u.full_name?.[0]?.toUpperCase()}
                          </div>
                          <div>
                            <p className="font-medium text-sm" style={{ color: 'var(--text-primary)' }}>{u.full_name}</p>
                            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{u.email}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <select value={u.role} onChange={e => updateRole(u.id, e.target.value)}
                          className="text-xs px-2 py-1 rounded-lg border outline-none cursor-pointer font-medium"
                          style={{
                            background: u.role === 'admin' ? 'var(--accent-light)' : 'var(--bg-secondary)',
                            color: u.role === 'admin' ? 'var(--accent)' : 'var(--text-secondary)',
                            border: '1px solid var(--border)',
                          }}>
                          <option value="user">User</option>
                          <option value="admin">Admin</option>
                        </select>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-xs px-2 py-0.5 rounded-full font-medium"
                          style={{
                            background: u.is_active ? 'var(--accent-light)' : '#FEF2F0',
                            color: u.is_active ? 'var(--accent)' : 'var(--danger)',
                          }}>
                          {u.is_active ? 'Active' : 'Disabled'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs" style={{ color: 'var(--text-muted)' }}>
                        {new Date(u.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => toggleUser(u.id)}
                          disabled={toggling === u.id}
                          className="flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg font-medium"
                          style={{
                            background: u.is_active ? '#FEF2F0' : 'var(--accent-light)',
                            color: u.is_active ? 'var(--danger)' : 'var(--accent)',
                            cursor: toggling === u.id ? 'not-allowed' : 'pointer',
                          }}>
                          {toggling === u.id
                            ? <Loader2 size={11} className="animate-spin" />
                            : u.is_active ? <ToggleLeft size={13} /> : <ToggleRight size={13} />}
                          {u.is_active ? 'Disable' : 'Enable'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
