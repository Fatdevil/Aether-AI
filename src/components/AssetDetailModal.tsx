import { useState } from 'react';
import { X, TrendingUp, TrendingDown, Brain, BarChart3, Newspaper, Cpu, Shield, ChevronDown, ChevronUp } from 'lucide-react';
import type { Asset } from '../types';
import { getRecommendation } from '../types';
import PriceChart from './PriceChart';

interface Props {
  asset: Asset;
  price?: { price: number; changePct: number; currency: string };
  onClose: () => void;
}

const AGENT_CONFIG: Record<string, { label: string; icon: typeof Brain; color: string; desc: string }> = {
  macro: { label: 'Makro', icon: Brain, color: '#667eea', desc: 'Makroekonomi, räntor, centralbanker' },
  micro: { label: 'Mikro', icon: BarChart3, color: '#f59e0b', desc: 'Tillgångsspecifik teknisk data' },
  sentiment: { label: 'Sentiment', icon: Newspaper, color: '#10b981', desc: 'Nyheter, flöden, marknadshumör' },
  tech: { label: 'Teknisk', icon: Cpu, color: '#ef4444', desc: 'RSI, MACD, SMA, trendanalys' },
};

export default function AssetDetailModal({ asset, price, onClose }: Props) {
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null);
  const score = asset.finalScore;
  const recommendation = getRecommendation(score);
  const scoreColor = score > 2 ? '#00e676' : score < -2 ? '#ff1744' : '#ffea00';
  const Icon = asset.icon;

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 9999,
        background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(8px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '1rem',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: '100%', maxWidth: '680px', maxHeight: '90vh',
          overflowY: 'auto',
          background: 'var(--bg-secondary)',
          border: '1px solid var(--glass-border)',
          borderRadius: '16px',
          padding: '0',
        }}
      >
        {/* ── Header ── */}
        <div style={{
          padding: '1.5rem 1.5rem 1rem',
          borderBottom: '1px solid var(--glass-border)',
          background: `linear-gradient(135deg, ${scoreColor}08 0%, transparent 60%)`,
          borderRadius: '16px 16px 0 0',
          position: 'sticky', top: 0, zIndex: 1,
          backdropFilter: 'blur(20px)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <div style={{
                width: 48, height: 48, borderRadius: '50%',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: 'var(--bg-tertiary)', border: '1px solid var(--glass-border)',
              }}>
                <Icon size={24} color={asset.color} />
              </div>
              <div>
                <h2 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 700 }}>{asset.name}</h2>
                <p style={{ margin: 0, color: 'var(--text-tertiary)', fontSize: '0.8rem' }}>{asset.category}</p>
              </div>
            </div>
            <button
              onClick={onClose}
              style={{
                background: 'rgba(255,255,255,0.06)', border: '1px solid var(--glass-border)',
                borderRadius: '8px', padding: '0.4rem', cursor: 'pointer', color: 'var(--text-secondary)',
              }}
            >
              <X size={18} />
            </button>
          </div>

          {/* Score + Price Row */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1rem', gap: '1rem', flexWrap: 'wrap' }}>
            {/* AI Score */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <div style={{
                fontSize: '2rem', fontWeight: 800, color: scoreColor, lineHeight: 1,
              }}>
                {score > 0 ? '+' : ''}{score.toFixed(1)}
              </div>
              <div>
                <div style={{
                  padding: '0.2rem 0.6rem', borderRadius: '6px', fontSize: '0.75rem', fontWeight: 700,
                  background: `${scoreColor}18`, color: scoreColor, display: 'inline-block',
                }}>
                  {recommendation}
                </div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', marginTop: '0.2rem' }}>
                  AI Composite Score
                </div>
              </div>
            </div>

            {/* Current Price */}
            {price && (
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '1.3rem', fontWeight: 700 }}>
                  {price.currency === 'SEK' ? '' : price.currency === 'USD' ? '$' : ''}{price.price.toLocaleString('sv-SE', { maximumFractionDigits: 2 })}
                </div>
                <div style={{
                  fontSize: '0.8rem', fontWeight: 600,
                  color: price.changePct >= 0 ? '#00e676' : '#ff1744',
                  display: 'flex', alignItems: 'center', gap: '0.2rem', justifyContent: 'flex-end',
                }}>
                  {price.changePct >= 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                  {price.changePct >= 0 ? '+' : ''}{price.changePct.toFixed(2)}%
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ── Content ── */}
        <div style={{ padding: '1.25rem 1.5rem 1.5rem' }}>

          {/* Supervisor Motivering */}
          {asset.supervisorText && (
            <section style={{ marginBottom: '1.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                <Shield size={16} color="#667eea" />
                <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700 }}>Supervisor — AI Motivering</h3>
              </div>
              <div style={{
                padding: '1rem', borderRadius: '10px',
                background: 'rgba(102, 126, 234, 0.06)', border: '1px solid rgba(102, 126, 234, 0.12)',
              }}>
                <p style={{
                  margin: 0, fontSize: '0.85rem', lineHeight: 1.7,
                  color: 'var(--text-secondary)', fontStyle: 'italic',
                }}>
                  "{asset.supervisorText}"
                </p>
              </div>
            </section>
          )}

          {/* 4 Agent Cards */}
          <section style={{ marginBottom: '1.5rem' }}>
            <h3 style={{ margin: '0 0 0.75rem', fontSize: '0.95rem', fontWeight: 700 }}>
              Agenternas Analys
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {(['macro', 'micro', 'sentiment', 'tech'] as const).map(agentKey => {
                const config = AGENT_CONFIG[agentKey];
                const agentScore = asset.scores[agentKey];
                const detail = asset.agentDetails?.[agentKey];
                const isExpanded = expandedAgent === agentKey;
                const AgentIcon = config.icon;

                return (
                  <div
                    key={agentKey}
                    style={{
                      borderRadius: '10px',
                      border: `1px solid ${isExpanded ? config.color + '40' : 'var(--glass-border)'}`,
                      background: isExpanded ? `${config.color}08` : 'rgba(255,255,255,0.02)',
                      overflow: 'hidden',
                      transition: 'all 0.2s',
                    }}
                  >
                    {/* Agent Header */}
                    <button
                      onClick={() => setExpandedAgent(isExpanded ? null : agentKey)}
                      style={{
                        width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        padding: '0.75rem 1rem', cursor: 'pointer',
                        background: 'none', border: 'none', color: 'var(--text-primary)',
                        fontFamily: 'var(--font-body)',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                        <AgentIcon size={16} color={config.color} />
                        <div style={{ textAlign: 'left' }}>
                          <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>{config.label}</div>
                          <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>{config.desc}</div>
                        </div>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <span style={{
                          fontWeight: 700, fontSize: '0.95rem',
                          color: agentScore > 0 ? '#00e676' : agentScore < 0 ? '#ff1744' : 'var(--text-tertiary)',
                        }}>
                          {agentScore > 0 ? '+' : ''}{agentScore.toFixed(1)}
                        </span>
                        {isExpanded ? <ChevronUp size={14} color="var(--text-tertiary)" /> : <ChevronDown size={14} color="var(--text-tertiary)" />}
                      </div>
                    </button>

                    {/* Agent Detail */}
                    {isExpanded && detail && (
                      <div style={{
                        padding: '0 1rem 1rem',
                        borderTop: `1px solid ${config.color}20`,
                      }}>
                        {/* Reasoning */}
                        <p style={{
                          margin: '0.75rem 0', fontSize: '0.82rem', lineHeight: 1.65,
                          color: 'var(--text-secondary)',
                        }}>
                          {detail.reasoning}
                        </p>

                        {/* Key Factors */}
                        {detail.key_factors && detail.key_factors.length > 0 && (
                          <div style={{ marginTop: '0.5rem' }}>
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', marginBottom: '0.3rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                              Nyckelfaktorer
                            </div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem' }}>
                              {detail.key_factors.map((factor, i) => (
                                <span key={i} style={{
                                  padding: '0.2rem 0.5rem', borderRadius: '4px', fontSize: '0.72rem',
                                  background: `${config.color}12`, color: config.color,
                                  border: `1px solid ${config.color}25`,
                                }}>
                                  {factor}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Confidence + Provider */}
                        <div style={{
                          display: 'flex', gap: '1rem', marginTop: '0.75rem', fontSize: '0.7rem', color: 'var(--text-tertiary)',
                        }}>
                          <span>Konfidens: {(detail.confidence * 100).toFixed(0)}%</span>
                          <span>LLM: {detail.provider}</span>
                        </div>
                      </div>
                    )}

                    {/* No detail fallback */}
                    {isExpanded && !detail && (
                      <div style={{ padding: '0 1rem 1rem', color: 'var(--text-tertiary)', fontSize: '0.8rem' }}>
                        Ingen detaljerad analys tillgänglig.
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </section>

          {/* Score Breakdown Bar */}
          <section style={{ marginBottom: '1.5rem' }}>
            <h3 style={{ margin: '0 0 0.75rem', fontSize: '0.95rem', fontWeight: 700 }}>Poängfördelning</h3>
            <div style={{
              padding: '1rem', borderRadius: '10px',
              background: 'rgba(255,255,255,0.02)', border: '1px solid var(--glass-border)',
            }}>
              {(['macro', 'micro', 'sentiment', 'tech'] as const).map(agentKey => {
                const s = asset.scores[agentKey];
                const pct = Math.min(Math.abs(s) / 10 * 100, 100);
                const config = AGENT_CONFIG[agentKey];
                return (
                  <div key={agentKey} style={{ marginBottom: agentKey !== 'tech' ? '0.6rem' : 0 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.2rem' }}>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{config.label}</span>
                      <span style={{ fontSize: '0.75rem', fontWeight: 600, color: s > 0 ? '#00e676' : s < 0 ? '#ff1744' : 'var(--text-tertiary)' }}>
                        {s > 0 ? '+' : ''}{s.toFixed(1)}
                      </span>
                    </div>
                    <div style={{
                      height: '6px', borderRadius: '3px', background: 'rgba(255,255,255,0.06)',
                      overflow: 'hidden',
                    }}>
                      <div style={{
                        height: '100%', borderRadius: '3px',
                        width: `${pct}%`,
                        background: s > 0 ? '#00e676' : s < 0 ? '#ff1744' : config.color,
                        opacity: 0.7,
                        transition: 'width 0.3s ease',
                      }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          {/* Scenario Probabilities */}
          {asset.scenarioProbabilities && (
            <section style={{ marginBottom: '1.5rem' }}>
              <h3 style={{ margin: '0 0 0.75rem', fontSize: '0.95rem', fontWeight: 700 }}>Scenarioanalys</h3>
              <div style={{
                display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem',
              }}>
                {[
                  { key: 'bull', label: '🟢 Bull', color: '#10b981' },
                  { key: 'base', label: '🟡 Bas', color: '#f59e0b' },
                  { key: 'bear', label: '🔴 Bear', color: '#ef4444' },
                ].map(({ key, label, color }) => {
                  const prob = (asset.scenarioProbabilities as any)[key] ?? 0;
                  const displayPct = prob > 1 ? prob : prob * 100; // Handle both 0-1 and 0-100 formats
                  return (
                    <div key={key} style={{
                      padding: '0.75rem', borderRadius: '10px', textAlign: 'center',
                      background: `${color}08`, border: `1px solid ${color}20`,
                    }}>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginBottom: '0.2rem' }}>{label}</div>
                      <div style={{ fontSize: '1.3rem', fontWeight: 700, color }}>{displayPct.toFixed(0)}%</div>
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {/* Price Chart */}
          <section>
            <h3 style={{ margin: '0 0 0.75rem', fontSize: '0.95rem', fontWeight: 700 }}>Prishistorik</h3>
            <div style={{
              padding: '0.75rem', borderRadius: '10px',
              background: 'rgba(255,255,255,0.02)', border: '1px solid var(--glass-border)',
            }}>
              <PriceChart assetId={asset.id} assetName={asset.name} height={220} />
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
