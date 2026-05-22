const BASE = import.meta.env.VITE_API_URL || '/api/v1';

function getToken() {
  return localStorage.getItem('access_token');
}

async function request(path, options = {}) {
  const token = getToken();
  const headers = {
    ...(options.body && !(options.body instanceof FormData) ? { 'Content-Type': 'application/json' } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };
  const res = await fetch(`${BASE}${path}`, { ...options, headers });
  if (res.status === 401) {
    // Try refresh
    const refresh = localStorage.getItem('refresh_token');
    if (refresh) {
      const r = await fetch(`${BASE}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refresh }),
      });
      if (r.ok) {
        const data = await r.json();
        localStorage.setItem('access_token', data.access_token);
        localStorage.setItem('refresh_token', data.refresh_token);
        const retryHeaders = {
          ...headers,
          Authorization: `Bearer ${data.access_token}`,
        };
        const retry = await fetch(`${BASE}${path}`, { ...options, headers: retryHeaders });
        if (!retry.ok) throw new Error((await retry.json()).detail || 'Request failed');
        return retry.status === 204 ? null : retry.json();
      }
    }
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(err.detail || 'Request failed');
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  // Auth
  register: (data) => request('/auth/register', { method: 'POST', body: JSON.stringify(data) }),
  login: (data) => request('/auth/login', { method: 'POST', body: JSON.stringify(data) }),
  me: () => request('/auth/me'),

  // Conversations
  listConversations: () => request('/conversations'),
  createConversation: (title = 'New Chat') => request('/conversations', { method: 'POST', body: JSON.stringify({ title }) }),
  getMessages: (convId) => request(`/conversations/${convId}/messages`),
  renameConversation: (convId, title) => request(`/conversations/${convId}`, { method: 'PATCH', body: JSON.stringify({ title }) }),
  deleteConversation: (convId) => request(`/conversations/${convId}`, { method: 'DELETE' }),

  // Query
  query: (data) => request('/query', { method: 'POST', body: JSON.stringify(data) }),

  // Documents
  uploadDocuments: (formData) => request('/documents/upload', { method: 'POST', body: formData }),
  listDocuments: (convId) => request(`/documents?conversation_id=${convId}`),
  deleteDocument: (docId) => request(`/documents/${docId}`, { method: 'DELETE' }),

  // Audio
  transcribeAudio: (formData) => request('/audio/transcribe', { method: 'POST', body: formData }),

  // Health
  health: () => request('/health'),

  // Admin
  adminStats: () => request('/admin/stats'),
  listUsers: () => request('/admin/users'),
  toggleUser: (userId) => request(`/admin/users/${userId}/toggle`, { method: 'PATCH' }),
  updateRole: (userId, role) => request(`/admin/users/${userId}/role?role=${role}`, { method: 'PATCH' }),
};
