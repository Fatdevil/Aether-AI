import { useState } from 'react';
// import { motion, AnimatePresence } from 'framer-motion';
import { TrendingUp, Globe2, Newspaper, BarChart3, Zap, WifiOff } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { api, type APISector, type APIRegion, type APINewsItem } from '../api/client';

// Local types for data shapes used in this page
interface CausalChain {
  trigger_event?: string;
  title?: string;
  current_step_description?: string;
  description?: string;
  portfolio_impact?: string;
  severity?: string;
}

interface Narrative {
  name?: string;
  title?: string;
  strength?: string;
  momentum?: string;
}

interface PipelineRun {
  status: string;
  run_number?: number;
  timestamp?: string;
  completed_at?: string;
  duration_seconds?: number;
  assets_analyzed?: number;
}

type SubTab = 'scenarios' | 'sectors' | 'news' | 'backtest';

export default function AnalysisPage() {
  const [activeTab, setActiveTab] = useState<SubTab>('scenarios');

  const tabs: { id: SubTab; label: string; icon: typeof TrendingUp; description: string }[] = [
    { id: 'scenarios', label: 'Scenarion', icon: Zap, description: 'Kausala kedjor & händelseförlopp' },
    { id: 'sectors', label: 'Sektorer & Regioner', icon: Globe2, description: 'Rotationssignaler' },
    { id: 'news', label: 'Nyheter', icon: Newspaper, description: 'Senaste med sentimentanalys' },
    { id: 'backtest', label: 'Historik', icon: BarChart3, description: 'Regimskiftens resultat' },
  ];

  return (
    <div className="container" style={{ padding: '2rem 1.25rem 6rem' }}>
      {/* Section Header */}
      <div style={{ marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '1.8rem', marginBottom: '0.25rem' }}>
          <span className="text-gradient">Analys</span>
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '1rem' }}>
          Djupdyk i marknaden — scenarion, sektorer och nyheter
        </p>
      </div>

      {/* Sub-tab Navigation */}
      <div style={{
        display: 'flex', gap: '0.5rem', marginBottom: '1.5rem',
        overflowX: 'auto', paddingBottom: '0.5rem',
      }}>
        {tabs.map(tab => {
          const TabIcon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                display: 'flex', alignItems: 'center', gap: '0.5rem',
                padding: '0.65rem 1.2rem',
                background: activeTab === tab.id
                  ? 'linear-gradient(135deg, rgba(79, 172, 254, 0.15), rgba(157, 78, 221, 0.15))'
                  : 'rgba(19, 20, 31, 0.4)',
                border: `1px solid ${activeTab === tab.id ? 'rgba(79, 172, 254, 0.3)' : 'rgba(255,255,255,0.08)'}`,
                borderRadius: '10px',
                color: activeTab === tab.id ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                cursor: 'pointer',
                fontFamily: 'var(--font-body)',
                fontSize: '0.9rem',
                fontWeight: activeTab === tab.id ? 600 : 400,
                whiteSpace: 'nowrap',
                transition: 'all 0.2s ease',
              }}
            >
              <TabIcon size={16} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      <div>
        {activeTab === 'scenarios' && <ScenariosTab />}
        {activeTab === 'sectors' && <SectorsTab />}
        {activeTab === 'news' && <NewsTab />}
        {activeTab === 'backtest' && <BacktestTab />}
      </div>
    </div>
  );
}

