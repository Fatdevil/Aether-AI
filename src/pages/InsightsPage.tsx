import { useState } from 'react';
// import { motion, AnimatePresence } from 'framer-motion';
import { Brain, Shield, History, Users, ChevronDown, ChevronUp } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';

type SubTab = 'supervisor' | 'agents' | 'performance' | 'adversarial';

export default function InsightsPage() {
  const [activeTab, setActiveTab] = useState<SubTab>('supervisor');

  const tabs: { id: SubTab; label: string; icon: typeof Brain }[] = [
    { id: 'supervisor', label: 'AI Motivering', icon: Brain },
    { id: 'agents', label: 'Agentpoäng', icon: Users },
    { id: 'performance', label: 'Prestanda', icon: History },
    { id: 'adversarial', label: 'Motargument', icon: Shield },
  ];

  return (
    <div className="container" style={{ padding: '2rem 1.25rem 6rem' }}>
      <div style={{ marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '1.8rem', marginBottom: '0.25rem' }}>
          <span className="text-gradient-purple">AI Insikter</span>
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '1rem' }}>
          Hur AI:n tänker — agenternas resonemang och historisk prestanda
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
                  ? 'linear-gradient(135deg, rgba(157, 78, 221, 0.15), rgba(255, 0, 127, 0.15))'
                  : 'rgba(19, 20, 31, 0.4)',
                border: `1px solid ${activeTab === tab.id ? 'rgba(157, 78, 221, 0.3)' : 'rgba(255,255,255,0.08)'}`,
                borderRadius: '10px',
                color: activeTab === tab.id ? 'var(--accent-purple)' : 'var(--text-secondary)',
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

      <div>
        {activeTab === 'supervisor' && <SupervisorTab />}
        {activeTab === 'agents' && <AgentsTab />}
        {activeTab === 'performance' && <PerformanceTab />}
        {activeTab === 'adversarial' && <AdversarialTab />}
      </div>
    </div>
  );
}

/* ── Supervisor Reasoning ── */
function SupervisorTab() {
  const { data: assets, isLoading } = useQuery({
    queryKey: ['assets'],
    queryFn: () => api.getAssets(),
    staleTime: 30_000,
  });

  const { data: autoStatus } = useQuery({
    queryKey: ['auto-status'],
    queryFn: () => api.getAutoStatus(),
    staleTime: 60_000,
  });

  if (isLoading) return <LoadingState />;

  // Sort by absolute score DESC
  const sorted = [...(assets || [])].sort((a: any, b: any) => Math.abs(b.finalScore) - Math.abs(a.finalScore));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Pipeline Status */}
      {autoStatus && (
        <div className="glass-panel" style={{ padding: '1.25rem' }}>
          <h3 style={{ fontSize: '1rem', marginBottom: '0.75rem' }}>🤖 Autonom Pipeline</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.75rem' }}>
            <MiniStat label="Körningar" value={autoStatus.pipeline_run_count || 0} />
            <MiniStat label="Senaste" value={autoStatus.last_pipeline_run ? new Date(autoStatus.last_pipeline_run).toLocaleTimeString('sv-SE') : '—'} />
            <MiniStat label="Status" value={autoStatus.last_pipeline_status || 'Väntar'} />
          </div>
        </div>
      )}

      {/* Top Supervisor Recommendations */}
      <div className="glass-panel" style={{ padding: '1.5rem' }}>
        <h3 style={{ fontSize: '1.1rem', marginBottom: '1rem' }}>🧠 Supervisor — Top rekommendationer</h3>
        {sorted.slice(0, 8).map((asset: any) => (
          <AssetInsightCard key={asset.id} asset={asset} />
        ))}
      </div>
    </div>
  );
}

