import { useState, useEffect } from 'react';
import { Crosshair, Target, TrendingUp, TrendingDown, Star } from 'lucide-react';
import { api, type APITradeSignal } from '../api/client';

interface TradeSignalPanelProps {
  assetId: string;
}

export default function TradeSignalPanel({ assetId }: TradeSignalPanelProps) {
  const [signal, setSignal] = useState<APITradeSignal | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchSignals = async () => {
      try {
        const data = await api.getSignals();
        setSignal(data.signals[assetId] || null);
      } catch {
        setSignal(null);
      }
      setLoading(false);
    };
    fetchSignals();
  }, [assetId]);

  if (loading) return null;
  if (!signal || signal.direction === 'none') return null;

  const isNeutral = signal.direction === 'neutral';
  const isLong = signal.direction === 'long';

  const dirColor = isNeutral ? 'var(--text-tertiary)' : isLong ? 'var(--score-positive)' : 'var(--score-negative)';
  const dirLabel = isNeutral ? 'AVVAKTA' : isLong ? '🟢 LONG (KÖP)' : '🔴 SHORT (SÄLJ)';
  const stars = signal.quality?.stars || 0;

  if (isNeutral) {
    return (
      <div className="glass-panel" style={{
        padding: '1.25rem', marginTop: '1.5rem',
        background: 'rgba(255,255,255,0.02)', borderLeft: `3px solid var(--text-tertiary)`,
      }}>
        <div className="flex items-center gap-2" style={{ marginBottom: '0.5rem' }}>
          <Crosshair size={18} color="var(--text-tertiary)" />
          <h4 style={{ margin: 0, color: 'var(--text-tertiary)' }}>Trade Signal: AVVAKTA</h4>
        </div>
        {signal.key_levels && (
          <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Stöd: <strong>${signal.key_levels.support?.toLocaleString()}</strong> • 
            Motstånd: <strong>${signal.key_levels.resistance?.toLocaleString()}</strong>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="glass-panel" style={{
      padding: '1.25rem', marginTop: '1.5rem',
      background: isLong ? 'rgba(0,200,81,0.04)' : 'rgba(255,71,87,0.04)',
      borderLeft: `3px solid ${dirColor}`,
    }}>
      {/* Header */}
      <div className="flex justify-between items-center" style={{ marginBottom: '1rem' }}>
        <div className="flex items-center gap-2">
          {isLong ? <TrendingUp size={20} color={dirColor} /> : <TrendingDown size={20} color={dirColor} />}
          <h4 style={{ margin: 0, color: dirColor }}>{dirLabel}</h4>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>
            {signal.strength}
          </span>
        </div>
        <div className="flex items-center gap-1">
          {[...Array(5)].map((_, i) => (
            <Star key={i} size={14} fill={i < stars ? '#ffd93d' : 'transparent'} color={i < stars ? '#ffd93d' : '#444'} />
          ))}
          <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginLeft: '0.25rem' }}>
            {signal.quality?.label}
          </span>
        </div>
      </div>

      {/* Levels Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.75rem', marginBottom: '1rem' }}>
        {signal.entry && (
          <div style={{ padding: '0.75rem', background: 'rgba(255,255,255,0.03)', borderRadius: '8px' }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', marginBottom: '0.25rem' }}>ENTRY</div>
            <div style={{ fontSize: '1.1rem', fontWeight: 700 }}>${signal.entry.primary.toLocaleString()}</div>
            <div style={{ fontSize: '0.7rem', color: 'var(--accent-cyan)' }}>
              Ideal: ${signal.entry.ideal.toLocaleString()}
            </div>
          </div>
        )}
        {signal.stop_loss && (
          <div style={{ padding: '0.75rem', background: 'rgba(255,71,87,0.06)', borderRadius: '8px' }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--score-negative)', marginBottom: '0.25rem' }}>STOP-LOSS</div>
            <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--score-negative)' }}>
              ${signal.stop_loss.price.toLocaleString()}
            </div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>
              {signal.stop_loss.type} ({signal.stop_loss.pct_from_entry.toFixed(1)}%)
            </div>
          </div>
        )}
        {signal.risk_reward && (
          <div style={{ padding: '0.75rem', background: 'rgba(255,255,255,0.03)', borderRadius: '8px' }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', marginBottom: '0.25rem' }}>R:R RATIO</div>
            <div style={{ fontSize: '1.1rem', fontWeight: 700, color: signal.risk_reward.ratio >= 2 ? 'var(--score-positive)' : 'var(--text-secondary)' }}>
              {signal.risk_reward.ratio.toFixed(1)}x
            </div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>{signal.risk_reward.label}</div>
          </div>
        )}
      </div>

      {/* Targets */}
      {signal.targets && signal.targets.length > 0 && (
        <div style={{ marginBottom: '0.75rem' }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', marginBottom: '0.5rem' }}>TARGETS</div>
          <div className="flex gap-2" style={{ flexWrap: 'wrap' }}>
            {signal.targets.map((t, i) => (
              <span key={i} style={{
                padding: '0.25rem 0.6rem', borderRadius: '6px', fontSize: '0.78rem',
                background: 'rgba(0, 242, 254, 0.08)', color: 'var(--accent-cyan)',
              }}>
                <Target size={12} style={{ display: 'inline', marginRight: '0.25rem', verticalAlign: 'middle' }} />
                ${t.price.toLocaleString()} (+{t.pct_from_entry.toFixed(1)}%)
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Position sizing + factors */}
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', color: 'var(--text-tertiary)', flexWrap: 'wrap', gap: '0.5rem' }}>
        {signal.position_sizing && (
          <span>Max position: {signal.position_sizing.max_portfolio_pct.toFixed(0)}% av portfölj</span>
        )}
        <span>ATR: {signal.atr_pct?.toFixed(1)}%</span>
      </div>

      {signal.entry?.note && (
        <div style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)', marginTop: '0.5rem', fontStyle: 'italic' }}>
          💡 {signal.entry.note}
        </div>
      )}
    </div>
  );
}
