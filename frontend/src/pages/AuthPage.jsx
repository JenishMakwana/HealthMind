import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Stethoscope, Eye, EyeOff, AlertCircle, ArrowRight, Loader2 } from 'lucide-react';

export default function AuthPage({ onSuccess }) {
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState({ email: '', password: '', full_name: '' });
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login, register } = useAuth();

  const set = (k) => (e) => setForm((p) => ({ ...p, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (mode === 'login') {
        await login(form.email, form.password);
      } else {
        await register(form.email, form.password, form.full_name);
      }
      onSuccess?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex" style={{ background: 'var(--bg-primary)' }}>
      {/* Left panel */}
      <div className="hidden lg:flex flex-col justify-between w-[480px] p-12 relative overflow-hidden"
        style={{ background: 'linear-gradient(150deg, #1B7A6E 0%, #0D5247 40%, #0A3D33 100%)' }}>
        {/* Decorative circles */}
        <div className="absolute -top-20 -right-20 w-72 h-72 rounded-full opacity-10"
          style={{ background: 'radial-gradient(circle, #2CC4B3 0%, transparent 70%)' }} />
        <div className="absolute bottom-20 -left-16 w-60 h-60 rounded-full opacity-10"
          style={{ background: 'radial-gradient(circle, #2CC4B3 0%, transparent 70%)' }} />
        <div className="absolute top-1/3 right-8 w-1 h-32 rounded-full opacity-20" style={{ background: '#2CC4B3' }} />

        <div>
          <div className="flex items-center gap-3 mb-16">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center"
              style={{ background: 'rgba(255,255,255,0.15)' }}>
              <Stethoscope size={20} color="white" />
            </div>
            <span className="text-white font-semibold text-lg tracking-tight">HealthMind</span>
          </div>

          <div>
            <p className="text-sm font-medium tracking-widest uppercase mb-4"
              style={{ color: 'rgba(44,196,179,0.8)' }}>Medical Knowledge AI</p>
            <h1 style={{ fontFamily: 'Cormorant Garamond, serif' }}
              className="text-5xl font-light text-white leading-tight mb-6">
              Intelligence<br />at the speed<br />of care
            </h1>
            <p className="text-base leading-relaxed" style={{ color: 'rgba(255,255,255,0.6)' }}>
              Upload medical literature, guidelines, and research. Query your knowledge base with contextual AI retrieval powered by Llama 4 and BioBERT.
            </p>
          </div>
        </div>


      </div>

      {/* Right panel */}
      <div className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-2 mb-10">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center"
              style={{ background: 'var(--accent)' }}>
              <Stethoscope size={18} color="white" />
            </div>
            <span className="font-semibold text-lg" style={{ color: 'var(--text-primary)' }}>HealthMind</span>
          </div>

          <div className="mb-8">
            <h2 className="text-4xl font-medium mb-2"
              style={{ color: 'var(--text-primary)', fontFamily: 'Cormorant Garamond, serif' }}>
              {mode === 'login' ? 'Welcome back' : 'Create account'}
            </h2>
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
              {mode === 'login'
                ? 'Sign in to access your medical knowledge base'
                : 'Join HealthMind to start querying medical literature'}
            </p>
          </div>

          {/* Tab toggle */}
          <div className="flex rounded-xl p-1 mb-8" style={{ background: 'var(--bg-tertiary)' }}>
            {['login', 'register'].map((m) => (
              <button key={m} onClick={() => { setMode(m); setError(''); }}
                className="flex-1 py-2 rounded-lg text-sm font-medium capitalize"
                style={{
                  background: mode === m ? 'white' : 'transparent',
                  color: mode === m ? 'var(--text-primary)' : 'var(--text-muted)',
                  boxShadow: mode === m ? '0 1px 6px rgba(0,0,0,0.08)' : 'none',
                }}>
                {m === 'login' ? 'Sign In' : 'Register'}
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="space-y-4">
            {mode === 'register' && (
              <Field label="Full Name" type="text" value={form.full_name} onChange={set('full_name')}
                placeholder="Dr. Jane Smith" required />
            )}
            <Field label="Email Address" type="email" value={form.email} onChange={set('email')}
              placeholder="you@hospital.org" required />
            <div>
              <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--text-secondary)' }}>
                Password
              </label>
              <div className="relative">
                <input
                  type={showPw ? 'text' : 'password'}
                  value={form.password}
                  onChange={set('password')}
                  placeholder={mode === 'register' ? 'At least 8 characters' : '••••••••'}
                  required
                  minLength={mode === 'register' ? 8 : 1}
                  className="w-full px-4 py-3 pr-11 rounded-xl text-sm border outline-none"
                  style={{
                    background: 'white',
                    border: '1px solid var(--border)',
                    color: 'var(--text-primary)',
                  }}
                />
                <button type="button" onClick={() => setShowPw(!showPw)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 p-1 rounded"
                  style={{ color: 'var(--text-muted)' }}>
                  {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {error && (
              <div className="flex items-start gap-2.5 rounded-xl px-4 py-3 text-sm animate-fade-in"
                style={{ background: '#FEF2F0', border: '1px solid #FCD5CD', color: 'var(--danger)' }}>
                <AlertCircle size={16} className="mt-0.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <button type="submit" disabled={loading}
              className="w-full flex items-center justify-center gap-2 py-3.5 rounded-xl font-medium text-sm mt-2"
              style={{
                background: loading ? 'var(--bg-tertiary)' : 'var(--accent)',
                color: loading ? 'var(--text-muted)' : 'white',
                cursor: loading ? 'not-allowed' : 'pointer',
              }}>
              {loading ? (
                <><Loader2 size={16} className="animate-spin" />Processing…</>
              ) : (
                <>{mode === 'login' ? 'Sign In' : 'Create Account'}<ArrowRight size={16} /></>
              )}
            </button>
          </form>

          <p className="text-xs text-center mt-8" style={{ color: 'var(--text-muted)' }}>
            Medical AI assistant — for professional use only.
          </p>
        </div>
      </div>
    </div>
  );
}

function Field({ label, ...props }) {
  return (
    <div>
      <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--text-secondary)' }}>
        {label}
      </label>
      <input
        {...props}
        className="w-full px-4 py-3 rounded-xl text-sm border outline-none"
        style={{ background: 'white', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
      />
    </div>
  );
}

