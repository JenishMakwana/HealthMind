import { useState, useEffect } from 'react';
import { Loader2 } from 'lucide-react';
import { useAuth } from './context/AuthContext';
import AuthPage from './pages/AuthPage';
import Sidebar from './components/Sidebar';
import ChatView from './components/ChatView';
import AdminPanel from './components/AdminPanel';
import { api } from './api/client';

function LoadingScreen() {
  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--bg-primary)' }}>
      <div className="text-center">
        <Loader2 size={28} className="animate-spin mx-auto mb-3" style={{ color: 'var(--accent)' }} />
        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Loading HealthMind...</p>
      </div>
    </div>
  );
}

export default function App() {
  const { user, loading } = useAuth();
  const [conversations, setConversations] = useState([]);
  const [activeConv, setActiveConv] = useState(null);
  const [showAdmin, setShowAdmin] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  useEffect(() => {
    if (user) {
      api.listConversations().then(setConversations).catch(console.error);
    } else {
      setConversations([]);
      setActiveConv(null);
    }
  }, [user]);

  const handleNewConv = async () => {
    try {
      const conv = await api.createConversation('New Chat');
      setConversations((prev) => [conv, ...prev]);
      setActiveConv(conv);
      setShowAdmin(false);
    } catch (err) {
      console.error(err);
    }
  };

  const handleDelete = async (convId) => {
    try {
      await api.deleteConversation(convId);
      setConversations((prev) => prev.filter((c) => c.id !== convId));
      if (activeConv?.id === convId) setActiveConv(null);
    } catch (err) {
      console.error(err);
    }
  };

  const handleRename = async (convId, title) => {
    try {
      const updated = await api.renameConversation(convId, title);
      setConversations((prev) => prev.map((c) => (c.id === convId ? updated : c)));
      if (activeConv?.id === convId) setActiveConv(updated);
    } catch (err) {
      console.error(err);
    }
  };

  const refreshConvTitle = async (convId) => {
    try {
      const convs = await api.listConversations();
      setConversations(convs);
      const updated = convs.find((c) => c.id === convId);
      if (updated && activeConv?.id === convId) setActiveConv(updated);
    } catch {
      // no-op
    }
  };

  if (loading) return <LoadingScreen />;
  if (!user) return <AuthPage />;

  return (
    <div className="flex h-screen overflow-hidden app-shell" style={{ background: 'var(--bg-primary)' }}>
      {sidebarOpen && (
        <Sidebar
          conversations={conversations}
          activeId={activeConv?.id}
          onSelect={(conv) => {
            setActiveConv(conv);
            setShowAdmin(false);
          }}
          onNew={handleNewConv}
          onDelete={handleDelete}
          onRename={handleRename}
          onAdminClick={() => setShowAdmin(true)}
          onClose={() => setSidebarOpen(false)}
        />
      )}

      <main className="flex-1 flex overflow-hidden min-h-0 min-w-0">
        {showAdmin ? (
          <AdminPanel onClose={() => setShowAdmin(false)} />
        ) : (
          <ChatView
            conversation={activeConv}
            onTitleChange={refreshConvTitle}
            sidebarOpen={sidebarOpen}
            onToggleSidebar={() => setSidebarOpen((prev) => !prev)}
            onCreateConversation={handleNewConv}
          />
        )}
      </main>
    </div>
  );
}
