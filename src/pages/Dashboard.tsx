import { useState } from 'react';
import { motion } from 'framer-motion';
import { ChevronDown, ChevronUp, Activity, ArrowRight } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { Asset } from '../types';
import DailyBrief from '../components/DailyBrief';
import PriceChart from '../components/PriceChart';
import AssetDetailModal from '../components/AssetDetailModal';

interface DashboardProps {
  assets: Asset[];
  marketState: {
    overallScore: number;
    overallSummary: string;
    expandedSummary?: string;
    lastUpdated: string;
  };
  prices: Record<string, { price: number; changePct: number; currency: string }>;
}

export default function Dashboard({ assets, marketState, prices }: DashboardProps) {
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [showFullBrief, setShowFullBrief] = useState(false);
  const [detailAsset, setDetailAsset] = useState<Asset | null>(null);
  const score = marketState.overallScore;

  // Compute market regime
  const regime = getRegimeInfo(score);
  const sorted = [...assets].sort((a, b) => Math.abs(b.finalScore) - Math.abs(a.finalScore));
  const buySignals = assets.filter(a => a.finalScore >= 3);
  const sellSignals = assets.filter(a => a.finalScore <= -3);

  return (
    <main className="container" style={{ padding: '1.5rem 1.25rem 6rem' }}>
      {/* ── Section 1: Hero — Marknadsregim + Sammanfattning ── */}
      <motion.section
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-panel"
        style={{
          padding: '1.75rem 2rem',
          marginBottom: '1.5rem',
          borderLeft: `4px solid ${regime.color}`,
          background: `linear-gradient(135deg, ${regime.color}08 0%, transparent 60%)`,
        }}
      >
        {/* Regime + Score Row */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span style={{ fontSize: '2rem' }}>{regime.icon}</span>
            <div>
              <h2 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 700 }}>
                {regime.label}
              </h2>
              <p style={{ margin: 0, color: 'var(--text-tertiary)', fontSize: '0.8rem' }}>
                {marketState.lastUpdated}
              </p>
            </div>
          </div>

          {/* Signal Counts */}
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <SignalBadge count={buySignals.length} type="buy" />
            <SignalBadge count={assets.length - buySignals.length - sellSignals.length} type="neutral" />
            <SignalBadge count={sellSignals.length} type="sell" />
          </div>
        </div>

        {/* AI Summary */}
        <p style={{ fontSize: '0.95rem', lineHeight: 1.7, color: 'var(--text-secondary)', margin: 0 }}>
          {marketState.overallSummary}
        </p>

        {/* Expandable Full Analysis */}
        {marketState.expandedSummary && (
          <div style={{ marginTop: '1rem' }}>
            <button
              onClick={() => setShowFullBrief(!showFullBrief)}
              style={{
                background: 'rgba(79, 172, 254, 0.08)',
                border: '1px solid rgba(79, 172, 254, 0.2)',
                padding: '0.5rem 1rem',
                borderRadius: '8px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                transition: 'all 0.2s ease',
                fontFamily: 'var(--font-body)',
              }}
            >
              <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--accent-cyan)' }}>
                {showFullBrief ? 'Dölj analys' : '📖 Läs full AI-analys'}
              </span>
              {showFullBrief ? <ChevronUp size={14} color="var(--accent-cyan)" /> : <ChevronDown size={14} color="var(--accent-cyan)" />}
            </button>

            {showFullBrief && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                style={{
                  marginTop: '1rem',
                  padding: '1.25rem 1.5rem',
                  borderRadius: '10px',
                  background: 'rgba(79, 172, 254, 0.04)',
                  border: '1px solid rgba(79, 172, 254, 0.1)',
                }}
              >
                {marketState.expandedSummary.split('\n').map((line, i) => {
                  const trimmed = line.trim();
                  if (!trimmed) return <div key={i} style={{ height: '0.5rem' }} />;
                  if (trimmed.startsWith('### ')) {
                    return (
                      <h4 key={i} style={{
                        fontSize: '1rem', fontWeight: 700, color: 'var(--accent-cyan)',
                        margin: '1rem 0 0.3rem', borderBottom: '1px solid rgba(0,242,254,0.08)', paddingBottom: '0.25rem',
                      }}>
                        {trimmed.replace('### ', '')}
                      </h4>
                    );
                  }
                  if (trimmed.startsWith('## ')) {
                    return <h3 key={i} style={{ fontSize: '1.1rem', fontWeight: 700, margin: '1rem 0 0.3rem' }}>{trimmed.replace('## ', '')}</h3>;
                  }
                  return (
                    <p key={i} style={{ fontSize: '0.88rem', lineHeight: 1.75, color: 'var(--text-secondary)', margin: '0 0 0.25rem' }}>
                      {trimmed}
                    </p>
                  );
                })}
              </motion.div>
            )}
          </div>
        )}
      </motion.section>

      {/* ── Section 2: Daily Brief ── */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05 }}
        style={{ marginBottom: '1.5rem' }}
      >
        <DailyBrief />
      </motion.div>

      {/* ── Section 3: Top Signaler — Strongest Buy & Sell ── */}
      {(buySignals.length > 0 || sellSignals.length > 0) && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: '1rem',
            marginBottom: '1.5rem',
          }}
        >
          {buySignals.length > 0 && (
            <div className="glass-panel" style={{ padding: '1.25rem', borderLeft: '3px solid var(--score-positive)' }}>
              <h4 style={{ fontSize: '0.75rem', color: 'var(--score-positive)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.75rem' }}>
                ⬆ Starkaste köpsignaler
              </h4>
              {buySignals.sort((a, b) => b.finalScore - a.finalScore).slice(0, 3).map(a => {
                const BuyIcon = a.icon;
                return (
                <div key={a.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.4rem 0', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                  <span style={{ fontWeight: 500, fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}><BuyIcon size={14} color={a.color} /> {a.name}</span>
                  <span style={{ fontWeight: 700, color: 'var(--score-positive)', fontSize: '0.9rem' }}>+{a.finalScore.toFixed(1)}</span>
                </div>
              );})}
            </div>
          )}

          {sellSignals.length > 0 && (
            <div className="glass-panel" style={{ padding: '1.25rem', borderLeft: '3px solid var(--score-negative)' }}>
              <h4 style={{ fontSize: '0.75rem', color: 'var(--score-negative)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.75rem' }}>
                ⬇ Starkaste säljsignaler
              </h4>
              {sellSignals.sort((a, b) => a.finalScore - b.finalScore).slice(0, 3).map(a => {
                const SellIcon = a.icon;
                return (
                <div key={a.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.4rem 0', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                  <span style={{ fontWeight: 500, fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}><SellIcon size={14} color={a.color} /> {a.name}</span>
                  <span style={{ fontWeight: 700, color: 'var(--score-negative)', fontSize: '0.9rem' }}>{a.finalScore.toFixed(1)}</span>
                </div>
              );})}
            </div>
          )}
        </motion.div>
      )}

      {/* ── Section 4: Alla tillgångar — Grid ── */}
      <motion.section
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
      >
        <h3 style={{ fontSize: '1.1rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Activity size={18} color="var(--accent-blue)" />
          Alla tillgångar ({assets.length})
        </h3>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
          gap: '0.75rem',
        }}>
          {sorted.map(asset => {
            const p = prices[asset.id];
            const isSelected = selectedAssetId === asset.id;

            return (
              <motion.div
                key={asset.id}
                className="glass-panel"
                whileHover={{ scale: 1.01 }}
                onClick={() => setSelectedAssetId(isSelected ? null : asset.id)}
                style={{
                  padding: '1rem 1.25rem',
                  cursor: 'pointer',
                  border: isSelected ? '1px solid rgba(79, 172, 254, 0.3)' : undefined,
                  background: isSelected ? 'rgba(79, 172, 254, 0.06)' : undefined,
                }}
              >
                {/* Asset Header */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                    <AssetIconBadge icon={asset.icon} color={asset.color} />
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '0.95rem' }}>{asset.name}</div>
                      <div style={{ color: 'var(--text-tertiary)', fontSize: '0.75rem' }}>
                        {p ? `${p.currency}${p.price.toLocaleString('sv-SE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—'}
                        {p && (
                          <span style={{
                            marginLeft: '0.5rem',
                            color: p.changePct >= 0 ? 'var(--score-positive)' : 'var(--score-negative)',
                            fontWeight: 600,
                          }}>
                            {p.changePct >= 0 ? '↑' : '↓'} {Math.abs(p.changePct).toFixed(2)}%
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Score Badge */}
                  <ScoreBadge score={asset.finalScore} />
                </div>

                {/* Agent Scores Row */}
                <div style={{
                  display: 'flex', gap: '0.5rem', marginTop: '0.75rem',
                  flexWrap: 'wrap',
                }}>
                  {['macro', 'micro', 'sentiment', 'tech'].map(agent => {
                    const agentScore = (asset.scores as any)?.[agent] ?? 0;
                    return (
                      <MiniAgent key={agent} label={agent} score={agentScore} />
                    );
                  })}
                </div>

                {/* Expanded: Chart + Deep Dive button */}
                {isSelected && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    style={{ marginTop: '1rem' }}
                  >
                    {asset.supervisorText && (
                      <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: '0.75rem', fontStyle: 'italic' }}>
                        "{asset.supervisorText.substring(0, 200)}..."
                      </p>
                    )}
                    <PriceChart assetId={asset.id} assetName={asset.name} height={200} />
                    <button
                      onClick={(e) => { e.stopPropagation(); setDetailAsset(asset); }}
                      style={{
                        marginTop: '0.75rem', width: '100%', padding: '0.6rem',
                        background: 'linear-gradient(135deg, rgba(79, 172, 254, 0.1), rgba(157, 78, 221, 0.1))',
                        border: '1px solid rgba(79, 172, 254, 0.2)', borderRadius: '8px',
                        color: 'var(--accent-blue)', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600,
                        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem',
                        fontFamily: 'var(--font-body)',
                      }}
                    >
                      🔬 Djupdyk — Se alla agenters analys
                      <ArrowRight size={14} />
                    </button>
                  </motion.div>
                )}
              </motion.div>
            );
          })}
        </div>
      </motion.section>

      {/* ── CTA: Gå till portfölj ── */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.25 }}
        style={{ marginTop: '2rem', textAlign: 'center' }}
      >
        <Link to="/portfolio" style={{ textDecoration: 'none' }}>
          <button className="button-primary" style={{ fontSize: '1rem', padding: '0.85rem 2rem' }}>
            💼 Se portföljrekommendation
          </button>
        </Link>
      </motion.div>

      {/* Asset Detail Modal */}
      {detailAsset && (
        <AssetDetailModal
          asset={detailAsset}
          price={prices[detailAsset.id]}
          onClose={() => setDetailAsset(null)}
        />
      )}
    </main>
  );
}

/* ── Helper Components ── */

function AssetIconBadge({ icon: Icon, color }: { icon: LucideIcon; color: string }) {
  return (
    <div style={{
      width: 36, height: 36, borderRadius: '50%',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'var(--bg-tertiary)', border: '1px solid var(--glass-border)',
      flexShrink: 0,
    }}>
      <Icon size={18} color={color} />
    </div>
  );
}

function SignalBadge({ count, type }: { count: number; type: 'buy' | 'sell' | 'neutral' }) {
  const config = {
    buy: { bg: 'rgba(0, 230, 118, 0.1)', border: 'rgba(0, 230, 118, 0.2)', color: 'var(--score-positive)', label: 'Köp' },
    sell: { bg: 'rgba(255, 23, 68, 0.1)', border: 'rgba(255, 23, 68, 0.2)', color: 'var(--score-negative)', label: 'Sälj' },
    neutral: { bg: 'rgba(255, 255, 255, 0.04)', border: 'rgba(255, 255, 255, 0.08)', color: 'var(--text-secondary)', label: 'Neutral' },
  }[type];

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '0.3rem',
      padding: '0.3rem 0.65rem', borderRadius: '8px',
      background: config.bg, border: `1px solid ${config.border}`,
    }}>
      <span style={{ fontWeight: 700, fontSize: '0.85rem', color: config.color }}>{count}</span>
      <span style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>{config.label}</span>
    </div>
  );
}

function ScoreBadge({ score }: { score: number }) {
  const color = score > 2 ? 'var(--score-positive)' : score < -2 ? 'var(--score-negative)' : 'var(--score-neutral)';
  const bgColor = score > 2 ? 'rgba(0,230,118,0.1)' : score < -2 ? 'rgba(255,23,68,0.1)' : 'rgba(255,234,0,0.08)';
  const label = score > 3 ? 'KÖP' : score < -3 ? 'SÄLJ' : score > 0 ? 'Positiv' : score < 0 ? 'Negativ' : 'Neutral';

  return (
    <div style={{ textAlign: 'right' }}>
      <div style={{
        fontWeight: 800, fontSize: '1.2rem', color,
        lineHeight: 1,
      }}>
        {score > 0 ? '+' : ''}{score.toFixed(1)}
      </div>
      <div style={{
        fontSize: '0.6rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em',
        padding: '0.15rem 0.4rem', borderRadius: '4px', marginTop: '0.2rem',
        background: bgColor, color, display: 'inline-block',
      }}>
        {label}
      </div>
    </div>
  );
}

function MiniAgent({ label, score }: { label: string; score: number }) {
  const color = score > 0 ? 'var(--score-positive)' : score < 0 ? 'var(--score-negative)' : 'var(--text-tertiary)';
  const displayLabel = { macro: 'Makro', micro: 'Mikro', sentiment: 'Sent', tech: 'Tekn' }[label] || label;

  return (
    <div style={{
      fontSize: '0.7rem', padding: '0.2rem 0.45rem', borderRadius: '4px',
      background: 'rgba(255,255,255,0.04)',
      display: 'flex', alignItems: 'center', gap: '0.25rem',
    }}>
      <span style={{ color: 'var(--text-tertiary)' }}>{displayLabel}:</span>
      <span style={{ fontWeight: 600, color }}>{score > 0 ? '+' : ''}{score}</span>
    </div>
  );
}

function getRegimeInfo(score: number) {
  if (score >= 4) return { label: 'Risk On', icon: '🚀', color: '#10b981' };
  if (score >= 1.5) return { label: 'Optimistisk', icon: '📈', color: '#10b981' };
  if (score <= -4) return { label: 'Risk Off', icon: '🛑', color: '#ef4444' };
  if (score <= -1.5) return { label: 'Defensiv', icon: '🛡️', color: '#ef4444' };
  return { label: 'Avvaktande', icon: '⏸️', color: '#f59e0b' };
}
