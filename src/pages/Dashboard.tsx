import { useState, useEffect } from 'react';
import { Activity, BarChart3, Brain, ChevronRight } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { Asset } from '../types';
import AssetCard from '../components/AssetCard';
import AssetDetail from '../components/AssetDetail';
import { CalendarWidget } from '../components/IntelligenceWidgets';
import CorrelationHeatmap from '../components/CorrelationHeatmap';
import TrendingWidget from '../components/TrendingWidget';
import { api } from '../api/client';

// Predictive Pulse Widget for Dashboard
function PredictivePulse() {
  const [health, setHealth] = useState<any>(null);
  const [events, setEvents] = useState<any>(null);

  useEffect(() => {
    api.getSystemHealth().then(setHealth).catch(() => {});
    api.getEventLog().then(setEvents).catch(() => {});
  }, []);

  const statusColor = health?.status === 'HEALTHY' ? '#00c851' : health?.status === 'WARNING' ? '#ffa502' : '#ff4757';
  const statusEmoji = health?.status === 'HEALTHY' ? '🟢' : health?.status === 'WARNING' ? '🟡' : '🔴';

  return (
    <Link to="/predict" style={{ textDecoration: 'none', color: 'inherit' }}>
      <div className="glass-panel" style={{
        padding: '1.25rem', cursor: 'pointer',
        transition: 'all 0.2s ease',
        background: 'linear-gradient(135deg, rgba(102,126,234,0.04) 0%, rgba(118,75,162,0.04) 100%)',
        borderLeft: '3px solid #667eea',
      }}
      onMouseEnter={e => (e.currentTarget.style.background = 'linear-gradient(135deg, rgba(102,126,234,0.08) 0%, rgba(118,75,162,0.08) 100%)')}
      onMouseLeave={e => (e.currentTarget.style.background = 'linear-gradient(135deg, rgba(102,126,234,0.04) 0%, rgba(118,75,162,0.04) 100%)')}
      >
        <h4 style={{ margin: '0 0 0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1rem' }}>
          <Brain size={18} color="#a78bfa" />
          Predictive Intelligence
          <ChevronRight size={14} color="var(--text-tertiary)" style={{ marginLeft: 'auto' }} />
        </h4>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {/* System Health */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>System</span>
            <span style={{ fontSize: '0.78rem', fontWeight: 600, color: statusColor }}>
              {health ? `${statusEmoji} ${health.status}` : '...'}
            </span>
          </div>

          {/* Events */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>Events (30d)</span>
            <span style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-primary)' }}>
              {events?.last_30_days ?? '—'}
            </span>
          </div>

          {/* Critical count */}
          {events?.by_severity?.CRITICAL > 0 && (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>Kritiska</span>
              <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#ff4757' }}>
                🔴 {events.by_severity.CRITICAL}
              </span>
            </div>
          )}

          {/* CTA */}
          <div style={{
            marginTop: '0.25rem', fontSize: '0.7rem', color: '#667eea',
            display: 'flex', alignItems: 'center', gap: '0.3rem',
          }}>
            Öppna prediktiv analys →
          </div>
        </div>
      </div>
    </Link>
  );
}

interface DashboardProps {
  assets: Asset[];
  marketState: {
    overallScore: number;
    overallSummary: string;
    lastUpdated: string;
  };
  prices: Record<string, { price: number; changePct: number; currency: string }>;
}

export default function Dashboard({ assets, marketState, prices }: DashboardProps) {
  const [selectedAsset, setSelectedAsset] = useState(assets[0]);

  // Update selected asset when assets change (e.g. after refresh)
  const currentSelected = assets.find(a => a.id === selectedAsset?.id) || assets[0];

  return (
    <main className="container" style={{ paddingTop: '2rem', paddingBottom: '6rem' }}>

      {/* Supervisor Summary — Redesigned */}
      <section className="glass-panel animate-fade-in" style={{ padding: '1.75rem 2rem', marginBottom: '2rem' }}>
        {(() => {
          // Compute market mood from asset scores
          const buyAssets = assets.filter(a => a.finalScore >= 3);
          const sellAssets = assets.filter(a => a.finalScore <= -3);
          const neutralAssets = assets.filter(a => a.finalScore > -3 && a.finalScore < 3);
          const sorted = [...assets].sort((a, b) => b.finalScore - a.finalScore);
          const topBuys = sorted.filter(a => a.finalScore > 0).slice(0, 2);
          const topSells = sorted.filter(a => a.finalScore < 0).reverse().slice(0, 2);

          // Market mood
          const score = marketState.overallScore;
          let mood = 'SELEKTIV';
          let moodColor = '#f59e0b';
          let moodIcon = '⚡';
          if (score >= 4) { mood = 'RISK ON'; moodColor = '#10b981'; moodIcon = '🚀'; }
          else if (score >= 1.5) { mood = 'OPTIMISTISK'; moodColor = '#10b981'; moodIcon = '📈'; }
          else if (score <= -4) { mood = 'RISK OFF'; moodColor = '#ef4444'; moodIcon = '🛑'; }
          else if (score <= -1.5) { mood = 'DEFENSIV'; moodColor = '#ef4444'; moodIcon = '🛡'; }
          else if (buyAssets.length > 0 && sellAssets.length > 0) { mood = 'SELEKTIV'; moodColor = '#f59e0b'; moodIcon = '⚡'; }
          else { mood = 'AVVAKTA'; moodColor = '#6b7280'; moodIcon = '⏸'; }

          return (
            <>
              {/* Top row: Title + Mood badge */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
                <Activity className="pulse-glow" size={28} color="var(--accent-purple)" />
                <h2 style={{ fontSize: '1.4rem', margin: 0, flex: 1 }}>Supervisor Marknadssyn</h2>
                <div style={{
                  display: 'flex', alignItems: 'center', gap: '0.5rem',
                  padding: '0.4rem 1rem', borderRadius: '20px',
                  background: `${moodColor}12`,
                  border: `1.5px solid ${moodColor}40`,
                  boxShadow: `0 0 20px ${moodColor}15`,
                }}>
                  <span style={{ fontSize: '1.1rem' }}>{moodIcon}</span>
                  <span style={{ fontSize: '0.9rem', fontWeight: 800, color: moodColor, letterSpacing: '0.05em' }}>
                    {mood}
                  </span>
                </div>
              </div>

              {/* Signal counts */}
              <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap', alignItems: 'center' }}>
                <div style={{
                  display: 'flex', alignItems: 'center', gap: '0.35rem',
                  padding: '0.3rem 0.75rem', borderRadius: '8px',
                  background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.15)',
                }}>
                  <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#10b981' }} />
                  <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#10b981' }}>{buyAssets.length}</span>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>Köp</span>
                </div>
                <div style={{
                  display: 'flex', alignItems: 'center', gap: '0.35rem',
                  padding: '0.3rem 0.75rem', borderRadius: '8px',
                  background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)',
                }}>
                  <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#6b7280' }} />
                  <span style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--text-secondary)' }}>{neutralAssets.length}</span>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>Neutral</span>
                </div>
                <div style={{
                  display: 'flex', alignItems: 'center', gap: '0.35rem',
                  padding: '0.3rem 0.75rem', borderRadius: '8px',
                  background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.15)',
                }}>
                  <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#ef4444' }} />
                  <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#ef4444' }}>{sellAssets.length}</span>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>Sälj</span>
                </div>

                <span style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', marginLeft: 'auto' }}>
                  4 AI × {assets.length} tillgångar • {marketState.lastUpdated}
                </span>
              </div>

              {/* Top picks row */}
              <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
                {/* Best buys */}
                {topBuys.length > 0 && (
                  <div style={{
                    flex: 1, minWidth: '200px', padding: '0.6rem 0.85rem', borderRadius: '8px',
                    background: 'rgba(16,185,129,0.04)', borderLeft: '3px solid #10b981',
                  }}>
                    <div style={{ fontSize: '0.65rem', color: '#10b981', fontWeight: 700, marginBottom: '0.35rem', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                      Starkaste köpsignaler
                    </div>
                    <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                      {topBuys.map(a => (
                        <div key={a.id} style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                          <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>{a.name}</span>
                          <span style={{
                            fontSize: '0.7rem', fontWeight: 800, padding: '0.1rem 0.4rem', borderRadius: '4px',
                            background: 'rgba(16,185,129,0.15)', color: '#10b981',
                          }}>+{a.finalScore.toFixed(1)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {/* Worst sells */}
                {topSells.length > 0 && (
                  <div style={{
                    flex: 1, minWidth: '200px', padding: '0.6rem 0.85rem', borderRadius: '8px',
                    background: 'rgba(239,68,68,0.04)', borderLeft: '3px solid #ef4444',
                  }}>
                    <div style={{ fontSize: '0.65rem', color: '#ef4444', fontWeight: 700, marginBottom: '0.35rem', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                      Starkaste säljsignaler
                    </div>
                    <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                      {topSells.map(a => (
                        <div key={a.id} style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                          <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>{a.name}</span>
                          <span style={{
                            fontSize: '0.7rem', fontWeight: 800, padding: '0.1rem 0.4rem', borderRadius: '4px',
                            background: 'rgba(239,68,68,0.15)', color: '#ef4444',
                          }}>{a.finalScore.toFixed(1)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Summary text */}
              <p style={{ fontSize: '0.88rem', maxWidth: '900px', lineHeight: '1.7', color: 'var(--text-tertiary)', margin: 0 }}>
                {marketState.overallSummary}
              </p>
            </>
          );
        })()}
      </section>

      {/* Intelligence Widgets — Row 1: Compact Trio */}
      <div className="animate-fade-in" style={{ marginBottom: '1rem', animationDelay: '0.05s' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem' }}>
          <CalendarWidget />
          <TrendingWidget />
          <PredictivePulse />
        </div>
      </div>

      {/* Intelligence Widgets — Row 2: Correlation (full width) */}
      <div className="animate-fade-in" style={{ marginBottom: '2rem', animationDelay: '0.1s' }}>
        <CorrelationHeatmap />
      </div>

      {/* Main Grid */}
      <div className="dashboard-grid">
        {/* Asset List */}
        <div className="asset-list-col animate-fade-in" style={{ animationDelay: '0.1s' }}>
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            <BarChart3 size={20} color="var(--accent-blue)" /> Överblick ({assets.length})
          </h3>
          <div className="flex flex-col gap-2">
            {assets.map((asset) => (
              <AssetCard
                key={asset.id}
                asset={asset}
                price={prices[asset.id]}
                isSelected={currentSelected?.id === asset.id}
                onClick={() => setSelectedAsset(asset)}
              />
            ))}
          </div>
        </div>

        {/* Detail Panel */}
        <div className="detail-col animate-fade-in" style={{ animationDelay: '0.2s' }}>
          {currentSelected && (
            <AssetDetail asset={currentSelected} price={prices[currentSelected.id]} />
          )}
        </div>
      </div>
    </main>
  );
}
