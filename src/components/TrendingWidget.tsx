import { useState, useEffect } from 'react';
import { Flame, ArrowUp, ArrowDown, Minus } from 'lucide-react';

interface TrendingEntity {
  symbol: string;
  mentions: number;
  sentiment_avg: number;
  score: number;
}

export default function TrendingWidget() {
  const [trending, setTrending] = useState<TrendingEntity[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('http://localhost:8000/api/trending')
      .then(r => r.json())
      .then(data => {
        setTrending(data.trending || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const getSentimentIcon = (score: number) => {
    if (score > 0.15) return <ArrowUp size={12} style={{ color: '#10b981' }} />;
    if (score < -0.15) return <ArrowDown size={12} style={{ color: '#ef4444' }} />;
    return <Minus size={12} style={{ color: 'var(--text-tertiary)' }} />;
  };

  const getSentimentColor = (score: number) => {
    if (score > 0.3) return '#10b981';
    if (score > 0.1) return '#34d399';
    if (score < -0.3) return '#ef4444';
    if (score < -0.1) return '#f87171';
    return 'var(--text-secondary)';
  };

  if (loading) {
    return (
      <div className="glass-panel" style={{ padding: '1rem' }}>
        <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <Flame size={16} style={{ color: '#f59e0b' }} /> Trending Nu
        </h4>
        <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>Laddar...</div>
      </div>
    );
  }

  if (trending.length === 0) {
    return (
      <div className="glass-panel" style={{ padding: '1rem' }}>
        <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <Flame size={16} style={{ color: '#f59e0b' }} /> Trending Nu
        </h4>
        <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>
          Ingen trending-data tillgänglig. Kontrollera MARKETAUX_API_KEY.
        </div>
      </div>
    );
  }

  const maxMentions = Math.max(...trending.map(t => t.mentions));

  return (
    <div className="glass-panel" style={{ padding: '1rem' }}>
      <h4 style={{ margin: '0 0 0.75rem', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
        <Flame size={16} style={{ color: '#f59e0b' }} />
        Trending Nu
        <span style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)', fontWeight: 400, marginLeft: 'auto' }}>
          Marketaux • Idag
        </span>
      </h4>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
        {trending.slice(0, 10).map((entity, i) => (
          <div key={entity.symbol} style={{
            display: 'flex', alignItems: 'center', gap: '0.5rem',
            padding: '0.35rem 0.5rem', borderRadius: '6px',
            background: i < 3 ? 'rgba(245, 158, 11, 0.06)' : 'transparent',
            border: i < 3 ? '1px solid rgba(245, 158, 11, 0.1)' : '1px solid transparent',
          }}>
            {/* Rank */}
            <span style={{
              fontSize: '0.65rem', fontWeight: 700, width: '16px', textAlign: 'center',
              color: i < 3 ? '#f59e0b' : 'var(--text-tertiary)',
            }}>
              {i + 1}
            </span>

            {/* Symbol */}
            <span style={{
              fontSize: '0.8rem', fontWeight: 600, width: '55px',
              color: 'var(--text-primary)', fontFamily: 'monospace',
            }}>
              {entity.symbol}
            </span>

            {/* Bar */}
            <div style={{ flex: 1, position: 'relative', height: '6px', borderRadius: '3px', background: 'rgba(255,255,255,0.05)' }}>
              <div style={{
                height: '100%', borderRadius: '3px',
                width: `${(entity.mentions / maxMentions) * 100}%`,
                background: `linear-gradient(90deg, ${getSentimentColor(entity.sentiment_avg)}, ${getSentimentColor(entity.sentiment_avg)}88)`,
                transition: 'width 0.5s ease',
              }} />
            </div>

            {/* Mentions */}
            <span style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)', width: '30px', textAlign: 'right' }}>
              {entity.mentions}
            </span>

            {/* Sentiment */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.15rem', width: '45px' }}>
              {getSentimentIcon(entity.sentiment_avg)}
              <span style={{
                fontSize: '0.65rem', fontWeight: 600,
                color: getSentimentColor(entity.sentiment_avg),
              }}>
                {entity.sentiment_avg > 0 ? '+' : ''}{(entity.sentiment_avg * 100).toFixed(0)}%
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
