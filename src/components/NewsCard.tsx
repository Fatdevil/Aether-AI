import { useState } from 'react';
import type { NewsItem } from '../types';

interface AffectedAsset {
  id: string;
  direction: 'up' | 'down' | 'mixed';
  strength: 'weak' | 'moderate' | 'strong';
  reason: string;
}

interface AffectedSector {
  id: string;
  direction: 'up' | 'down' | 'mixed';
  reason: string;
}

interface NewsImpact {
  score: number;
  category: string;
  urgency: string;
  one_liner: string;
  affected_assets: AffectedAsset[];
  affected_sectors: AffectedSector[];
  affected_regions: string[];
  provider: string;
}

interface NewsCardProps {
  item: NewsItem;
}

const ASSET_NAMES: Record<string, string> = {
  btc: 'Bitcoin', sp500: 'S&P 500', 'global-equity': 'ACWI', gold: 'Guld',
  silver: 'Silver', eurusd: 'EUR/USD', oil: 'Olja', us10y: '10Y Ränta',
};

const SECTOR_NAMES: Record<string, string> = {
  tech: '💻 Tech', finance: '🏦 Finans', defense: '🛡️ Försvar', energy: '⚡ Energi',
  healthcare: '🏥 Hälsovård', consumer: '🛒 Konsument', industrials: '🏭 Industri',
  realestate: '🏠 Fastigheter',
};

function getImpactColor(score: number): string {
  if (score >= 8) return '#ef4444';
  if (score >= 6) return '#f59e0b';
  if (score >= 4) return '#3b82f6';
  return 'var(--text-tertiary)';
}

function getDirectionEmoji(dir: string): string {
  if (dir === 'up') return '📈';
  if (dir === 'down') return '📉';
  return '↔️';
}

function getDirectionColor(dir: string): string {
  if (dir === 'up') return 'var(--score-positive)';
  if (dir === 'down') return 'var(--score-negative)';
  return 'var(--text-tertiary)';
}

function getStrengthLabel(s: string): string {
  if (s === 'strong') return 'stark';
  if (s === 'moderate') return 'moderat';
  return 'svag';
}

