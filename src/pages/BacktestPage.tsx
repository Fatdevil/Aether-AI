import { useState, useEffect } from 'react';
import { Target, TrendingUp, TrendingDown, BarChart2, Brain, RefreshCw } from 'lucide-react';

interface BacktestData {
  database_stats: {
    total: number; assets: number; sectors: number;
    regions: number; snapshots_filled: number; evaluations: number;
  };
  timeframe_summaries: Record<string, {
    total: number; correct: number; accuracy: number;
    avg_magnitude_error: number; avg_actual_change: number;
  }>;
  agent_accuracy: Record<string, Record<string, {
    accuracy_direction: number; total_predictions: number;
    correct_predictions: number; bias: number;
    avg_magnitude_error: number; calibration_error: number;
  }>>;
  best_predictions: any[];
  worst_predictions: any[];
}

export default function BacktestPage() {
  const [data, setData] = useState<BacktestData | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await fetch('http://localhost:8000/api/backtest');
      setData(await res.json());
    } catch (e) {
      console.error('Failed to fetch backtest data:', e);
    }
    setLoading(false);
  };

  useEffect(() => { fetchData(); }, []);

  const getAccuracyColor = (acc: number) => {
    if (acc >= 70) return '#10b981';
    if (acc >= 50) return '#f59e0b';
    return '#ef4444';
  };

  const getAccuracyLabel = (acc: number) => {
    if (acc >= 70) return 'Utmärkt';
    if (acc >= 55) return 'Bra';
    if (acc >= 45) return 'Medel';
    return 'Svag';
  };

  if (loading) {
    return (
      <main className="container" style={{ padding: '2rem 0' }}>
        <div className="glass-panel" style={{ padding: '3rem', textAlign: 'center' }}>
          <RefreshCw size={32} className="spin" style={{ color: 'var(--accent-cyan)', margin: '0 auto 1rem' }} />
          <p style={{ color: 'var(--text-secondary)' }}>Laddar backtestdata...</p>
        </div>
      </main>
    );
  }

  if (!data) return null;

  const stats = data.database_stats;
  const tfLabels: Record<string, string> = {
    '1h': '1 timme', '4h': '4 timmar', '24h': '24 timmar',
    '48h': '48 timmar', '7d': '7 dagar',
  };

  return (
    <main className="container" style={{ padding: '2rem 0' }}>
      {/* Title */}
      <div className="flex justify-between items-center" style={{ marginBottom: '2rem' }}>
        <div>
          <h2 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Target size={24} style={{ color: 'var(--accent-cyan)' }} />
            AI Backtest
          </h2>
          <p style={{ margin: '0.25rem 0 0', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
            Hur träffsäker har AI-analyserna varit?
          </p>
        </div>
        <button onClick={fetchData} className="glass-panel" style={{
          padding: '0.5rem 1rem', cursor: 'pointer', border: '1px solid var(--glass-border)',
          background: 'rgba(0, 242, 254, 0.05)', color: 'var(--accent-cyan)',
          borderRadius: '8px', fontSize: '0.8rem',
        }}>
          <RefreshCw size={14} style={{ marginRight: '0.3rem' }} /> Uppdatera
        </button>
      </div>

      {/* Stats overview */}
      <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.75rem', marginBottom: '2rem' }}>
        {[
          { label: 'Totala analyser', value: stats.total, color: 'var(--accent-cyan)' },
          { label: 'Tillgångar', value: stats.assets, color: '#a78bfa' },
          { label: 'Sektorer', value: stats.sectors, color: '#f59e0b' },
          { label: 'Regioner', value: stats.regions, color: '#34d399' },
          { label: 'Prisuppföljningar', value: stats.snapshots_filled, color: '#60a5fa' },
          { label: 'Utvärderingar', value: stats.evaluations, color: '#f472b6' },
        ].map(s => (
          <div key={s.label} className="glass-panel" style={{ padding: '0.8rem', textAlign: 'center' }}>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: s.color }}>{s.value}</div>
            <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)' }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Ensemble Status */}
      <EnsembleIndicator />

      {/* Accuracy by timeframe */}
      <div className="glass-panel" style={{ padding: '1.25rem', marginBottom: '1.5rem' }}>
        <h3 style={{ margin: '0 0 1rem', fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <BarChart2 size={18} style={{ color: 'var(--accent-cyan)' }} />
          Träffsäkerhet per tidshorisont
        </h3>

        {stats.evaluations === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-tertiary)' }}>
            <p style={{ fontSize: '0.9rem', margin: '0 0 0.5rem' }}>📊 Inga utvärderingar ännu</p>
            <p style={{ fontSize: '0.75rem', margin: 0 }}>
              Systemet börjar utvärdera analyser efter 1h, 4h, 24h, 48h och 7d.
              <br />Återkom om några timmar för de första resultaten!
            </p>
          </div>
        ) : (
          <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '0.75rem' }}>
            {Object.entries(data.timeframe_summaries).map(([tf, tfData]) => (
              <div key={tf} style={{
                padding: '1rem', borderRadius: '8px',
                background: 'rgba(255,255,255,0.02)', border: '1px solid var(--glass-border)',
              }}>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', marginBottom: '0.5rem' }}>
                  {tfLabels[tf] || tf}
                </div>
                <div style={{
                  fontSize: '2rem', fontWeight: 700,
                  color: tfData.total > 0 ? getAccuracyColor(tfData.accuracy) : 'var(--text-tertiary)',
                }}>
                  {tfData.total > 0 ? `${tfData.accuracy}%` : '—'}
                </div>
                <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)' }}>
                  {tfData.total > 0
                    ? `${tfData.correct}/${tfData.total} rätt · ${getAccuracyLabel(tfData.accuracy)}`
                    : 'Väntar på data'}
                </div>
                {tfData.total > 0 && (
                  <div style={{
                    marginTop: '0.5rem', height: '4px', borderRadius: '2px',
                    background: 'rgba(255,255,255,0.05)', overflow: 'hidden',
                  }}>
                    <div style={{
                      height: '100%', borderRadius: '2px',
                      width: `${tfData.accuracy}%`,
                      background: getAccuracyColor(tfData.accuracy),
                      transition: 'width 0.5s ease',
                    }} />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Per-agent accuracy */}
      <div className="glass-panel" style={{ padding: '1.25rem', marginBottom: '1.5rem' }}>
        <h3 style={{ margin: '0 0 1rem', fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Brain size={18} style={{ color: '#a78bfa' }} />
          Agenternas träffsäkerhet
        </h3>
        <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem' }}>
          {Object.entries(data.agent_accuracy)
            .filter(([agent]) => agent !== 'supervisor')
            .map(([agent, periods]) => {
              // Use "all" period for display
              const allStats = periods?.all || periods?.['30d'] || { accuracy_direction: 0, total_predictions: 0, correct_predictions: 0, bias: 0 };
              const accuracy = (allStats.accuracy_direction || 0) * 100;
              const hasData = allStats.total_predictions > 0;
              const agentLabels: Record<string, string> = {
                macro: '🌍 Makro', micro: '🔬 Mikro',
                sentiment: '💬 Sentiment', tech: '📊 Teknisk',
              };
              return (
                <div key={agent} style={{
                  padding: '1rem', borderRadius: '8px',
                  background: 'rgba(255,255,255,0.02)', border: '1px solid var(--glass-border)',
                }}>
                  <div style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.5rem' }}>
                    {agentLabels[agent] || agent}
                  </div>
                  <div style={{
                    fontSize: '1.5rem', fontWeight: 700,
                    color: hasData ? getAccuracyColor(accuracy) : 'var(--text-tertiary)',
                  }}>
                    {hasData ? `${accuracy.toFixed(0)}%` : '—'}
                  </div>
                  <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)' }}>
                    {hasData
                      ? `${allStats.correct_predictions}/${allStats.total_predictions} · bias: ${(allStats.bias || 0) > 0 ? '+' : ''}${((allStats.bias || 0)).toFixed(2)}`
                      : 'Inga utvärderingar'}
                  </div>
                </div>
              );
            })}

          {/* Supervisor (overall) */}
          {data.agent_accuracy.supervisor && (() => {
            const sup = data.agent_accuracy.supervisor?.all || { accuracy_direction: 0, total_predictions: 0, correct_predictions: 0, bias: 0 };
            const supAcc = (sup.accuracy_direction || 0) * 100;
            const hasSup = sup.total_predictions > 0;
            return (
              <div style={{
                padding: '1rem', borderRadius: '8px',
                background: 'rgba(0,242,254,0.03)', border: '1px solid rgba(0,242,254,0.15)',
              }}>
                <div style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--accent-cyan)' }}>
                  🎯 Supervisor (slutgiltig)
                </div>
                <div style={{
                  fontSize: '1.5rem', fontWeight: 700,
                  color: hasSup ? getAccuracyColor(supAcc) : 'var(--text-tertiary)',
                }}>
                  {hasSup ? `${supAcc.toFixed(0)}%` : '—'}
                </div>
                <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)' }}>
                  {hasSup
                    ? `${sup.correct_predictions}/${sup.total_predictions} prediktioner`
                    : 'Väntar på data'}
                </div>
              </div>
            );
          })()}
        </div>
      </div>

      {/* Best & Worst predictions */}
      <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1rem' }}>
        {/* Best */}
        <div className="glass-panel" style={{ padding: '1.25rem' }}>
          <h3 style={{ margin: '0 0 1rem', fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <TrendingUp size={18} style={{ color: '#10b981' }} />
            Bästa träffar
          </h3>
          {data.best_predictions.length === 0 ? (
            <p style={{ color: 'var(--text-tertiary)', fontSize: '0.8rem' }}>Inga utvärderingar än</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {data.best_predictions.map((p: any, i: number) => (
                <div key={i} style={{
                  padding: '0.5rem 0.75rem', borderRadius: '6px',
                  background: 'rgba(16, 185, 129, 0.05)', border: '1px solid rgba(16, 185, 129, 0.15)',
                  fontSize: '0.8rem',
                }}>
                  <div style={{ fontWeight: 600 }}>{p.asset_name || p.asset_id}</div>
                  <div style={{ color: 'var(--text-secondary)', fontSize: '0.7rem' }}>
                    Predikterade: {p.predicted_direction} · Faktisk: {p.actual_direction} ({p.actual_change_pct?.toFixed(1)}%)
                    · Tidsram: {p.timeframe}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Worst */}
        <div className="glass-panel" style={{ padding: '1.25rem' }}>
          <h3 style={{ margin: '0 0 1rem', fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <TrendingDown size={18} style={{ color: '#ef4444' }} />
            Sämsta missar
          </h3>
          {data.worst_predictions.length === 0 ? (
            <p style={{ color: 'var(--text-tertiary)', fontSize: '0.8rem' }}>Inga utvärderingar än</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {data.worst_predictions.map((p: any, i: number) => (
                <div key={i} style={{
                  padding: '0.5rem 0.75rem', borderRadius: '6px',
                  background: 'rgba(239, 68, 68, 0.05)', border: '1px solid rgba(239, 68, 68, 0.15)',
                  fontSize: '0.8rem',
                }}>
                  <div style={{ fontWeight: 600 }}>{p.asset_name || p.asset_id}</div>
                  <div style={{ color: 'var(--text-secondary)', fontSize: '0.7rem' }}>
                    Predikterade: {p.predicted_direction} · Faktisk: {p.actual_direction} ({p.actual_change_pct?.toFixed(1)}%)
                    · Tidsram: {p.timeframe}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Prediction vs Outcome Visual */}
      <PredictionOutcomes />
    </main>
  );
}

/* ===== Prediction vs Outcome Component ===== */
function PredictionOutcomes() {
  const [outcomes, setOutcomes] = useState<any[]>([]);

  useEffect(() => {
    fetch('http://localhost:8000/api/predictions/outcomes?limit=200')
      .then(r => r.json())
      .then(d => setOutcomes(d?.outcomes || []))
      .catch(() => {});
  }, []);

  if (outcomes.length === 0) return null;

  // Group by asset
  const byAsset: Record<string, any[]> = {};
  for (const o of outcomes) {
    const key = o.asset_name || o.asset_id;
    if (!byAsset[key]) byAsset[key] = [];
    byAsset[key].push(o);
  }

  return (
    <div className="glass-panel" style={{ padding: '1.25rem', marginTop: '1.5rem' }}>
      <h3 style={{ margin: '0 0 1rem', fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        🎯 Prediktioner vs Utfall
        <span style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)', fontWeight: 400 }}>
          {outcomes.length} utvärderingar · Grön = rätt, Röd = fel, Grå = neutral
        </span>
      </h3>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {Object.entries(byAsset).map(([name, items]) => {
          const correct = items.filter(i => i.direction_correct === 1).length;
          const total = items.length;
          const acc = total > 0 ? (correct / total * 100) : 0;
          return (
            <div key={name} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <div style={{ width: '120px', fontSize: '0.75rem', fontWeight: 600, flexShrink: 0 }}>
                {name}
                <div style={{ fontSize: '0.6rem', color: 'var(--text-tertiary)', fontWeight: 400 }}>
                  {correct}/{total} ({acc.toFixed(0)}%)
                </div>
              </div>
              <div style={{ flex: 1, display: 'flex', gap: '3px', flexWrap: 'wrap' }}>
                {items.slice(0, 50).map((item: any, idx: number) => (
                  <div
                    key={idx}
                    title={`Score: ${item.score_at_analysis?.toFixed(1)} → ${item.actual_change_pct?.toFixed(1)}% (${item.timeframe})`}
                    style={{
                      width: '10px', height: '10px', borderRadius: '2px',
                      background: item.predicted_direction === 'neutral'
                        ? 'rgba(255,255,255,0.15)'
                        : item.direction_correct === 1
                          ? '#10b981'
                          : '#ef4444',
                      opacity: 0.8,
                    }}
                  />
                ))}
              </div>
              <div style={{
                width: '60px', height: '6px', borderRadius: '3px',
                background: 'rgba(255,255,255,0.05)', flexShrink: 0, overflow: 'hidden',
              }}>
                <div style={{
                  height: '100%', borderRadius: '3px',
                  width: `${acc}%`,
                  background: acc >= 50 ? '#10b981' : acc >= 40 ? '#f59e0b' : '#ef4444',
                }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ===== Ensemble Status Indicator ===== */
function EnsembleIndicator() {
  const [status, setStatus] = useState<any>(null);

  useEffect(() => {
    fetch('http://localhost:8000/api/ensemble/status')
      .then(r => r.json())
      .then(setStatus)
      .catch(() => {});
  }, []);

  if (!status) return null;

  return (
    <div className="glass-panel" style={{
      padding: '0.75rem 1rem', marginBottom: '1.5rem',
      display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap',
      background: status.enabled ? 'rgba(16, 185, 129, 0.05)' : 'rgba(255,255,255,0.02)',
      border: `1px solid ${status.enabled ? 'rgba(16, 185, 129, 0.15)' : 'var(--glass-border)'}`,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
        <div style={{
          width: '8px', height: '8px', borderRadius: '50%',
          background: status.enabled ? '#10b981' : '#6b7280',
          boxShadow: status.enabled ? '0 0 6px rgba(16,185,129,0.5)' : 'none',
        }} />
        <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>
          🔀 Ensemble {status.enabled ? 'AKTIV' : 'AV'}
        </span>
      </div>
      {status.enabled && (
        <>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>
            Second opinions idag: {status.daily_count}/{status.daily_max}
          </span>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>
            Kvar: {status.remaining}
          </span>
        </>
      )}
      {!status.enabled && (
        <span style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>
          Sätt ENSEMBLE_ENABLED=true i .env för att aktivera multi-provider
        </span>
      )}
    </div>
  );
}
