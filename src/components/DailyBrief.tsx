import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { formatProvider } from '../utils/timeAgo';

interface BriefContent {
  headline?: string;
  overnight?: string;
  geopolitics?: string;
  today_focus?: string;
  portfolio_position?: string;
  day_summary?: string;
  why_it_happened?: string;
  portfolio_impact?: string;
  tomorrow_outlook?: string;
  market_mood?: string;
  confidence?: number;
}

interface Brief {
  type: string;
  date: string;
  generated_at: string;
  provider: string;
  content: BriefContent;
}

const MOOD_STYLES: Record<string, { color: string; bg: string; label: string }> = {
  RISK_ON: { color: '#10b981', bg: 'rgba(16,185,129,0.08)', label: 'RISK ON' },
  RISK_OFF: { color: '#ef4444', bg: 'rgba(239,68,68,0.08)', label: 'RISK OFF' },
  CAUTIOUS: { color: '#f59e0b', bg: 'rgba(245,158,11,0.08)', label: 'FÖRSIKTIG' },
  NEUTRAL: { color: '#6b7280', bg: 'rgba(107,114,128,0.08)', label: 'NEUTRAL' },
};

export default function DailyBrief() {
  const { data, isLoading } = useQuery({
    queryKey: ['daily-brief'],
    queryFn: () => api.getLatestBrief(),
    staleTime: 300_000,
    refetchInterval: 300_000,
    retry: 1,
  });

  const brief: Brief | null = data?.brief || null;

  if (isLoading) {
    return (
      <div className="glass-panel" style={{ padding: '1.5rem', opacity: 0.6 }}>
        <div style={{ fontSize: '0.72rem', color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Laddar marknadsbrev...
        </div>
      </div>
    );
  }

  if (!brief || !brief.content?.headline || brief.provider === 'fallback') {
    return null; // Don't render if no brief available yet
  }

  const c = brief.content;
  const mood = MOOD_STYLES[c.market_mood || 'NEUTRAL'] || MOOD_STYLES.NEUTRAL;
  const isMorning = brief.type === 'morning';
  const icon = isMorning ? '☀️' : '🌙';
  const label = isMorning ? 'MORGONBREV' : 'KVÄLLSSAMMANFATTNING';

  // Format time
  const genTime = brief.generated_at
    ? new Date(brief.generated_at).toLocaleTimeString('sv-SE', { hour: '2-digit', minute: '2-digit' })
    : '';

  // Build sections based on brief type
  const sections = isMorning
    ? [
        { key: 'overnight', title: 'Natten som var', text: c.overnight },
        { key: 'geopolitics', title: 'Geopolitik', text: c.geopolitics },
        { key: 'today_focus', title: 'Dagens fokus', text: c.today_focus },
        { key: 'portfolio_position', title: 'Portföljposition', text: c.portfolio_position },
      ]
    : [
        { key: 'day_summary', title: 'Dagens marknader', text: c.day_summary },
        { key: 'why_it_happened', title: 'Varför det hände', text: c.why_it_happened },
        { key: 'portfolio_impact', title: 'Portföljpåverkan', text: c.portfolio_impact },
        { key: 'tomorrow_outlook', title: 'Imorgon', text: c.tomorrow_outlook },
      ];

  return (
    <div
      className="glass-panel animate-fade-in"
      style={{
        padding: '1.5rem',
        borderLeft: `3px solid ${mood.color}`,
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Subtle gradient overlay */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: '60px',
          background: `linear-gradient(180deg, ${mood.bg}, transparent)`,
          pointerEvents: 'none',
        }}
      />

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', position: 'relative' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontSize: '1.2rem' }}>{icon}</span>
          <span style={{
            fontSize: '0.65rem',
            fontWeight: 700,
            textTransform: 'uppercase',
            letterSpacing: '0.1em',
            color: mood.color,
          }}>
            {label}
          </span>
          <span style={{
            fontSize: '0.6rem',
            padding: '0.15rem 0.5rem',
            borderRadius: '10px',
            background: mood.bg,
            color: mood.color,
            fontWeight: 600,
          }}>
            {mood.label}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{
            fontSize: '0.6rem',
            padding: '0.1rem 0.4rem',
            borderRadius: '4px',
            background: 'rgba(102, 126, 234, 0.12)',
            color: 'rgba(102, 126, 234, 0.8)',
            fontWeight: 600,
          }}>
            {formatProvider(brief.provider)}
          </span>
          <span style={{ fontSize: '0.6rem', color: '#374151' }}>
            {genTime}
          </span>
        </div>
      </div>

      {/* Headline */}
      <h3 style={{
        fontSize: '1.05rem',
        fontWeight: 800,
        color: 'var(--text-primary)',
        marginBottom: '1rem',
        lineHeight: 1.3,
        position: 'relative',
      }}>
        {c.headline}
      </h3>

      {/* Content sections */}
      <div style={{ display: 'grid', gap: '0.75rem' }}>
        {sections.map(section => {
          if (!section.text) return null;
          return (
            <div key={section.key}>
              <div style={{
                fontSize: '0.6rem',
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                color: '#6b7280',
                marginBottom: '0.3rem',
              }}>
                {section.title}
              </div>
              <p style={{
                fontSize: '0.82rem',
                lineHeight: 1.6,
                color: 'var(--text-secondary)',
                margin: 0,
              }}>
                {section.text}
              </p>
            </div>
          );
        })}
      </div>

      {/* Confidence indicator */}
      {c.confidence !== undefined && c.confidence > 0 && (
        <div style={{
          marginTop: '1rem',
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
        }}>
          <span style={{ fontSize: '0.6rem', color: '#4b5563' }}>Konfidens:</span>
          <div style={{
            flex: 1,
            maxWidth: '100px',
            height: '3px',
            borderRadius: '2px',
            background: 'rgba(255,255,255,0.05)',
            overflow: 'hidden',
          }}>
            <div style={{
              width: `${(c.confidence || 0) * 100}%`,
              height: '100%',
              borderRadius: '2px',
              background: mood.color,
              transition: 'width 0.5s',
            }} />
          </div>
          <span style={{ fontSize: '0.6rem', color: '#4b5563' }}>
            {((c.confidence || 0) * 100).toFixed(0)}%
          </span>
        </div>
      )}
    </div>
  );
}