export default function NewsCard({ item }: NewsCardProps) {
  const [expanded, setExpanded] = useState(false);
  const tickers = (item as any).tickers as string[] | undefined;
  const dataSource = (item as any).data_source as string | undefined;
  const impact = (item as any).impact as NewsImpact | undefined;
  // Only show detailed analysis for important news with AI-generated unique commentary
  const isSignificant = impact && impact.score >= 7;
  const hasAIAnalysis = isSignificant && impact.provider === 'gemini';
  const hasImpact = hasAIAnalysis && (impact.affected_assets?.length > 0 || impact.affected_sectors?.length > 0);

  return (
    <div className="glass-panel" style={{ padding: '1.25rem' }}>
      <div className="flex justify-between items-start" style={{ marginBottom: '0.75rem', gap: '1rem' }}>
        <h4 style={{ margin: 0, fontSize: '1rem', lineHeight: 1.4, flex: 1 }}>{item.title}</h4>
        <div className="flex items-center gap-1" style={{ flexShrink: 0 }}>
          {/* Impact score badge – only for significant news */}
          {isSignificant && (
            <span style={{
              fontSize: '0.7rem', fontWeight: 700, padding: '0.15rem 0.45rem',
              borderRadius: '4px', color: '#fff',
              background: getImpactColor(impact.score),
            }}>
              ⚡{impact.score}
            </span>
          )}
        </div>
      </div>
      <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: '0.75rem' }}>
        {item.summary}
      </p>

      {/* Affected assets quick chips (always visible if impact exists) */}
      {hasImpact && (
        <div
          onClick={() => setExpanded(!expanded)}
          style={{ cursor: 'pointer', marginBottom: '0.6rem' }}
        >
          <div className="flex gap-1" style={{ flexWrap: 'wrap', alignItems: 'center' }}>
            {impact.affected_assets.map((asset, i) => (
              <span key={i} style={{
                fontSize: '0.7rem', padding: '0.15rem 0.45rem', borderRadius: '4px',
                background: `${getDirectionColor(asset.direction)}15`,
                border: `1px solid ${getDirectionColor(asset.direction)}30`,
                color: getDirectionColor(asset.direction),
                fontWeight: 600,
              }}>
                {getDirectionEmoji(asset.direction)} {ASSET_NAMES[asset.id] || asset.id}
              </span>
            ))}
            {impact.affected_sectors.map((sector, i) => (
              <span key={`s-${i}`} style={{
                fontSize: '0.65rem', padding: '0.12rem 0.4rem', borderRadius: '4px',
                background: 'rgba(139, 92, 246, 0.1)',
                border: '1px solid rgba(139, 92, 246, 0.2)',
                color: '#a78bfa',
              }}>
                {SECTOR_NAMES[sector.id] || sector.id} {getDirectionEmoji(sector.direction)}
              </span>
            ))}
            <span style={{
              fontSize: '0.6rem', color: 'var(--text-tertiary)',
              transition: 'transform 0.2s',
              transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
              display: 'inline-block', marginLeft: '0.2rem',
            }}>▼</span>
          </div>
        </div>
      )}

      {/* Expanded impact detail */}
      {expanded && impact && (
        <div className="animate-fade-in" style={{
          padding: '0.7rem 0.85rem', borderRadius: '6px', marginBottom: '0.75rem',
          background: 'rgba(139, 92, 246, 0.04)', borderLeft: '3px solid rgba(139, 92, 246, 0.3)',
        }}>
          {/* One-liner */}
          {impact.one_liner && impact.one_liner !== item.title && (
            <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '0.6rem', fontStyle: 'italic' }}>
              💡 {impact.one_liner}
            </div>
          )}

          {/* Affected assets with reasons */}
          {impact.affected_assets.length > 0 && (
            <div style={{ marginBottom: '0.5rem' }}>
              <div style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-tertiary)', marginBottom: '0.35rem' }}>
                📊 Påverkade tillgångar
              </div>
              {impact.affected_assets.map((asset, i) => (
                <div key={i} style={{
                  display: 'flex', gap: '0.5rem', alignItems: 'flex-start',
                  marginBottom: '0.3rem', fontSize: '0.78rem',
                }}>
                  <span style={{
                    color: getDirectionColor(asset.direction), fontWeight: 600,
                    minWidth: '80px', flexShrink: 0,
                  }}>
                    {getDirectionEmoji(asset.direction)} {ASSET_NAMES[asset.id] || asset.id}
                  </span>
                  <span style={{
                    fontSize: '0.65rem', padding: '0.08rem 0.3rem', borderRadius: '3px',
                    background: 'rgba(255,255,255,0.06)', color: 'var(--text-tertiary)',
                    flexShrink: 0,
                  }}>
                    {getStrengthLabel(asset.strength)}
                  </span>
                  <span style={{ color: 'var(--text-secondary)', flex: 1 }}>
                    {asset.reason}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Affected sectors with reasons */}
          {impact.affected_sectors.length > 0 && (
            <div style={{ marginBottom: '0.3rem' }}>
              <div style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-tertiary)', marginBottom: '0.35rem' }}>
                🏭 Påverkade sektorer
              </div>
              {impact.affected_sectors.map((sector, i) => (
                <div key={i} style={{
                  display: 'flex', gap: '0.5rem', alignItems: 'flex-start',
                  marginBottom: '0.3rem', fontSize: '0.78rem',
                }}>
                  <span style={{
                    color: getDirectionColor(sector.direction), fontWeight: 600,
                    minWidth: '100px', flexShrink: 0,
                  }}>
                    {SECTOR_NAMES[sector.id] || sector.id} {getDirectionEmoji(sector.direction)}
                  </span>
                  <span style={{ color: 'var(--text-secondary)', flex: 1 }}>
                    {sector.reason}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Category + AI badge */}
          <div className="flex justify-between items-center" style={{ marginTop: '0.4rem' }}>
            <span style={{
              fontSize: '0.6rem', padding: '0.1rem 0.35rem', borderRadius: '3px',
              background: 'rgba(255,255,255,0.05)', color: 'var(--text-tertiary)',
            }}>
              {impact.category}
            </span>
            <span style={{
              fontSize: '0.55rem', padding: '0.08rem 0.3rem', borderRadius: '3px',
              background: 'rgba(139, 92, 246, 0.2)',
              color: '#a78bfa',
            }}>
              🧠 AI-analys
            </span>
          </div>
        </div>
      )}

      {/* Ticker badges */}
      {tickers && tickers.length > 0 && (
        <div className="flex" style={{ gap: '0.3rem', flexWrap: 'wrap', marginBottom: '0.6rem' }}>
          {tickers.map(ticker => (
            <span key={ticker} style={{
              fontSize: '0.7rem',
              padding: '0.15rem 0.45rem',
              borderRadius: '6px',
              background: 'var(--accent-cyan)10',
              border: '1px solid var(--accent-cyan)25',
              color: 'var(--accent-cyan)',
              fontWeight: 600,
              fontFamily: 'var(--font-mono)',
            }}>
              ${ticker}
            </span>
          ))}
        </div>
      )}

      <div className="flex justify-between items-center" style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>
        <div className="flex items-center gap-2">
          <span className="badge" style={{ fontSize: '0.75rem', padding: '0.15rem 0.5rem' }}>{item.category}</span>
          <span>{item.source}</span>
          {dataSource === 'marketaux' && (
            <span style={{
              fontSize: '0.65rem',
              padding: '0.1rem 0.35rem',
              borderRadius: '4px',
              background: '#a55eea15',
              color: '#a55eea',
              border: '1px solid #a55eea30',
            }}>
              API
            </span>
          )}
        </div>
        <span>{item.time}</span>
      </div>
    </div>
  );
}
