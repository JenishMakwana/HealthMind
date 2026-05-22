import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Send, Paperclip, Mic, MicOff, Loader2, FileText,
  Menu, Sparkles, Stethoscope, PanelRightOpen, PanelRightClose
} from 'lucide-react';
import { api } from '../api/client';
import MessageBubble from './MessageBubble';
import DocumentPanel from './DocumentPanel';

function audioBufferToWavBlob(audioBuffer) {
  const numberOfChannels = audioBuffer.numberOfChannels;
  const sampleRate = audioBuffer.sampleRate;
  const bitDepth = 16;
  const blockAlign = numberOfChannels * (bitDepth / 8);
  const byteRate = sampleRate * blockAlign;
  const dataSize = audioBuffer.length * blockAlign;
  const buffer = new ArrayBuffer(44 + dataSize);
  const view = new DataView(buffer);

  writeAscii(view, 0, 'RIFF');
  view.setUint32(4, 36 + dataSize, true);
  writeAscii(view, 8, 'WAVE');
  writeAscii(view, 12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, numberOfChannels, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, byteRate, true);
  view.setUint16(32, blockAlign, true);
  view.setUint16(34, bitDepth, true);
  writeAscii(view, 36, 'data');
  view.setUint32(40, dataSize, true);

  const channels = [];
  for (let channel = 0; channel < numberOfChannels; channel += 1) {
    channels.push(audioBuffer.getChannelData(channel));
  }

  let offset = 44;
  for (let i = 0; i < audioBuffer.length; i += 1) {
    for (let channel = 0; channel < numberOfChannels; channel += 1) {
      const sample = Math.max(-1, Math.min(1, channels[channel][i]));
      view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
      offset += 2;
    }
  }

  return new Blob([buffer], { type: 'audio/wav' });
}

function writeAscii(view, offset, text) {
  for (let i = 0; i < text.length; i += 1) {
    view.setUint8(offset + i, text.charCodeAt(i));
  }
}

async function convertRecordedBlobToWav(blob) {
  const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextCtor) throw new Error('This browser cannot convert microphone audio for transcription.');
  const audioContext = new AudioContextCtor();
  try {
    const decoded = await audioContext.decodeAudioData(await blob.arrayBuffer());
    return audioBufferToWavBlob(decoded);
  } finally {
    await audioContext.close();
  }
}

