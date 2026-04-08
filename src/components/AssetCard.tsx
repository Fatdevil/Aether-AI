import { TrendingUp, TrendingDown, Minus, Clock } from 'lucide-react';
import type { Asset } from '../types';
import { getScoreColor } from '../types';
import { timeAgo, formatProvider } from '../utils/timeAgo';

interface AssetCardProps {
  asset: Asset;
  price?: { price: number; changePct: number; currency: string };
  isSelected: boolean;
  onClick: () => void;
}

export default function AssetCard({ asset, price, isSelected, onClick }: AssetCardProps) {
  const Icon = asset.icon;

  const getTrendIcon = (trend: string) => {
    switch (trend) {
      case 'up': return <TrendingUp size={18} style={{ color: 'var(--score-positive)' }} />;
      case 'down': return <TrendingDown size={18} style={{ color: 'var(--score-negative)' }} />;
      default: return <Minus size={18} style={{ color: 'var(--score-neutral)' }} />;
    }
  };

  return (
    <div
      className="glass-panel asset-card"
      style={{
        padding: '1.25rem',
        cursor: 'pointer',
        border: isSelected ? '1px solid var(--accent-cyan)' : '',
      }}
      onClick={onClick}
    >
      <div className="flex justify-between items-center" style={{ marginBottom: '0.75rem' }}>
        <div className="flex items-center gap-4">
          <div className="asset-icon">
            <Icon size={20} color={asset.color} />
          </div>
          <div>
            <h4 style={{ margin: 0, fontSize: '1.05rem' }}>{asset.name}</h4>
            <div className="flex items-center gap-2" style={{ marginTop: '0.2rem' }}>
              <span className="badge" style={{ fontSize: '0.7rem', padding: '0.1rem 0.4rem' }}>{asset.category}</span>
              {price && (
                <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                  {price.currency}{price.price.toLocaleString('sv-SE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  <span style={{
                    color: price.changePct >= 0 ? 'var(--score-positive)' : 'var(--score-negative)',
                    marginLeft: '0.3rem',
                    fontSize: '0.75rem',
                  }}>
                    ({price.changePct >= 0 ? '+' : ''}{price.changePct.toFixed(2)}%)
                  </span>
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="flex flex-col" style={{ alignItems: 'flex-end' }}>
          <div className="flex items-center gap-2">
            {getTrendIcon(asset.trend)}
            <span style={{
              fontSize: '1.5rem',
              fontWeight: 700,
              color: `var(--score-${getScoreColor(asset.finalScore)})`,
            }}>
              {asset.finalScore > 0 ? '+' : ''}{asset.finalScore.toFixed(1)}
            </span>
          </div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>AI Slutpoäng</span>
        </div>
      </div>

      <div className="flex justify-between" style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
        <span>Makro: {asset.scores.macro}</span>
        <span>Mikro: {asset.scores.micro}</span>
        <span>Sent: {asset.scores.sentiment}</span>
        <span>Tekn: {asset.scores.tech}</span>
      </div>

      {/* Metadata: timestamp + model */}
      {(asset.analyzedAt || asset.providerUsed) && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: '0.4rem',
          marginTop: '0.5rem', paddingTop: '0.5rem',
          borderTop: '1px solid rgba(255,255,255,0.04)',
          fontSize: '0.68rem', color: 'var(--text-tertiary)',
        }}>
          <Clock size={11} style={{ opacity: 0.5 }} />
          {asset.analyzedAt && <span>{timeAgo(asset.analyzedAt)}</span>}
          {asset.analyzedAt && asset.providerUsed && <span>·</span>}
          {asset.providerUsed && (
            <span style={{
              padding: '0.05rem 0.35rem', borderRadius: '3px',
              background: 'rgba(102, 126, 234, 0.1)',
              color: 'rgba(102, 126, 234, 0.7)',
              fontSize: '0.65rem',
            }}>
              {formatProvider(asset.providerUsed)}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
