import { useState, useEffect, useCallback } from 'react';
import { Activity, Brain, Target, TrendingUp, Zap, CheckCircle, XCircle, BarChart3, Database } from 'lucide-react';

interface AgentStats {
  accuracy_direction: number;
  avg_magnitude_error: number;
  total_predictions: number;
  correct_predictions: number;
  bias: number;
  calibration_error: number;
}

interface PerformanceData {
  database_stats: {
    total: number;
    assets: number;
    sectors: number;
    regions: number;
    snapshots_filled: number;
    evaluations: number;
  };
  agent_accuracy: Record<string, Record<string, AgentStats>>;
  timeframe_summaries: Record<string, { total: number; correct: number; accuracy: number; avg_magnitude_error: number }>;
  best_predictions: any[];
  worst_predictions: any[];
}

const AGENT_LABELS: Record<string, { label: string; icon: string }> = {
  macro: { label: 'Makro', icon: '🌍' },
  micro: { label: 'Mikro', icon: '🔬' },
  sentiment: { label: 'Sentiment', icon: '📰' },
  tech: { label: 'Teknisk', icon: '📊' },
  supervisor: { label: 'Supervisor', icon: '🧠' },
};

export default function PerformancePage() {
  const [data, setData] = useState<PerformanceData | null>(null);
  const [period, setPeriod] = useState<'7d' | '30d' | 'all'>('all');
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const resp = await fetch('http://localhost:8000/api/performance');
      const json = await resp.json();
      setData(json);
    } catch { /* Backend might not be running */ }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  if (loading) return (
    <main className="container" style={{ paddingTop: '2rem', paddingBottom: '6rem', textAlign: 'center' }}>
      <Brain size={48} color="var(--accent-cyan)" style={{ animation: 'pulse 2s infinite' }} />
      <p style={{ color: 'var(--text-tertiary)', marginTop: '1rem' }}>Laddar AI-prestanda...</p>
    </main>
  );

  if (!data) return (
    <main className="container" style={{ paddingTop: '2rem', paddingBottom: '6rem' }}>
      <div className="glass-panel" style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-tertiary)' }}>
        <Database size={40} style={{ marginBottom: '0.5rem', opacity: 0.5 }} />
        <p>Ingen data tillgänglig ännu. Systemet sparar analyser automatiskt.</p>
      </div>
    </main>
  );

  const db = data.database_stats;

  const getAccuracyColor = (acc: number) => {
    if (acc >= 70) return '#2ed573';
    if (acc >= 50) return '#ffd93d';
    return '#ff4757';
  };

  const getBiasLabel = (bias: number) => {
    if (bias > 1.5) return { text: 'Bullish', color: '#2ed573' };
    if (bias < -1.5) return { text: 'Bearish', color: '#ff4757' };
    return { text: 'Neutral', color: 'var(--text-tertiary)' };
  };

  return (
    <main className="container" style={{ paddingTop: '2rem', paddingBottom: '6rem' }}>
      {/* Header */}
      <div className="flex items-center gap-2" style={{ marginBottom: '0.5rem' }}>
        <Activity size={28} color="var(--accent-purple)" />
        <h2 style={{ margin: 0, fontSize: '1.8rem' }}>AI Prestanda</h2>
      </div>
      <p style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)', marginBottom: '1.5rem' }}>
        Utvärdering av AI-modellernas träffsäkerhet baserat på verkliga marknadsutfall
      </p>

      {/* Database Stats */}
      <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: '0.75rem', marginBottom: '1.5rem' }}>
        {[
          { label: 'Analyser', value: db.total, icon: <Brain size={16} />, color: 'var(--accent-cyan)' },
          { label: 'Tillgångar', value: db.assets, icon: <BarChart3 size={16} />, color: 'var(--accent-blue)' },
          { label: 'Snapshots', value: db.snapshots_filled, icon: <Database size={16} />, color: '#a55eea' },
          { label: 'Utvärderingar', value: db.evaluations, icon: <Target size={16} />, color: '#ffd93d' },
        ].map((stat, i) => (
          <div key={i} className="glass-panel" style={{ padding: '0.8rem', textAlign: 'center' }}>
            <div style={{ color: stat.color, marginBottom: '0.2rem' }}>{stat.icon}</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 700 }}>{stat.value}</div>
            <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)' }}>{stat.label}</div>
          </div>
        ))}
      </div>

      {/* Period selector */}
      <div className="flex items-center gap-2" style={{ marginBottom: '1.5rem' }}>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>Period:</span>
        {(['7d', '30d', 'all'] as const).map(p => (
          <button key={p} onClick={() => setPeriod(p)} className="glass-panel" style={{
            padding: '0.3rem 0.7rem', fontSize: '0.8rem', cursor: 'pointer',
            border: `1px solid ${period === p ? 'var(--accent-cyan)' : 'var(--glass-border)'}`,
            color: period === p ? 'var(--accent-cyan)' : 'var(--text-secondary)',
            fontWeight: period === p ? 700 : 400,
          }}>
            {p === 'all' ? 'Totalt' : p}
          </button>
        ))}
      </div>

      {/* Agent Accuracy Cards */}
      <h3 style={{ fontSize: '1.1rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <Zap size={18} color="var(--accent-gold)" /> Agent-träffsäkerhet
      </h3>
      <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem', marginBottom: '2rem' }}>
        {Object.entries(AGENT_LABELS).map(([key, info]) => {
          const agentData = data.agent_accuracy[key]?.[period];
          const total = agentData?.total_predictions || 0;
          const accuracy = total > 0 ? Math.round((agentData?.accuracy_direction || 0) * 100) : 0;
          const bias = agentData?.bias || 0;
          const biasInfo = getBiasLabel(bias);

          return (
            <div key={key} className="glass-panel" style={{
              padding: '1.25rem',
              borderTop: `3px solid ${total > 0 ? getAccuracyColor(accuracy) : 'var(--glass-border)'}`,
            }}>
              <div className="flex items-center justify-between" style={{ marginBottom: '0.75rem' }}>
                <span style={{ fontSize: '1.1rem' }}>{info.icon} {info.label}</span>
                {total > 0 && (
                  <span style={{
                    fontSize: '1.5rem', fontWeight: 700,
                    color: getAccuracyColor(accuracy),
                  }}>
                    {accuracy}%
                  </span>
                )}
              </div>

              {total > 0 ? (
                <>
                  {/* Accuracy bar */}
                  <div style={{ height: '6px', background: 'rgba(255,255,255,0.05)', borderRadius: '3px', marginBottom: '0.75rem', overflow: 'hidden' }}>
                    <div style={{
                      height: '100%', width: `${accuracy}%`,
                      background: `linear-gradient(90deg, ${getAccuracyColor(accuracy)}, ${getAccuracyColor(accuracy)}88)`,
                      borderRadius: '3px', transition: 'width 0.5s ease',
                    }} />
                  </div>

                  <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', lineHeight: 1.8 }}>
                    <div className="flex justify-between">
                      <span>Prediktioner</span>
                      <span style={{ color: 'var(--text-secondary)' }}>{total}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Korrekta</span>
                      <span style={{ color: '#2ed573' }}>{agentData?.correct_predictions || 0}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Bias</span>
                      <span style={{ color: biasInfo.color }}>{bias > 0 ? '+' : ''}{bias.toFixed(1)} ({biasInfo.text})</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Magn. fel</span>
                      <span style={{ color: 'var(--text-secondary)' }}>{(agentData?.avg_magnitude_error || 0).toFixed(1)}</span>
                    </div>
                  </div>
                </>
              ) : (
                <p style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)', margin: 0, textAlign: 'center', padding: '1rem 0' }}>
                  Inväntar data...
                </p>
              )}
            </div>
          );
        })}
      </div>

      {/* Timeframe Comparison */}
      <h3 style={{ fontSize: '1.1rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <Target size={18} color="var(--accent-cyan)" /> Träffsäkerhet per tidshorisont
      </h3>
      <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.75rem', marginBottom: '2rem' }}>
        {['1h', '4h', '24h', '48h', '7d'].map(tf => {
          const tfData = data.timeframe_summaries[tf];
          return (
            <div key={tf} className="glass-panel" style={{ padding: '1rem', textAlign: 'center' }}>
              <div style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--text-secondary)' }}>
                {tf === '1h' ? '1 timme' : tf === '4h' ? '4 timmar' : tf === '24h' ? '24 timmar' : tf === '48h' ? '2 dagar' : '7 dagar'}
              </div>
              <div style={{
                fontSize: '1.8rem', fontWeight: 700,
                color: (tfData?.total || 0) > 0 ? getAccuracyColor(tfData?.accuracy || 0) : 'var(--text-tertiary)',
              }}>
                {(tfData?.total || 0) > 0 ? `${tfData?.accuracy}%` : '—'}
              </div>
              <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)' }}>
                {tfData?.total || 0} analyser
              </div>
            </div>
          );
        })}
      </div>

      {/* Best & Worst Predictions */}
      {(data.best_predictions.length > 0 || data.worst_predictions.length > 0) && (
        <>
          <h3 style={{ fontSize: '1.1rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <TrendingUp size={18} color="#2ed573" /> Bästa & sämsta prediktioner
          </h3>
          <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1rem' }}>
            {/* Best */}
            <div className="glass-panel" style={{ padding: '1.25rem', borderLeft: '3px solid #2ed573' }}>
              <h4 style={{ margin: '0 0 0.75rem', fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <CheckCircle size={16} color="#2ed573" /> Bästa träffar
              </h4>
              {data.best_predictions.length === 0 ? (
                <p style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)', margin: 0 }}>Inväntar utvärderingar...</p>
              ) : (
                data.best_predictions.map((p, i) => (
                  <div key={i} style={{ fontSize: '0.8rem', padding: '0.4rem 0', borderBottom: '1px solid var(--glass-border)' }}>
                    <div className="flex justify-between">
                      <span style={{ fontWeight: 600 }}>{p.asset_name || p.asset_id}</span>
                      <span style={{ color: '#2ed573' }}>{p.actual_change_pct > 0 ? '+' : ''}{p.actual_change_pct?.toFixed(2)}%</span>
                    </div>
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>
                      Score: {p.score_at_analysis?.toFixed(1)} → Verkligt: {p.actual_change_pct?.toFixed(2)}%
                    </span>
                  </div>
                ))
              )}
            </div>

            {/* Worst */}
            <div className="glass-panel" style={{ padding: '1.25rem', borderLeft: '3px solid #ff4757' }}>
              <h4 style={{ margin: '0 0 0.75rem', fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <XCircle size={16} color="#ff4757" /> Sämsta missar
              </h4>
              {data.worst_predictions.length === 0 ? (
                <p style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)', margin: 0 }}>Inväntar utvärderingar...</p>
              ) : (
                data.worst_predictions.map((p, i) => (
                  <div key={i} style={{ fontSize: '0.8rem', padding: '0.4rem 0', borderBottom: '1px solid var(--glass-border)' }}>
                    <div className="flex justify-between">
                      <span style={{ fontWeight: 600 }}>{p.asset_name || p.asset_id}</span>
                      <span style={{ color: '#ff4757' }}>{p.actual_change_pct > 0 ? '+' : ''}{p.actual_change_pct?.toFixed(2)}%</span>
                    </div>
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>
                      Score: {p.score_at_analysis?.toFixed(1)} → Verkligt: {p.actual_change_pct?.toFixed(2)}%
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}

      {/* Learning info */}
      <div className="glass-panel" style={{ padding: '1.25rem', marginTop: '1.5rem', borderLeft: '3px solid var(--accent-purple)' }}>
        <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <Brain size={16} color="var(--accent-purple)" /> Adaptivt lärande
        </h4>
        <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.6 }}>
          Systemet sparar varje analys och jämför mot verkliga marknadsutfall. 
          Agenter med låg träffsäkerhet viktas automatiskt ned, och alla agenter 
          får feedback om sin historiska prestation i sina promptar. 
          Ju mer data desto bättre blir prognosen.
        </p>
      </div>
    </main>
  );
}