export default function ChatView({
  conversation,
  onTitleChange,
  sidebarOpen,
  onToggleSidebar,
  onCreateConversation,
}) {
  const [messages, setMessages] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingMsgs, setLoadingMsgs] = useState(true);
  const [showDocs, setShowDocs] = useState(false);
  const [uploadingDocs, setUploadingDocs] = useState(false);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [composerError, setComposerError] = useState('');
  const bottomRef = useRef();
  const textareaRef = useRef();
  const uploadInputRef = useRef();
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);

  useEffect(() => {
    if (!conversation) {
      setMessages([]);
      setDocuments([]);
      setLoadingMsgs(false);
      return;
    }

    setLoadingMsgs(true);
    setMessages([]);
    setComposerError('');
    Promise.all([
      api.getMessages(conversation.id),
      api.listDocuments(conversation.id),
    ])
      .then(([msgs, docs]) => {
        setMessages(msgs);
        setDocuments(docs);
      })
      .catch(console.error)
      .finally(() => setLoadingMsgs(false));
  }, [conversation?.id]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const resizeTextarea = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 160) + 'px';
  }, []);

  useEffect(() => {
    resizeTextarea();
  }, [input, resizeTextarea]);

  const refreshDocuments = useCallback(async () => {
    if (!conversation?.id) return;
    const updated = await api.listDocuments(conversation.id);
    setDocuments(updated);
  }, [conversation?.id]);

  useEffect(() => {
    const hasProcessing = documents.some((d) => d.status === 'processing');
    if (!hasProcessing) return;

    const interval = setInterval(() => {
      refreshDocuments();
    }, 3000);

    return () => clearInterval(interval);
  }, [documents, refreshDocuments]);

  const send = async () => {
    const q = input.trim();
    if (!q || loading || !conversation) return;
    setComposerError('');
    setInput('');
    setLoading(true);

    const tempUser = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: q,
      created_at: new Date().toISOString(),
      conversation_id: conversation.id,
    };
    setMessages((prev) => [...prev, tempUser]);

    try {
      const res = await api.query({ query: q, conversation_id: conversation.id, top_k: 5 });
      const assistantMsg = {
        id: res.message_id,
        role: 'assistant',
        content: res.answer,
        sources: res.sources,
        created_at: new Date().toISOString(),
        conversation_id: conversation.id,
        meta: {
          model: res.model,
          retrieval_ms: res.retrieval_ms,
          rerank_ms: res.rerank_ms,
          generation_ms: res.generation_ms,
          retrieval_strategy: res.retrieval_strategy,
        },
      };
      setMessages((prev) => [...prev, assistantMsg]);
      if (messages.length < 2 && onTitleChange) {
        setTimeout(() => onTitleChange(conversation.id), 500);
      }
    } catch (err) {
      setMessages((prev) => [...prev, {
        id: `err-${Date.now()}`,
        role: 'assistant',
        content: `Error: ${err.message}`,
        created_at: new Date().toISOString(),
        conversation_id: conversation.id,
      }]);
    } finally {
      setLoading(false);
    }
  };

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const handleFileUpload = async (files) => {
    if (!files?.length || !conversation?.id || uploadingDocs) return;
    setComposerError('');
    setUploadingDocs(true);
    try {
      const fd = new FormData();
      fd.append('conversation_id', conversation.id);
      Array.from(files).forEach((file) => fd.append('files', file));
      const res = await api.uploadDocuments(fd);
      if (res?.rejected_files?.length > 0) {
        setComposerError(`Warning: Some files were rejected (non-medical): ${res.rejected_files.join(', ')}`);
      }
      await refreshDocuments();
      setShowDocs(true);
    } catch (err) {
      setComposerError(err.message);
    } finally {
      setUploadingDocs(false);
      if (uploadInputRef.current) uploadInputRef.current.value = '';
    }
  };

  const stopRecording = useCallback(() => {
    mediaRecorderRef.current?.stop();
  }, []);

  const startRecording = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setComposerError('Microphone recording is not supported in this browser.');
      return;
    }

    setComposerError('');

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : '';
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      audioChunksRef.current = [];
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) audioChunksRef.current.push(event.data);
      };

      recorder.onstop = async () => {
        setRecording(false);
        stream.getTracks().forEach((track) => track.stop());
        if (!audioChunksRef.current.length) return;

        setTranscribing(true);
        try {
          const wavBlob = await convertRecordedBlobToWav(new Blob(audioChunksRef.current, {
            type: recorder.mimeType || 'audio/webm',
          }));
          const fd = new FormData();
          fd.append('file', wavBlob, 'recording.wav');
          const res = await api.transcribeAudio(fd);
          setInput((prev) => `${prev}${prev.trim() ? ' ' : ''}${res.text}`.trimStart());
        } catch (err) {
          setComposerError(err.message);
        } finally {
          setTranscribing(false);
          audioChunksRef.current = [];
          mediaRecorderRef.current = null;
        }
      };

      recorder.start();
      setRecording(true);
    } catch (err) {
      setComposerError(err.message || 'Unable to access your microphone.');
    }
  }, []);

  const toggleRecording = useCallback(() => {
    if (recording) stopRecording();
    else startRecording();
  }, [recording, startRecording, stopRecording]);

  return (
    <div className="flex-1 flex overflow-hidden min-h-0 min-w-0">
      <div className="flex-1 flex flex-col min-h-0 min-w-0">
        <div className="chat-topbar">
          <button className="icon-button" onClick={onToggleSidebar} title={sidebarOpen ? 'Hide sidebar' : 'Show sidebar'}>
            <Menu size={16} />
          </button>

          <div className="chat-topbar-copy">
            <h1>{conversation?.title || 'Select a conversation'}</h1>
            <p>
              {conversation
                ? `${documents.length} document${documents.length !== 1 ? 's' : ''} attached`
                : 'Choose an existing chat or start a new one from the sidebar'}
            </p>
          </div>

          {conversation && (
            <>
              <button className="soft-chip" onClick={() => setShowDocs((prev) => !prev)}>
                {showDocs ? <PanelRightClose size={14} /> : <PanelRightOpen size={14} />}
                Knowledge Base
              </button>
              <div className="topbar-brand hide-mobile">HealthMind</div>
            </>
          )}
        </div>

        <div className="flex-1 overflow-y-auto min-h-0 px-4 sm:px-6">
          {!conversation ? (
            <WelcomeState onCreateConversation={onCreateConversation} />
          ) : loadingMsgs ? (
            <div className="flex items-center justify-center h-full">
              <Loader2 size={24} className="animate-spin" style={{ color: 'var(--accent)' }} />
            </div>
          ) : messages.length === 0 ? (
            <EmptyConversation documents={documents} />
          ) : (
            <div className="max-w-3xl mx-auto py-6 space-y-6">
              {messages.map((msg) => (
                <MessageBubble key={msg.id} message={msg} />
              ))}
              {loading && <TypingIndicator />}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        {conversation && (
          <div className="chat-composer-shell">
            <div className="max-w-3xl mx-auto w-full">
              {composerError && (
                <div className="composer-error">
                  {composerError}
                </div>
              )}

              <div className="chat-composer">
                <input
                  ref={uploadInputRef}
                  type="file"
                  multiple
                  accept=".pdf,.docx,.txt"
                  className="hidden"
                  onChange={(e) => handleFileUpload(e.target.files)}
                />

                <button
                  type="button"
                  className="icon-button"
                  onClick={() => uploadInputRef.current?.click()}
                  disabled={uploadingDocs || loading}
                  title="Upload documents"
                >
                  {uploadingDocs ? <Loader2 size={15} className="animate-spin" /> : <Paperclip size={15} />}
                </button>

                <textarea
                  ref={textareaRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={onKeyDown}
                  placeholder={
                    documents.length === 0
                      ? 'Upload documents first, then ask a question...'
                      : 'Ask a question about your medical knowledge base...'
                  }
                  rows={1}
                  disabled={loading}
                  className="composer-textarea"
                />

                <button
                  type="button"
                  className={`icon-button ${recording ? 'danger' : ''}`}
                  onClick={toggleRecording}
                  disabled={transcribing || loading}
                  title={recording ? 'Stop recording' : 'Record audio'}
                >
                  {transcribing ? <Loader2 size={15} className="animate-spin" /> : recording ? <MicOff size={15} /> : <Mic size={15} />}
                </button>

                <button
                  onClick={send}
                  disabled={!input.trim() || loading}
                  className="send-button"
                >
                  {loading ? <Loader2 size={16} className="animate-spin" /> : <Send size={15} />}
                </button>
              </div>

              <p className="composer-note">
                {recording
                  ? 'Recording audio... press the mic again to stop.'
                  : transcribing
                    ? 'Transcribing audio...'
                    : 'HealthMind can make mistakes. Verify important medical details.'}
              </p>
            </div>
          </div>
        )}
      </div>

      {conversation && showDocs && (
        <div className="w-[320px] shrink-0 border-l overflow-hidden bg-white" style={{ borderColor: 'var(--border)' }}>
          <DocumentPanel
            conversationId={conversation.id}
            documents={documents}
            onDocumentsChange={setDocuments}
          />
        </div>
      )}
    </div>
  );
}

function WelcomeState({ onCreateConversation }) {
  return (
    <div className="h-full flex items-center justify-center px-6">
      <div className="welcome-card">
        <div className="welcome-badge">
          <Stethoscope size={18} />
        </div>
        <p className="welcome-kicker">Premium Medical AI</p>
        <h2>HealthMind</h2>
        <p className="welcome-copy">
          Upload clinical documents, ask grounded questions, and work through answers with a calm, premium light interface.
        </p>
        <div className="welcome-actions">
          <button className="welcome-primary" onClick={onCreateConversation}>
            <Sparkles size={15} />
            Start New Chat
          </button>
        </div>
      </div>
    </div>
  );
}

function EmptyConversation({ documents }) {
  return (
    <div className="max-w-3xl mx-auto py-10">
      <div className="empty-state-card">
        <div className="welcome-badge">
          <Sparkles size={18} />
        </div>
        <h3>{documents.length > 0 ? 'Ready when you are' : 'Upload documents to begin'}</h3>
        <p>
          {documents.length > 0
            ? `${documents.length} document${documents.length !== 1 ? 's' : ''} indexed and ready for retrieval.`
            : 'Use the paperclip button below or open the knowledge base panel to add PDF, DOCX, or TXT files.'}
        </p>
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex gap-3">
      <div className="w-9 h-9 rounded-2xl flex items-center justify-center bg-white border" style={{ borderColor: 'var(--border)' }}>
        <Stethoscope size={14} style={{ color: 'var(--accent)' }} />
      </div>
      <div className="typing-card">
        <span className="typing-dot" />
        <span className="typing-dot" />
        <span className="typing-dot" />
      </div>
    </div>
  );
}
