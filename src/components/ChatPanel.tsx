import { useState, useRef, useEffect, useCallback } from 'react';
import { MessageCircle, X, Send, Bot, User, Sparkles, Minimize2 } from 'lucide-react';
import { API_BASE } from '../api/client';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  provider?: string;
}

export default function ChatPanel() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: 'Hej! 👋 Jag är **Aether AI-assistenten**. Jag kan svara på frågor om marknadsläget, tillgångar, AI-scores, regimer och historiska bedömningar.\n\nFråga mig vad som helst — t.ex:\n- *"Hur ser det ut för Bitcoin just nu?"*\n- *"Vilka sektorer är starkast?"*\n- *"Vad är aktuell marknadsregim?"*',
      timestamp: new Date(),
    }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [pulseAnimation, setPulseAnimation] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Focus input when opening
  useEffect(() => {
    if (isOpen) {
      setPulseAnimation(false);
      setTimeout(() => inputRef.current?.focus(), 300);
    }
  }, [isOpen]);

  const sendMessage = useCallback(async (directMessage?: string) => {
    const trimmed = (directMessage || input).trim();
    if (!trimmed || isLoading) return;

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: trimmed,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);

    try {
      // Build history for context
      const history = messages
        .filter(m => m.id !== 'welcome')
        .map(m => ({ role: m.role, content: m.content }));

      const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: trimmed,
          history: history.slice(-6),
        }),
      });

      const data = await res.json();

      const aiMsg: ChatMessage = {
        id: `a-${Date.now()}`,
        role: 'assistant',
        content: data.response || 'Kunde inte generera svar.',
        timestamp: new Date(),
        provider: data.provider,
      };

      setMessages(prev => [...prev, aiMsg]);
    } catch {
      setMessages(prev => [...prev, {
        id: `e-${Date.now()}`,
        role: 'assistant',
        content: '⚠️ Kunde inte nå servern. Kontrollera att backend körs.',
        timestamp: new Date(),
      }]);
    } finally {
      setIsLoading(false);
    }
  }, [input, isLoading, messages]);

  // K2 FIX: Safe markdown rendering — no dangerouslySetInnerHTML, no XSS risk
  const renderInlineMarkdown = (text: string): React.ReactNode[] => {
    // Split on bold, italic, and code patterns, returning React elements
    const parts: React.ReactNode[] = [];
    // Process bold **text**, italic *text*, and code `text`
    const regex = /(\*\*.*?\*\*|\*.*?\*|`.*?`)/g;
    let lastIndex = 0;
    let match;
    let partKey = 0;

    while ((match = regex.exec(text)) !== null) {
      // Add preceding plain text
      if (match.index > lastIndex) {
        parts.push(<span key={partKey++}>{text.slice(lastIndex, match.index)}</span>);
      }

      const token = match[0];
      if (token.startsWith('**') && token.endsWith('**')) {
        parts.push(<strong key={partKey++}>{token.slice(2, -2)}</strong>);
      } else if (token.startsWith('*') && token.endsWith('*')) {
        parts.push(<em key={partKey++}>{token.slice(1, -1)}</em>);
      } else if (token.startsWith('`') && token.endsWith('`')) {
        parts.push(
          <code key={partKey++} style={{ background: 'rgba(0,255,200,0.1)', padding: '1px 4px', borderRadius: '3px', fontSize: '0.85em' }}>
            {token.slice(1, -1)}
          </code>
        );
      }
      lastIndex = match.index + token.length;
    }

    // Remaining plain text
    if (lastIndex < text.length) {
      parts.push(<span key={partKey++}>{text.slice(lastIndex)}</span>);
    }

    return parts.length > 0 ? parts : [<span key={0}>{text}</span>];
  };

  const renderMarkdown = (text: string) => {
    const lines = text.split('\n');
    return lines.map((line, i) => {
      const isList = line.startsWith('- ');
      const content = isList ? line.slice(2) : line;

      return (
        <span key={i}>
          {isList && <span style={{ color: '#00ffc8' }}>• </span>}
          {renderInlineMarkdown(content)}
          {i < lines.length - 1 && <br />}
        </span>
      );
    });
  };

  return (
    <>
      {/* Floating Chat Bubble */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          style={{
            position: 'fixed',
            bottom: 24,
            right: 24,
            width: 60,
            height: 60,
            borderRadius: '50%',
            background: 'linear-gradient(135deg, #00ffc8 0%, #00b4d8 50%, #7b2ff7 100%)',
            border: 'none',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 4px 20px rgba(0, 255, 200, 0.3), 0 0 40px rgba(0, 255, 200, 0.1)',
            zIndex: 9999,
            transition: 'transform 0.2s, box-shadow 0.2s',
            animation: pulseAnimation ? 'chatPulse 2s infinite' : 'none',
          }}
          onMouseEnter={e => {
            (e.target as HTMLElement).style.transform = 'scale(1.1)';
            (e.target as HTMLElement).style.boxShadow = '0 6px 30px rgba(0, 255, 200, 0.5), 0 0 60px rgba(0, 255, 200, 0.15)';
          }}
          onMouseLeave={e => {
            (e.target as HTMLElement).style.transform = 'scale(1)';
            (e.target as HTMLElement).style.boxShadow = '0 4px 20px rgba(0, 255, 200, 0.3), 0 0 40px rgba(0, 255, 200, 0.1)';
          }}
          title="Fråga Aether AI"
        >
          <MessageCircle size={26} color="#0a0f1c" />
        </button>
      )}

      {/* Chat Panel */}
      {isOpen && (
        <div
          style={{
            position: 'fixed',
            bottom: 24,
            right: 24,
            width: 420,
            height: 580,
            borderRadius: 16,
            background: 'rgba(10, 15, 28, 0.92)',
            backdropFilter: 'blur(24px)',
            border: '1px solid rgba(0, 255, 200, 0.15)',
            boxShadow: '0 8px 40px rgba(0, 0, 0, 0.6), 0 0 80px rgba(0, 255, 200, 0.05)',
            zIndex: 9999,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            animation: 'chatSlideUp 0.3s ease-out',
          }}
        >
          {/* Header */}
          <div
            style={{
              padding: '14px 16px',
              borderBottom: '1px solid rgba(255,255,255,0.06)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              background: 'linear-gradient(135deg, rgba(0, 255, 200, 0.05) 0%, rgba(123, 47, 247, 0.05) 100%)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: '50%',
                  background: 'linear-gradient(135deg, #00ffc8, #7b2ff7)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Sparkles size={18} color="#0a0f1c" />
              </div>
              <div>
                <div style={{ color: '#fff', fontWeight: 600, fontSize: 14 }}>Aether AI Chat</div>
                <div style={{ color: '#00ffc8', fontSize: 11, display: 'flex', alignItems: 'center', gap: 4 }}>
                  <span style={{
                    width: 6, height: 6, borderRadius: '50%', background: '#00ffc8',
                    display: 'inline-block', animation: 'chatOnline 2s infinite',
                  }} />
                  Online — Gemini Flash
                </div>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 4 }}>
              <button
                onClick={() => setIsOpen(false)}
                style={{
                  background: 'rgba(255,255,255,0.05)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: 8,
                  width: 32, height: 32,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  cursor: 'pointer', color: '#8899aa',
                  transition: 'all 0.2s',
                }}
                onMouseEnter={e => { (e.currentTarget).style.background = 'rgba(255,255,255,0.1)'; (e.currentTarget).style.color = '#fff'; }}
                onMouseLeave={e => { (e.currentTarget).style.background = 'rgba(255,255,255,0.05)'; (e.currentTarget).style.color = '#8899aa'; }}
                title="Minimera"
              >
                <Minimize2 size={14} />
              </button>
              <button
                onClick={() => setIsOpen(false)}
                style={{
                  background: 'rgba(255,255,255,0.05)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: 8,
                  width: 32, height: 32,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  cursor: 'pointer', color: '#8899aa',
                  transition: 'all 0.2s',
                }}
                onMouseEnter={e => { (e.currentTarget).style.background = 'rgba(255,60,60,0.15)'; (e.currentTarget).style.color = '#ff6b6b'; }}
                onMouseLeave={e => { (e.currentTarget).style.background = 'rgba(255,255,255,0.05)'; (e.currentTarget).style.color = '#8899aa'; }}
                title="Stäng"
              >
                <X size={14} />
              </button>
            </div>
          </div>

          {/* Messages */}
          <div
            style={{
              flex: 1,
              overflowY: 'auto',
              padding: '12px 14px',
              display: 'flex',
              flexDirection: 'column',
              gap: 12,
              scrollbarWidth: 'thin',
              scrollbarColor: 'rgba(0,255,200,0.2) transparent',
            }}
          >
            {messages.map(msg => (
              <div
                key={msg.id}
                style={{
                  display: 'flex',
                  justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                  gap: 8,
                  animation: 'chatMsgIn 0.3s ease-out',
                }}
              >
                {msg.role === 'assistant' && (
                  <div
                    style={{
                      width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
                      background: 'linear-gradient(135deg, rgba(0,255,200,0.2), rgba(123,47,247,0.2))',
                      border: '1px solid rgba(0,255,200,0.2)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      marginTop: 2,
                    }}
                  >
                    <Bot size={14} color="#00ffc8" />
                  </div>
                )}
                <div
                  style={{
                    maxWidth: '80%',
                    padding: '10px 14px',
                    borderRadius: msg.role === 'user' ? '14px 14px 4px 14px' : '14px 14px 14px 4px',
                    background: msg.role === 'user'
                      ? 'linear-gradient(135deg, rgba(0, 255, 200, 0.15), rgba(0, 180, 216, 0.1))'
                      : 'rgba(255, 255, 255, 0.04)',
                    border: `1px solid ${msg.role === 'user' ? 'rgba(0, 255, 200, 0.2)' : 'rgba(255, 255, 255, 0.06)'}`,
                    color: '#e0e4ea',
                    fontSize: 13,
                    lineHeight: 1.55,
                  }}
                >
                  {renderMarkdown(msg.content)}
                  {msg.provider && (
                    <div style={{ fontSize: 10, color: '#556', marginTop: 6, textAlign: 'right' }}>
                      {msg.provider}
                    </div>
                  )}
                </div>
                {msg.role === 'user' && (
                  <div
                    style={{
                      width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
                      background: 'rgba(0, 180, 216, 0.15)',
                      border: '1px solid rgba(0, 180, 216, 0.2)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      marginTop: 2,
                    }}
                  >
                    <User size={14} color="#00b4d8" />
                  </div>
                )}
              </div>
            ))}

            {/* Typing indicator */}
            {isLoading && (
              <div style={{ display: 'flex', gap: 8, animation: 'chatMsgIn 0.3s ease-out' }}>
                <div
                  style={{
                    width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
                    background: 'linear-gradient(135deg, rgba(0,255,200,0.2), rgba(123,47,247,0.2))',
                    border: '1px solid rgba(0,255,200,0.2)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}
                >
                  <Bot size={14} color="#00ffc8" />
                </div>
                <div
                  style={{
                    padding: '12px 18px',
                    borderRadius: '14px 14px 14px 4px',
                    background: 'rgba(255, 255, 255, 0.04)',
                    border: '1px solid rgba(255, 255, 255, 0.06)',
                    display: 'flex', gap: 6, alignItems: 'center',
                  }}
                >
                  <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#00ffc8', animation: 'chatDot1 1.4s infinite' }} />
                  <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#00ffc8', animation: 'chatDot2 1.4s infinite' }} />
                  <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#00ffc8', animation: 'chatDot3 1.4s infinite' }} />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Quick Suggestions (only when few messages) */}
          {messages.length <= 2 && !isLoading && (
            <div style={{ padding: '0 14px 8px', display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {['Marknadsläge?', 'Starkaste tillgångar?', 'Aktuell regim?', 'Sektorrotation?'].map(q => (
                <button
                  key={q}
                  onClick={() => sendMessage(q)}
                  style={{
                    padding: '5px 10px', fontSize: 11, borderRadius: 8,
                    background: 'rgba(0,255,200,0.05)', border: '1px solid rgba(0,255,200,0.15)',
                    color: '#00ffc8', cursor: 'pointer', transition: 'all 0.2s',
                  }}
                  onMouseEnter={e => { (e.currentTarget).style.background = 'rgba(0,255,200,0.12)'; }}
                  onMouseLeave={e => { (e.currentTarget).style.background = 'rgba(0,255,200,0.05)'; }}
                >
                  {q}
                </button>
              ))}
            </div>
          )}

          {/* Input */}
          <div
            style={{
              padding: '10px 14px',
              borderTop: '1px solid rgba(255,255,255,0.06)',
              display: 'flex',
              gap: 8,
              background: 'rgba(0, 0, 0, 0.2)',
            }}
          >
            <input
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } }}
              placeholder="Fråga Aether AI..."
              disabled={isLoading}
              style={{
                flex: 1,
                padding: '10px 14px',
                borderRadius: 10,
                border: '1px solid rgba(255,255,255,0.1)',
                background: 'rgba(255,255,255,0.04)',
                color: '#e0e4ea',
                fontSize: 13,
                outline: 'none',
                transition: 'border-color 0.2s',
              }}
              onFocus={e => { e.target.style.borderColor = 'rgba(0, 255, 200, 0.3)'; }}
              onBlur={e => { e.target.style.borderColor = 'rgba(255,255,255,0.1)'; }}
            />
            <button
              onClick={() => sendMessage()}
              disabled={isLoading || !input.trim()}
              style={{
                width: 40, height: 40, borderRadius: 10,
                background: input.trim()
                  ? 'linear-gradient(135deg, #00ffc8, #00b4d8)'
                  : 'rgba(255,255,255,0.05)',
                border: 'none',
                cursor: input.trim() ? 'pointer' : 'default',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                transition: 'all 0.2s',
                opacity: input.trim() ? 1 : 0.4,
              }}
            >
              <Send size={16} color={input.trim() ? '#0a0f1c' : '#556'} />
            </button>
          </div>
        </div>
      )}

      {/* CSS Animations */}
      <style>{`
        @keyframes chatPulse {
          0%, 100% { box-shadow: 0 4px 20px rgba(0, 255, 200, 0.3), 0 0 40px rgba(0, 255, 200, 0.1); }
          50% { box-shadow: 0 4px 30px rgba(0, 255, 200, 0.5), 0 0 60px rgba(0, 255, 200, 0.2); }
        }
        @keyframes chatSlideUp {
          from { opacity: 0; transform: translateY(20px) scale(0.95); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }
        @keyframes chatMsgIn {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes chatOnline {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
        @keyframes chatDot1 {
          0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
          40% { opacity: 1; transform: scale(1); }
        }
        @keyframes chatDot2 {
          0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
          50% { opacity: 1; transform: scale(1); }
        }
        @keyframes chatDot3 {
          0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
          60% { opacity: 1; transform: scale(1); }
        }
      `}</style>
    </>
  );
}
