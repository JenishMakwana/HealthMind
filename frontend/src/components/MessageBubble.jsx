import { useState } from 'react';
import { ChevronDown, ChevronRight, FileText, Stethoscope, User, Clock } from 'lucide-react';

export default function MessageBubble({ message }) {
  const isUser = message.role === 'user';
  const [showSources, setShowSources] = useState(false);

  const hasSources = message.sources && message.sources.length > 0;
  const hasMeta = message.meta;

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'} animate-slide-up`}>
      {/* Avatar */}
      <div className="shrink-0 w-8 h-8 rounded-full flex items-center justify-center mt-0.5"
        style={{
          background: isUser ? 'var(--accent)' : 'white',
          border: isUser ? 'none' : '1px solid var(--border)',
          boxShadow: isUser ? 'none' : '0 1px 4px rgba(0,0,0,0.06)',
        }}>
        {isUser
          ? <User size={14} color="white" />
          : <Stethoscope size={14} style={{ color: 'var(--accent)' }} />}
      </div>

      <div className={`flex flex-col max-w-[80%] ${isUser ? 'items-end' : 'items-start'}`}>
        {/* Bubble */}
        <div className="rounded-2xl px-4 py-3"
          style={{
            background: isUser ? 'var(--accent)' : 'white',
            border: isUser ? 'none' : '1px solid var(--border)',
            boxShadow: isUser ? '0 2px 12px rgba(27,122,110,0.25)' : '0 1px 6px rgba(0,0,0,0.06)',
            borderRadius: isUser ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
            color: isUser ? 'white' : 'var(--text-primary)',
          }}>
          <div className={`prose-message text-sm leading-relaxed ${isUser ? 'text-white' : ''}`}
            dangerouslySetInnerHTML={{ __html: formatMessage(message.content) }}
          />
        </div>

        {/* Meta info */}
        {hasMeta && (
          <div className="flex items-center gap-3 mt-1.5 px-1">
            {hasMeta.retrieval_ms !== undefined && (
              <span className="text-xs flex items-center gap-1" style={{ color: 'var(--text-muted)' }}>
                <Clock size={10} />
                {Math.round(hasMeta.retrieval_ms + (hasMeta.generation_ms || 0))}ms
              </span>
            )}
          </div>
        )}

        {/* Sources */}
        {hasSources && (
          <div className="mt-2 w-full max-w-full">
            <button
              onClick={() => setShowSources(!showSources)}
              className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg"
              style={{
                color: 'var(--accent)',
                background: 'var(--accent-light)',
              }}>
              <FileText size={12} />
              {message.sources.length} source{message.sources.length !== 1 ? 's' : ''} cited
              {showSources ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
            </button>

            {showSources && (
              <div className="mt-2 space-y-2 animate-fade-in">
                {message.sources.map((src, i) => (
                  <SourceCard key={i} source={src} />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Timestamp */}
        <p className="text-xs mt-1 px-1" style={{ color: 'var(--text-muted)' }}>
          {new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </p>
      </div>
    </div>
  );
}

function SourceCard({ source }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="rounded-xl p-3 text-xs"
      style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <p className="font-medium truncate" style={{ color: 'var(--text-primary)' }}>
            {source.title || source.filename}
          </p>
          <div className="flex items-center gap-2 mt-0.5">
            {source.page_number && (
              <span style={{ color: 'var(--text-muted)' }}>Page {source.page_number}</span>
            )}
          </div>
        </div>
        <button onClick={() => setExpanded(!expanded)}
          className="shrink-0 p-1 rounded-lg"
          style={{ color: 'var(--text-muted)' }}>
          {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        </button>
      </div>
      {expanded && source.text && (
        <p className="mt-2 pt-2 leading-relaxed italic"
          style={{ borderTop: '1px solid var(--border)', color: 'var(--text-secondary)' }}>
          "{source.text.length > 300 ? source.text.slice(0, 300) + '…' : source.text}"
        </p>
      )}
    </div>
  );
}

function formatMessage(text) {
  if (!text) return '';
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br/>')
    .replace(/^/, '<p>').replace(/$/, '</p>');
}
