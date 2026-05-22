import { useState } from 'react';
import {
  MessageSquare, Plus, Trash2, Edit3, Check, X,
  Stethoscope, LogOut, ShieldCheck, Search, PanelLeftClose
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function Sidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
  onRename,
  onAdminClick,
  onClose,
}) {
  const { user, logout } = useAuth();
  const [editingId, setEditingId] = useState(null);
  const [editTitle, setEditTitle] = useState('');
  const [query, setQuery] = useState('');

  const startEdit = (conv, e) => {
    e.stopPropagation();
    setEditingId(conv.id);
    setEditTitle(conv.title);
  };

  const confirmEdit = async (id) => {
    if (editTitle.trim()) {
      await onRename(id, editTitle.trim());
    }
    setEditingId(null);
  };

  const filtered = conversations.filter((conv) =>
    conv.title.toLowerCase().includes(query.toLowerCase()),
  );

  const now = new Date();
  const groups = { Today: [], 'Last 7 Days': [], Older: [] };
  filtered.forEach((conv) => {
    const d = new Date(conv.updated_at);
    const diffDays = (now - d) / 86400000;
    if (diffDays < 1) groups.Today.push(conv);
    else if (diffDays < 7) groups['Last 7 Days'].push(conv);
    else groups.Older.push(conv);
  });

  return (
    <aside className="health-sidebar h-full shrink-0">
      <div className="sidebar-brand">
        <div className="sidebar-logo">
          <Stethoscope size={15} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="sidebar-title">HealthMind</p>
          <p className="sidebar-subtitle">Premium Medical Workspace</p>
        </div>
        <button className="icon-button hide-mobile" onClick={onClose} title="Collapse sidebar">
          <PanelLeftClose size={15} />
        </button>
      </div>

      <div className="sidebar-section">
        <button onClick={onNew} className="primary-sidebar-button">
          <Plus size={15} />
          New Chat
        </button>
      </div>

      <div className="sidebar-section">
        <div className="sidebar-search">
          <Search size={14} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search chats..."
          />
        </div>
      </div>

      <div className="sidebar-scroll">
        {filtered.length > 0 && !activeId && !query && (
          <div className="sidebar-hint">
            Select a chat from the list or create a new one.
          </div>
        )}

        {filtered.length === 0 ? (
          <div className="sidebar-empty">
            <MessageSquare size={18} />
            <p>{query ? 'No chats found' : 'No conversations yet'}</p>
          </div>
        ) : (
          Object.entries(groups).map(([label, items]) => (
            items.length > 0 && (
              <div key={label} className="sidebar-group">
                <p className="sidebar-group-label">{label}</p>
                {items.map((conv) => (
                  <ConversationItem
                    key={conv.id}
                    conv={conv}
                    active={conv.id === activeId}
                    editing={editingId === conv.id}
                    editTitle={editTitle}
                    setEditTitle={setEditTitle}
                    onSelect={() => onSelect(conv)}
                    onStartEdit={(e) => startEdit(conv, e)}
                    onConfirmEdit={() => confirmEdit(conv.id)}
                    onCancelEdit={() => setEditingId(null)}
                    onDelete={(e) => {
                      e.stopPropagation();
                      onDelete(conv.id);
                    }}
                  />
                ))}
              </div>
            )
          ))
        )}
      </div>

      <div className="sidebar-footer">
        {user?.role === 'admin' && (
          <button className="sidebar-footer-action" onClick={onAdminClick}>
            <ShieldCheck size={14} />
            Admin Panel
          </button>
        )}

        <div className="sidebar-user-card">
          <div className="sidebar-user-avatar">
            {user?.full_name?.[0]?.toUpperCase() || 'U'}
          </div>
          <div className="min-w-0 flex-1">
            <p className="sidebar-user-name">{user?.full_name}</p>
            <p className="sidebar-user-email">{user?.email}</p>
          </div>
          <button className="icon-button" onClick={logout} title="Sign out">
            <LogOut size={14} />
          </button>
        </div>
      </div>
    </aside>
  );
}

function ConversationItem({
  conv,
  active,
  editing,
  editTitle,
  setEditTitle,
  onSelect,
  onStartEdit,
  onConfirmEdit,
  onCancelEdit,
  onDelete,
}) {
  return (
    <div className={`conversation-item ${active ? 'active' : ''}`} onClick={onSelect}>
      <MessageSquare size={14} className="conversation-icon" />

      {editing ? (
        <div className="conversation-edit-row">
          <input
            autoFocus
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => {
              if (e.key === 'Enter') onConfirmEdit();
              if (e.key === 'Escape') onCancelEdit();
            }}
            className="conversation-edit-input"
          />
          <button className="icon-button small" onClick={(e) => { e.stopPropagation(); onConfirmEdit(); }}>
            <Check size={12} />
          </button>
          <button className="icon-button small" onClick={(e) => { e.stopPropagation(); onCancelEdit(); }}>
            <X size={12} />
          </button>
        </div>
      ) : (
        <>
          <div className="conversation-copy">
            <p className="conversation-title">{conv.title}</p>
            <p className="conversation-date">
              {new Date(conv.updated_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
            </p>
          </div>
          <div className="conversation-actions">
            <button className="icon-button small" onClick={onStartEdit}>
              <Edit3 size={12} />
            </button>
            <button className="icon-button small danger" onClick={onDelete}>
              <Trash2 size={12} />
            </button>
          </div>
        </>
      )}
    </div>
  );
}
