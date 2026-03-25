import { useState, useEffect } from 'react';
import { Activity, BarChart3, Brain, ChevronRight } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { Asset } from '../types';
import { getScoreColor } from '../types';
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

      {/* Supervisor Summary */}
      <section className="glass-panel animate-fade-in" style={{ padding: '2rem', marginBottom: '2rem' }}>
        <div className="flex items-center gap-4" style={{ marginBottom: '1rem', flexWrap: 'wrap' }}>
          <Activity className="pulse-glow" size={32} color="var(--accent-purple)" style={{ borderRadius: '50%' }} />
          <div style={{ flex: 1 }}>
            <div className="flex items-center gap-2" style={{ flexWrap: 'wrap' }}>
              <h2 style={{ fontSize: '1.6rem', margin: 0 }}>Supervisor Marknadssyn</h2>
              <span style={{
                fontSize: '1.4rem',
                fontWeight: 700,
                color: `var(--score-${getScoreColor(marketState.overallScore)})`,
              }}>
                {marketState.overallScore > 0 ? '+' : ''}{marketState.overallScore.toFixed(1)}
              </span>
            </div>
            <p style={{ color: 'var(--text-tertiary)', margin: 0, fontSize: '0.85rem' }}>
              Väger samman 4x AI Modeller × {assets.length} tillgångar • Uppdaterad {marketState.lastUpdated}
            </p>
          </div>
        </div>
        <p style={{ fontSize: '1rem', maxWidth: '900px', lineHeight: '1.8', color: 'var(--text-secondary)' }}>
          "{marketState.overallSummary}"
        </p>
      </section>

      {/* Intelligence Widgets */}
      <div className="animate-fade-in" style={{ marginBottom: '2rem', animationDelay: '0.05s' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1fr) minmax(0, 2fr)', gap: '1rem', marginBottom: '0rem' }}>
          <CalendarWidget />
          <TrendingWidget />
          <PredictivePulse />
          <CorrelationHeatmap />
        </div>
      </div>

      {/* Main Grid */}
      <div className="dashboard-grid">
        {/* Asset List */}
        <div className="asset-list-col animate-fade-in" style={{ animationDelay: '0.1s' }}>
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            <BarChart3 size={20} color="var(--accent-blue)" /> Överblick ({assets.length})
          </h3>
          <div className="flex flex-col gap-4">
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