/* ── Scenarios Tab ── */
function ScenariosTab() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['predictive-summary'],
    queryFn: () => api.getPredictiveSummary(),
    staleTime: 60_000,
    retry: 1,
  });

  const { data: chains } = useQuery({
    queryKey: ['causal-chains'],
    queryFn: () => api.getCausalChainsActive(),
    staleTime: 60_000,
    retry: 1,
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState />;

  const activeChains = chains?.chains || [];
  const narratives = data?.narratives?.active_narratives || [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Active Causal Chains */}
      <div className="glass-panel" style={{ padding: '1.5rem' }}>
        <h3 style={{ fontSize: '1.1rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Zap size={18} color="var(--accent-gold)" />
          Aktiva kausala kedjor
        </h3>
        {activeChains.length > 0 ? activeChains.slice(0, 5).map((chain: CausalChain, i: number) => (
          <div key={i} style={{
            padding: '1rem',
            background: 'rgba(255,255,255,0.03)',
            borderRadius: '10px',
            marginBottom: '0.75rem',
            borderLeft: `3px solid ${chain.severity === 'CRITICAL' ? 'var(--score-negative)' : 'var(--accent-gold)'}`,
          }}>
            <div style={{ fontWeight: 600, marginBottom: '0.25rem' }}>{chain.trigger_event || chain.title || 'Händelse'}</div>
            <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
              {chain.current_step_description || chain.description || 'Analys pågår...'}
            </div>
            {typeof chain.portfolio_impact === 'string' && chain.portfolio_impact && (
              <div style={{ marginTop: '0.5rem', fontSize: '0.8rem', color: 'var(--accent-cyan)' }}>
                💼 Portföljpåverkan: {chain.portfolio_impact}
              </div>
            )}
          </div>
        )) : (
          <p style={{ color: 'var(--text-tertiary)', fontStyle: 'italic' }}>
            Inga aktiva kausala kedjor just nu. AI bevakar marknaden kontinuerligt.
          </p>
        )}
      </div>

      {/* Active Narratives */}
      <div className="glass-panel" style={{ padding: '1.5rem' }}>
        <h3 style={{ fontSize: '1.1rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          📖 Marknadens narrativ
        </h3>
        {narratives.length > 0 ? narratives.slice(0, 4).map((n: Narrative, i: number) => (
          <div key={i} style={{
            padding: '0.75rem 1rem',
            background: 'rgba(255,255,255,0.03)',
            borderRadius: '8px',
            marginBottom: '0.5rem',
          }}>
            <div style={{ fontWeight: 500 }}>{n.name || n.title}</div>
            <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginTop: '0.25rem' }}>
              Styrka: {n.strength || n.momentum || '—'}
            </div>
          </div>
        )) : (
          <p style={{ color: 'var(--text-tertiary)', fontStyle: 'italic' }}>
            Inga starka narrativ identifierade.
          </p>
        )}
      </div>
    </div>
  );
}

/* ── Sectors & Regions Tab ── */
function SectorsTab() {
  const { data: sectors, isLoading: loadSec, isError: errSec } = useQuery({
    queryKey: ['sectors'],
    queryFn: () => api.getSectors(),
    staleTime: 60_000,
    retry: 1,
  });
  const { data: regions, isLoading: loadReg, isError: errReg } = useQuery({
    queryKey: ['regions'],
    queryFn: () => api.getRegions(),
    staleTime: 60_000,
    retry: 1,
  });

  if (loadSec || loadReg) return <LoadingState />;
  if (errSec || errReg) return <ErrorState />;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Sectors */}
      <div className="glass-panel" style={{ padding: '1.5rem' }}>
        <h3 style={{ fontSize: '1.1rem', marginBottom: '1rem' }}>🏭 Sektorer</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '0.75rem' }}>
          {(sectors || []).map((s: APISector) => (
            <RotationCard key={s.id} item={s} />
          ))}
        </div>
      </div>

      {/* Regions */}
      <div className="glass-panel" style={{ padding: '1.5rem' }}>
        <h3 style={{ fontSize: '1.1rem', marginBottom: '1rem' }}>🌍 Regioner</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '0.75rem' }}>
          {(regions || []).map((r: APIRegion) => (
            <RotationCard key={r.id} item={r} />
          ))}
        </div>
      </div>
    </div>
  );
}

function RotationCard({ item }: { item: APISector | APIRegion }) {
  const signal = item.rotationSignal || item.allocationSignal || 'Neutralvikt';
  const signalColor = signal === 'Övervikt' ? 'var(--score-positive)' : signal === 'Undervikt' ? 'var(--score-negative)' : 'var(--score-neutral)';
  const changePct = item.changePct || 0;

  return (
    <div style={{
      padding: '1rem',
      background: 'rgba(255,255,255,0.03)',
      borderRadius: '10px',
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    }}>
      <div>
        <div style={{ fontWeight: 600, fontSize: '0.95rem' }}>
          {item.emoji || item.flag || ''} {item.name}
        </div>
        <div style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', marginTop: '0.2rem' }}>
          {item.ticker} · {changePct >= 0 ? '+' : ''}{changePct.toFixed(1)}%
        </div>
      </div>
      <span style={{
        padding: '0.25rem 0.65rem',
        borderRadius: '20px',
        fontSize: '0.75rem',
        fontWeight: 600,
        color: signalColor,
        background: `${signalColor}15`,
        border: `1px solid ${signalColor}30`,
      }}>
        {signal}
      </span>
    </div>
  );
}