function AssetInsightCard({ asset }: { asset: any }) {
  const [expanded, setExpanded] = useState(false);
  const score = asset.finalScore || 0;
  const scoreColor = score > 2 ? 'var(--score-positive)' : score < -2 ? 'var(--score-negative)' : 'var(--score-neutral)';
  const AssetIcon = asset.icon;

  return (
    <div
      style={{
        padding: '1rem',
        background: 'rgba(255,255,255,0.03)',
        borderRadius: '10px',
        marginBottom: '0.75rem',
        cursor: 'pointer',
        transition: 'background 0.2s ease',
      }}
      onClick={() => setExpanded(!expanded)}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <AssetIcon size={18} color={asset.color} />
          <div>
            <div style={{ fontWeight: 600, fontSize: '0.95rem' }}>{asset.name}</div>
            <div style={{ color: 'var(--text-tertiary)', fontSize: '0.8rem' }}>
              {score > 0 ? 'Positiv' : score < 0 ? 'Negativ' : 'Neutral'} signal
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span style={{ fontWeight: 700, fontSize: '1.1rem', color: scoreColor }}>
            {score > 0 ? '+' : ''}{score.toFixed(1)}
          </span>
          {expanded ? <ChevronUp size={16} color="var(--text-tertiary)" /> : <ChevronDown size={16} color="var(--text-tertiary)" />}
        </div>
      </div>

      {expanded && (
        <div
          style={{ marginTop: '0.75rem', paddingTop: '0.75rem', borderTop: '1px solid var(--glass-border)' }}
        >
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', lineHeight: 1.6 }}>
            {asset.supervisorText || 'Ingen detaljerad motivering tillgänglig.'}
          </p>
          {asset.agentDetails && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '0.5rem', marginTop: '0.75rem' }}>
              {['macro', 'micro', 'sentiment', 'tech'].map(agent => {
                const detail = asset.agentDetails?.[agent];
                if (!detail) return null;
                const agentScore = asset.scores?.[agent] || 0;
                const color = agentScore > 0 ? 'var(--score-positive)' : agentScore < 0 ? 'var(--score-negative)' : 'var(--text-tertiary)';
                return (
                  <div key={agent} style={{
                    padding: '0.5rem 0.75rem',
                    background: 'rgba(255,255,255,0.03)',
                    borderRadius: '6px',
                    fontSize: '0.8rem',
                  }}>
                    <div style={{ fontWeight: 600, textTransform: 'capitalize', color }}>
                      {agent} {agentScore > 0 ? '+' : ''}{agentScore.toFixed(1)}
                    </div>
                    <div style={{ color: 'var(--text-tertiary)', fontSize: '0.75rem', marginTop: '0.2rem' }}>
                      {detail.reasoning?.substring(0, 80) || '—'}...
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ── Agents Tab ── */
function AgentsTab() {
  const { data: assets, isLoading } = useQuery({
    queryKey: ['assets'],
    queryFn: () => api.getAssets(),
    staleTime: 30_000,
  });

  if (isLoading) return <LoadingState />;

  return (
    <div className="glass-panel" style={{ padding: '1.5rem' }}>
      <h3 style={{ fontSize: '1.1rem', marginBottom: '1rem' }}>📊 Agentpoäng per tillgång</h3>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--glass-border)' }}>
              <th style={{ textAlign: 'left', padding: '0.75rem 0.5rem', color: 'var(--text-secondary)' }}>Tillgång</th>
              <th style={{ textAlign: 'center', padding: '0.75rem 0.5rem', color: 'var(--text-secondary)' }}>Makro</th>
              <th style={{ textAlign: 'center', padding: '0.75rem 0.5rem', color: 'var(--text-secondary)' }}>Mikro</th>
              <th style={{ textAlign: 'center', padding: '0.75rem 0.5rem', color: 'var(--text-secondary)' }}>Sentiment</th>
              <th style={{ textAlign: 'center', padding: '0.75rem 0.5rem', color: 'var(--text-secondary)' }}>Teknisk</th>
              <th style={{ textAlign: 'center', padding: '0.75rem 0.5rem', color: 'var(--accent-cyan)', fontWeight: 700 }}>Total</th>
            </tr>
          </thead>
          <tbody>
            {(assets || []).map((a: any) => (
              <tr key={a.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                <td style={{ padding: '0.6rem 0.5rem', fontWeight: 500 }}><AssetIconInline icon={a.icon} color={a.color || 'var(--text-secondary)'} /> {a.name}</td>
                <td style={{ textAlign: 'center', padding: '0.6rem 0.5rem' }}><ScorePill value={a.scores?.macro} /></td>
                <td style={{ textAlign: 'center', padding: '0.6rem 0.5rem' }}><ScorePill value={a.scores?.micro} /></td>
                <td style={{ textAlign: 'center', padding: '0.6rem 0.5rem' }}><ScorePill value={a.scores?.sentiment} /></td>
                <td style={{ textAlign: 'center', padding: '0.6rem 0.5rem' }}><ScorePill value={a.scores?.tech} /></td>
                <td style={{ textAlign: 'center', padding: '0.6rem 0.5rem' }}><ScorePill value={a.finalScore} bold /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ScorePill({ value, bold }: { value?: number; bold?: boolean }) {
  const v = value || 0;
  const color = v > 1 ? 'var(--score-positive)' : v < -1 ? 'var(--score-negative)' : 'var(--text-tertiary)';
  return (
    <span style={{
      color,
      fontWeight: bold ? 700 : 500,
      fontSize: bold ? '0.9rem' : '0.8rem',
    }}>
      {v > 0 ? '+' : ''}{v.toFixed(1)}
    </span>
  );
}

/* ── Performance Tab ── */
function PerformanceTab() {
  const { data: confidence } = useQuery({
    queryKey: ['confidence'],
    queryFn: () => api.getConfidence(),
    staleTime: 120_000,
  });

  const { data: meta } = useQuery({
    queryKey: ['meta-strategy'],
    queryFn: () => api.getMetaStrategy(),
    staleTime: 120_000,
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Confidence Calibration */}
      <div className="glass-panel" style={{ padding: '1.5rem' }}>
        <h3 style={{ fontSize: '1.1rem', marginBottom: '1rem' }}>🎯 Konfidens-kalibrering</h3>
        {confidence?.calibration ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.75rem' }}>
            <MiniStat label="Brier Score" value={confidence.calibration.brier_score?.toFixed(3) || '—'} />
            <MiniStat label="Prediktioner" value={confidence.calibration.n_predictions || 0} />
            <MiniStat label="Kalibrering" value={confidence.calibration.calibration_quality || '—'} />
          </div>
        ) : (
          <p style={{ color: 'var(--text-tertiary)', fontStyle: 'italic' }}>Inte tillräckligt med data ännu.</p>
        )}
      </div>

      {/* Meta Strategy */}
      <div className="glass-panel" style={{ padding: '1.5rem' }}>
        <h3 style={{ fontSize: '1.1rem', marginBottom: '1rem' }}>⚖️ Metodvikter</h3>
        {meta?.weights ? (
          Object.entries(meta.weights).map(([method, weight]: [string, any]) => (
            <div key={method} style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '0.5rem 0',
              borderBottom: '1px solid rgba(255,255,255,0.04)',
            }}>
              <span style={{ fontSize: '0.85rem', textTransform: 'capitalize' }}>{method.replace(/_/g, ' ')}</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <div style={{
                  width: '60px', height: '6px', background: 'var(--bg-tertiary)',
                  borderRadius: '3px', overflow: 'hidden',
                }}>
                  <div style={{
                    width: `${(typeof weight === 'number' ? weight : 0) * 100}%`,
                    height: '100%', background: 'var(--accent-purple)', borderRadius: '3px',
                  }} />
                </div>
                <span style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', width: '35px', textAlign: 'right' }}>
                  {(typeof weight === 'number' ? weight * 100 : 0).toFixed(0)}%
                </span>
              </div>
            </div>
          ))
        ) : (
          <p style={{ color: 'var(--text-tertiary)', fontStyle: 'italic' }}>Metodvikter ej beräknade ännu.</p>
        )}
      </div>
    </div>
  );
}

/* ── Adversarial Tab ── */
function AdversarialTab() {
  const { data: assets } = useQuery({
    queryKey: ['assets'],
    queryFn: () => api.getAssets(),
    staleTime: 30_000,
  });

  // Show strong signals that could be challenged
  const strong = (assets || []).filter((a: any) => Math.abs(a.finalScore || 0) > 3);

  return (
    <div className="glass-panel" style={{ padding: '1.5rem' }}>
      <h3 style={{ fontSize: '1.1rem', marginBottom: '0.5rem' }}>🛡️ Djävulens Advokat</h3>
      <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '1rem' }}>
        AI utmanar sina egna starka rekommendationer för att hitta blinda fläckar.
      </p>
      {strong.length > 0 ? strong.map((asset: any) => {
        const AssetIcon2 = asset.icon;
        const score = asset.finalScore || 0;
        return (
          <div key={asset.id} style={{
            padding: '1rem',
            background: 'rgba(255,255,255,0.03)',
            borderRadius: '10px',
            marginBottom: '0.75rem',
            borderLeft: `3px solid ${score > 0 ? 'var(--score-positive)' : 'var(--score-negative)'}`,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <span style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.4rem' }}><AssetIcon2 size={16} color={asset.color || 'var(--text-secondary)'} /> {asset.name}</span>
              <span style={{
                fontWeight: 700,
                color: score > 0 ? 'var(--score-positive)' : 'var(--score-negative)',
              }}>
                {score > 0 ? 'KÖP' : 'SÄLJ'} ({score > 0 ? '+' : ''}{score.toFixed(1)})
              </span>
            </div>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
              Stark signal — adversarial-granskning sker automatiskt i pipeline.
            </p>
          </div>
        );
      }) : (
        <p style={{ color: 'var(--text-tertiary)', fontStyle: 'italic' }}>
          Inga tillräckligt starka signaler (±3) att utmana just nu.
        </p>
      )}
    </div>
  );
}

/* ── Shared Components ── */
function MiniStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div style={{
      padding: '0.75rem',
      background: 'rgba(255,255,255,0.03)',
      borderRadius: '8px',
      textAlign: 'center',
    }}>
      <div style={{ color: 'var(--text-tertiary)', fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{label}</div>
      <div style={{ fontWeight: 600, fontSize: '1rem', marginTop: '0.25rem' }}>{value}</div>
    </div>
  );
}

function AssetIconInline({ icon: Icon, color }: { icon: any; color: string }) {
  if (typeof Icon === 'function') {
    return <Icon size={14} color={color} style={{ display: 'inline', verticalAlign: 'middle', marginRight: '0.3rem' }} />;
  }
  return <span>{String(Icon)}</span>;
}

function LoadingState() {
  return (
    <div style={{
      display: 'flex', justifyContent: 'center', alignItems: 'center',
      padding: '3rem', color: 'var(--text-tertiary)',
    }}>
      <div className="spin-animation" style={{
        width: 24, height: 24, border: '2px solid var(--glass-border)',
        borderTopColor: 'var(--accent-purple)', borderRadius: '50%', marginRight: '0.75rem',
      }} />
      Laddar...
    </div>
  );
}