/* ── News Tab ── */
function NewsTab() {
  const { data: news, isLoading, isError } = useQuery({
    queryKey: ['news'],
    queryFn: () => api.getNews(),
    staleTime: 30_000,
    retry: 1,
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState />;

  return (
    <div className="glass-panel" style={{ padding: '1.5rem' }}>
      <h3 style={{ fontSize: '1.1rem', marginBottom: '1rem' }}>📰 Senaste nyheterna</h3>
      {(news || []).slice(0, 15).map((n: APINewsItem, i: number) => {
        const sentColor = n.sentiment === 'positive' ? 'var(--score-positive)' : n.sentiment === 'negative' ? 'var(--score-negative)' : 'var(--text-tertiary)';
        const impact = n.impact?.score || 0;
        return (
          <a
            key={n.id || i}
            href={n.url}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: 'block',
              padding: '0.85rem 1rem',
              background: impact >= 7 ? 'rgba(255, 23, 68, 0.05)' : 'rgba(255,255,255,0.02)',
              borderRadius: '8px',
              marginBottom: '0.5rem',
              textDecoration: 'none',
              color: 'inherit',
              borderLeft: impact >= 7 ? '3px solid var(--score-negative)' : impact >= 4 ? '3px solid var(--accent-gold)' : '3px solid transparent',
              transition: 'background 0.2s ease',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '0.5rem' }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 500, fontSize: '0.9rem', lineHeight: 1.4 }}>{n.title}</div>
                <div style={{ color: 'var(--text-tertiary)', fontSize: '0.75rem', marginTop: '0.3rem', display: 'flex', gap: '0.75rem' }}>
                  <span>{n.source}</span>
                  <span>{n.time}</span>
                  <span style={{ color: sentColor }}>● {n.sentiment === 'positive' ? 'Positiv' : n.sentiment === 'negative' ? 'Negativ' : 'Neutral'}</span>
                </div>
              </div>
              {impact > 0 && (
                <span style={{
                  padding: '0.15rem 0.5rem', borderRadius: '4px', fontSize: '0.7rem', fontWeight: 700,
                  color: impact >= 7 ? 'var(--score-negative)' : 'var(--accent-gold)',
                  background: impact >= 7 ? 'rgba(255,23,68,0.1)' : 'rgba(255,215,0,0.1)',
                }}>
                  ⚡{impact}
                </span>
              )}
            </div>
          </a>
        );
      })}
    </div>
  );
}

/* ── Backtest Tab ── */
function BacktestTab() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['pipeline-history'],
    queryFn: () => api.getPipelineHistory(),
    staleTime: 120_000,
    retry: 1,
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState />;

  return (
    <div className="glass-panel" style={{ padding: '1.5rem' }}>
      <h3 style={{ fontSize: '1.1rem', marginBottom: '1rem' }}>📊 Pipeline-historik</h3>
      <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '1rem' }}>
        Senaste körningar av den autonoma AI-pipelinen
      </p>
      {(data?.history || []).slice(0, 10).map((run: PipelineRun, i: number) => (
        <div key={i} style={{
          padding: '0.75rem 1rem',
          background: 'rgba(255,255,255,0.03)',
          borderRadius: '8px',
          marginBottom: '0.5rem',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <div>
            <div style={{ fontWeight: 500, fontSize: '0.85rem' }}>
              {run.status === 'COMPLETE' ? '✅' : '❌'} Körning #{run.run_number || i + 1}
            </div>
            <div style={{ color: 'var(--text-tertiary)', fontSize: '0.75rem' }}>
              {run.timestamp || run.completed_at || '—'} · {run.duration_seconds || 0}s
            </div>
          </div>
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
            {run.events_detected || 0} händelser
          </div>
        </div>
      ))}
      {(!data?.history || data.history.length === 0) && (
        <p style={{ color: 'var(--text-tertiary)', fontStyle: 'italic' }}>Ingen historik tillgänglig ännu.</p>
      )}
    </div>
  );
}

/* ── Shared Loading ── */
function LoadingState() {
  return (
    <div style={{
      display: 'flex', justifyContent: 'center', alignItems: 'center',
      padding: '3rem', color: 'var(--text-tertiary)',
    }}>
      <div className="spin-animation" style={{
        width: 24, height: 24, border: '2px solid var(--glass-border)',
        borderTopColor: 'var(--accent-cyan)', borderRadius: '50%', marginRight: '0.75rem',
      }} />
      Laddar...
    </div>
  );
}

function ErrorState() {
  return (
    <div className="glass-panel" style={{ padding: '2.5rem', textAlign: 'center' }}>
      <WifiOff size={28} color="var(--text-tertiary)" style={{ marginBottom: '0.75rem' }} />
      <p style={{ color: 'var(--text-secondary)', margin: 0, fontSize: '0.95rem' }}>
        Backend är inte tillgänglig just nu
      </p>
      <p style={{ color: 'var(--text-tertiary)', margin: '0.5rem 0 0', fontSize: '0.8rem' }}>
        Starta backend på port 8000 för att se live-data
      </p>
    </div>
  );
}
