import { useState, useEffect } from 'react';
import { Brain, Zap, Shield, Activity, Users, TrendingUp, Eye, Play, RefreshCw, ChevronDown, ChevronRight } from 'lucide-react';
import { api } from '../api/client';

// ============================================================
// PREDICTIVE INTELLIGENCE PAGE
// Visualiserar hela prediktionssystemet:
// System Health → Events → Kausala Kedjor → Actor Sim →
// Adversarial → Portföljrekommendationer
// ============================================================

interface SectionProps {
  title: string;
  icon: React.ReactNode;
  badge?: string;
  badgeColor?: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}

function CollapsibleSection({ title, icon, badge, badgeColor, children, defaultOpen = true }: SectionProps) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="glass-panel animate-fade-in" style={{ padding: '1.25rem', overflow: 'hidden' }}>
      <div
        onClick={() => setOpen(!open)}
        style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', userSelect: 'none' }}
      >
        {icon}
        <h3 style={{ margin: 0, fontSize: '1.05rem', flex: 1 }}>{title}</h3>
        {badge && (
          <span style={{
            fontSize: '0.7rem', padding: '0.15rem 0.6rem', borderRadius: '10px',
            background: `${badgeColor || '#00f2fe'}18`, color: badgeColor || '#00f2fe',
            border: `1px solid ${badgeColor || '#00f2fe'}40`, fontWeight: 600,
          }}>{badge}</span>
        )}
        {open ? <ChevronDown size={16} color="var(--text-tertiary)" /> : <ChevronRight size={16} color="var(--text-tertiary)" />}
      </div>
      {open && <div style={{ marginTop: '1rem' }}>{children}</div>}
    </div>
  );
}

function MetricCard({ label, value, sub, color }: { label: string; value: string | number; sub?: string; color?: string }) {
  return (
    <div style={{
      padding: '0.75rem', borderRadius: '8px',
      background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.04)',
    }}>
      <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', marginBottom: '0.25rem' }}>{label}</div>
      <div style={{ fontSize: '1.2rem', fontWeight: 700, color: color || 'var(--text-primary)' }}>{value}</div>
      {sub && <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)', marginTop: '0.15rem' }}>{sub}</div>}
    </div>
  );
}

// ---- SYSTEM HEALTH SECTION ----
function SystemHealthSection() {
  const [health, setHealth] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getSystemHealth().then(setHealth).catch(() => {}).finally(() => setLoading(false));
  }, []);

  if (loading) return <div style={{ color: 'var(--text-tertiary)', fontSize: '0.85rem' }}>Laddar systemstatus...</div>;
  if (!health) return null;

  const statusColor = health.status === 'HEALTHY' ? '#00c851' : health.status === 'WARNING' ? '#ffa502' : '#ff4757';
  const statusEmoji = health.status === 'HEALTHY' ? '🟢' : health.status === 'WARNING' ? '🟡' : '🔴';

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '0.75rem' }}>
      <MetricCard label="Systemstatus" value={`${statusEmoji} ${health.status}`} color={statusColor} />
      <MetricCard label="Filer saknas" value={health.missing_files || 0} color={health.missing_files > 2 ? '#ff4757' : '#00c851'} />
      <MetricCard label="Inaktuella" value={health.stale_files || 0} color={health.stale_files > 2 ? '#ffa502' : '#00c851'} />
      <MetricCard label="Meddelande" value="" sub={health.message} />
      {health.recommendations?.length > 0 && (
        <div style={{ gridColumn: '1 / -1', fontSize: '0.75rem', color: 'var(--text-tertiary)', padding: '0.5rem', borderRadius: '6px', background: 'rgba(255,165,2,0.05)' }}>
          💡 {health.recommendations[0]}
        </div>
      )}
    </div>
  );
}

// ---- PIPELINE SECTION ----
function PipelineSection() {
  const [result, setResult] = useState<any>(null);
  const [running, setRunning] = useState(false);
  const [autoStatus, setAutoStatus] = useState<any>(null);

  useEffect(() => {
    api.getAutoStatus().then(setAutoStatus).catch(() => {});
  }, []);

  const runPipeline = async () => {
    setRunning(true);
    try {
      const res = await api.runPipeline();
      setResult(res);
      // Refresh auto-status after manual run
      api.getAutoStatus().then(setAutoStatus).catch(() => {});
    } catch { /* ignore */ }
    setRunning(false);
  };

  const formatTime = (iso: string) => {
    try { return new Date(iso).toLocaleTimeString('sv-SE', { hour: '2-digit', minute: '2-digit' }); }
    catch { return '—'; }
  };

  return (
    <div>
      {/* Auto-status banner */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1rem',
        padding: '0.6rem 1rem', borderRadius: '8px',
        background: 'rgba(102,126,234,0.06)', border: '1px solid rgba(102,126,234,0.12)',
        flexWrap: 'wrap',
      }}>
        <span style={{
          fontSize: '0.7rem', padding: '0.15rem 0.5rem', borderRadius: '8px',
          background: 'rgba(16,185,129,0.15)', color: '#10b981', fontWeight: 700,
        }}>🤖 AUTONOM</span>
        {autoStatus?.last_run ? (
          <>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
              Senaste: <strong>{formatTime(autoStatus.last_run)}</strong>
            </span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>
              Nästa: ~{formatTime(autoStatus.next_run_approx)}
            </span>
            <span style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)' }}>
              {autoStatus.run_count} körningar • var {autoStatus.interval_hours}h
            </span>
          </>
        ) : (
          <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>
            Första automatiska körning startar ~2 min efter serverstart
          </span>
        )}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
        <button
          onClick={runPipeline}
          disabled={running}
          style={{
            padding: '0.6rem 1.5rem', borderRadius: '8px', cursor: running ? 'wait' : 'pointer',
            background: running ? 'rgba(255,255,255,0.05)' : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            border: 'none', color: '#fff', fontWeight: 600, fontSize: '0.85rem',
            display: 'flex', alignItems: 'center', gap: '0.5rem',
            transition: 'all 0.3s ease', opacity: running ? 0.6 : 1,
          }}
        >
          {running ? <RefreshCw size={16} className="spin" /> : <Play size={16} />}
          {running ? 'Pipeline körs...' : 'Kör Manuellt'}
        </button>
        {result && (
          <span style={{ fontSize: '0.75rem', color: result.status === 'COMPLETE' ? '#00c851' : '#ff4757' }}>
            {result.status} • {result.duration_seconds}s
          </span>
        )}
      </div>

      {result && result.status === 'COMPLETE' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.75rem' }}>
          <MetricCard label="AI-events" value={result.detection?.ai_events || 0} color="#a78bfa" />
          <MetricCard label="Prisavvikelser" value={result.detection?.price_anomalies || 0} color="#ffa502" />
          <MetricCard label="Aktiva kedjor" value={result.causal_chains?.active || 0} color="#00f2fe" />
          <MetricCard label="Lead-lag signaler" value={result.lead_lag?.actionable_signals || 0} color="#10b981" />

          {/* Portfolio Recommendations */}
          {result.portfolio_recommendation?.recommendations?.length > 0 && (
            <div style={{ gridColumn: '1 / -1', marginTop: '0.5rem' }}>
              <div style={{ fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--text-secondary)' }}>
                💼 Portföljrekommendationer
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                {result.portfolio_recommendation.recommendations.slice(0, 6).map((rec: any, i: number) => {
                  const isBull = rec.action === 'ÖKA';
                  const barWidth = Math.min(Math.abs(rec.weighted_score) * 8, 100);
                  return (
                    <div key={i} style={{
                      display: 'flex', alignItems: 'center', gap: '0.5rem',
                      padding: '0.5rem 0.75rem', borderRadius: '6px',
                      background: isBull ? 'rgba(16,185,129,0.04)' : 'rgba(239,68,68,0.04)',
                      borderLeft: `3px solid ${isBull ? '#10b981' : '#ef4444'}`,
                    }}>
                      <span style={{ fontSize: '0.8rem', fontWeight: 600, width: '90px', color: 'var(--text-primary)' }}>
                        {isBull ? '📈' : '📉'} {rec.asset}
                      </span>
                      <span style={{
                        fontSize: '0.7rem', padding: '0.1rem 0.4rem', borderRadius: '4px', fontWeight: 700,
                        background: isBull ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)',
                        color: isBull ? '#10b981' : '#ef4444',
                      }}>{rec.action}</span>
                      <div style={{ flex: 1, height: '6px', background: 'rgba(255,255,255,0.04)', borderRadius: '3px' }}>
                        <div style={{
                          width: `${barWidth}%`, height: '100%', borderRadius: '3px',
                          background: isBull ? '#10b981' : '#ef4444',
                          transition: 'width 0.5s ease',
                        }} />
                      </div>
                      <span style={{ fontSize: '0.75rem', fontWeight: 700, width: '50px', textAlign: 'right', color: isBull ? '#10b981' : '#ef4444' }}>
                        {rec.weighted_score > 0 ? '+' : ''}{rec.weighted_score}
                      </span>
                      <span style={{ fontSize: '0.6rem', color: 'var(--text-tertiary)', width: '40px', textAlign: 'right' }}>
                        {rec.strength}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---- EVENT DETECTION SECTION ----
function EventDetectionSection() {
  const [stats, setStats] = useState<any>(null);
  const [unprocessed, setUnprocessed] = useState<any[]>([]);

  useEffect(() => {
    api.getEventLog().then(setStats).catch(() => {});
    api.getUnprocessedEvents().then(setUnprocessed).catch(() => {});
  }, []);

  const hasByData = stats && stats.by_severity;

  return (
    <div>
      {hasByData ? (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))', gap: '0.5rem', marginBottom: '1rem' }}>
            <MetricCard label="🔴 Kritiska" value={stats.by_severity?.CRITICAL || 0} color="#ff4757" />
            <MetricCard label="🟠 Höga" value={stats.by_severity?.HIGH || 0} color="#ffa502" />
            <MetricCard label="🟡 Medium" value={stats.by_severity?.MEDIUM || 0} color="#ffd93d" />
            <MetricCard label="Totalt 30d" value={stats.last_30_days || 0} />
            <MetricCard label="Kedjor triggade" value={stats.chains_triggered || 0} color="#00f2fe" />
          </div>
          {stats.processed_rate !== undefined && (
            <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>
              Processade: {Math.round(stats.processed_rate * 100)}% av detekterade events
            </div>
          )}
        </>
      ) : (
        <div style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>
          {stats?.total === 0 ? 'Inga events detekterade ännu. Kör pipeline för att starta.' : 'Laddar eventdata...'}
        </div>
      )}

      {unprocessed.length > 0 && (
        <div style={{ marginTop: '1rem' }}>
          <div style={{ fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.5rem', color: '#ffa502' }}>
            ⏳ Väntar på analys ({unprocessed.length})
          </div>
          {unprocessed.slice(0, 5).map((e: any, i: number) => (
            <div key={i} style={{
              padding: '0.4rem 0.6rem', fontSize: '0.78rem', marginBottom: '0.3rem',
              borderRadius: '5px', background: 'rgba(255,165,2,0.05)',
              borderLeft: `2px solid ${e.severity === 'CRITICAL' ? '#ff4757' : '#ffa502'}`,
            }}>
              <strong>{e.severity}</strong> — {e.title}
              {e.assets?.length > 0 && (
                <span style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)', marginLeft: '0.5rem' }}>
                  [{e.assets.join(', ')}]
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---- ACTOR SIMULATION SECTION ----
function ActorSimulationSection() {
  const [eventInput, setEventInput] = useState('Fed höjer ränta 50bps oväntad');
  const [result, setResult] = useState<any>(null);
  const [running, setRunning] = useState(false);
  const [intelligence, setIntelligence] = useState<any>(null);

  useEffect(() => {
    api.getActorIntelligence().then(setIntelligence).catch(() => {});
  }, []);

  const runSim = async () => {
    setRunning(true);
    try {
      const res = await api.runActorSimulation(eventInput);
      setResult(res);
    } catch { /* ignore */ }
    setRunning(false);
  };

  const actionColors: Record<string, string> = {
    'KÖP': '#10b981', 'SÄLJ': '#ef4444', 'AVVAKTA': '#a4b0be',
    'HEDGE': '#f59e0b', 'INTERVENE': '#a78bfa',
  };

  return (
    <div>
      {/* Input & Trigger */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
        <input
          value={eventInput}
          onChange={e => setEventInput(e.target.value)}
          placeholder="Beskriv en marknadshändelse..."
          style={{
            flex: 1, minWidth: '200px', padding: '0.6rem 0.75rem', borderRadius: '8px',
            background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
            color: 'var(--text-primary)', fontSize: '0.85rem',
          }}
        />
        <button
          onClick={runSim}
          disabled={running || !eventInput.trim()}
          style={{
            padding: '0.6rem 1.2rem', borderRadius: '8px', cursor: running ? 'wait' : 'pointer',
            background: running ? 'rgba(255,255,255,0.05)' : 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
            border: 'none', color: '#fff', fontWeight: 600, fontSize: '0.85rem',
            display: 'flex', alignItems: 'center', gap: '0.4rem',
            opacity: running ? 0.6 : 1,
          }}
        >
          {running ? <RefreshCw size={14} className="spin" /> : <Users size={14} />}
          {running ? 'Simulerar...' : 'Simulera'}
        </button>
      </div>

      {/* Previous intelligence */}
      {intelligence && intelligence.simulations_analyzed > 0 && !result && (
        <div style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)', marginBottom: '1rem' }}>
          📊 {intelligence.simulations_analyzed} tidigare simuleringar • Snitt panik-risk: {intelligence.avg_panic_risk}
          {intelligence.latest_key_insight && (
            <div style={{ marginTop: '0.3rem', color: 'var(--text-secondary)', fontStyle: 'italic' }}>
              "{intelligence.latest_key_insight}"
            </div>
          )}
        </div>
      )}

      {/* Simulation Result */}
      {result && !result.error && (
        <div>
          {/* Summary Bar */}
          <div style={{
            display: 'flex', gap: '1rem', marginBottom: '1rem', padding: '0.75rem',
            borderRadius: '8px', background: 'rgba(255,255,255,0.02)',
            flexWrap: 'wrap',
          }}>
            <div>
              <span style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)' }}>Konsensus</span>
              <div style={{
                fontSize: '1rem', fontWeight: 700,
                color: result.consensus_direction === 'BULL' ? '#10b981' : result.consensus_direction === 'BEAR' ? '#ef4444' : '#ffa502',
              }}>{result.consensus_direction}</div>
            </div>
            <div>
              <span style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)' }}>Panik-risk</span>
              <div style={{
                fontSize: '1rem', fontWeight: 700,
                color: result.panic_risk > 0.6 ? '#ef4444' : result.panic_risk > 0.3 ? '#ffa502' : '#10b981',
              }}>{(result.panic_risk * 100).toFixed(0)}%</div>
            </div>
            {result.key_insight && (
              <div style={{ flex: 1, minWidth: '200px' }}>
                <span style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)' }}>Nyckelinsikt</span>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontStyle: 'italic' }}>
                  "{result.key_insight}"
                </div>
              </div>
            )}
          </div>

          {/* Actor Reactions */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
            {result.reactions?.map((r: any, i: number) => {
              const barWidth = (r.intensity / 10) * 100;
              return (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: '0.5rem',
                  padding: '0.4rem 0.6rem', borderRadius: '6px',
                  background: 'rgba(255,255,255,0.015)',
                }}>
                  <span style={{ width: '160px', fontSize: '0.78rem', fontWeight: 500, color: 'var(--text-primary)' }}>
                    {r.actor_name?.slice(0, 22)}
                  </span>
                  <span style={{
                    width: '60px', fontSize: '0.68rem', fontWeight: 700, textAlign: 'center',
                    padding: '0.1rem 0.3rem', borderRadius: '3px',
                    background: `${actionColors[r.action] || '#a4b0be'}18`,
                    color: actionColors[r.action] || '#a4b0be',
                  }}>{r.action}</span>
                  <div style={{ flex: 1, height: '7px', background: 'rgba(255,255,255,0.04)', borderRadius: '4px', overflow: 'hidden' }}>
                    <div style={{
                      width: `${barWidth}%`, height: '100%', borderRadius: '4px',
                      background: `linear-gradient(90deg, ${actionColors[r.action] || '#a4b0be'}, ${actionColors[r.action] || '#a4b0be'}80)`,
                      transition: 'width 0.5s ease',
                    }} />
                  </div>
                  <span style={{ width: '35px', fontSize: '0.72rem', fontWeight: 600, textAlign: 'right', color: 'var(--text-secondary)' }}>
                    {r.intensity}/10
                  </span>
                  <span style={{ width: '55px', fontSize: '0.62rem', color: 'var(--text-tertiary)', textAlign: 'right' }}>
                    {r.timing}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Net Impact */}
          {result.net_asset_impact && Object.keys(result.net_asset_impact).length > 0 && (
            <div style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              {Object.entries(result.net_asset_impact).map(([asset, impact]: [string, any]) => (
                <span key={asset} style={{
                  fontSize: '0.72rem', padding: '0.2rem 0.5rem', borderRadius: '5px', fontWeight: 600,
                  background: impact > 0 ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)',
                  color: impact > 0 ? '#10b981' : '#ef4444',
                }}>
                  {asset}: {impact > 0 ? '+' : ''}{impact}%
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---- META & CONFIDENCE SECTION ----
function MetaConfidenceSection() {
  const [meta, setMeta] = useState<any>(null);
  const [confidence, setConfidence] = useState<any>(null);

  useEffect(() => {
    api.getMetaStrategy().then(setMeta).catch(() => {});
    api.getConfidence().then(setConfidence).catch(() => {});
  }, []);

  const regimeOrder = ['RISK_ON', 'NEUTRAL', 'RISK_OFF', 'CRISIS'];
  const methodLabels: Record<string, string> = {
    causal_chain: 'Kausal', event_tree: 'EventTree', lead_lag: 'LeadLag',
    narrative: 'Narrativ', actor_sim: 'ActorSim',
  };
  const regimeEmoji: Record<string, string> = {
    RISK_ON: '📈', NEUTRAL: '➡️', RISK_OFF: '📉', CRISIS: '🔴',
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
      {/* Meta Strategy weights */}
      <div>
        <div style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.75rem', color: 'var(--text-secondary)' }}>
          ⚖️ Metodvikter per Regim
        </div>
        {meta?.regimes ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {regimeOrder.map(regime => {
              const data = meta.regimes[regime];
              if (!data) return null;
              // Get weights from the current_weights on the meta strategy
              const methods = data.methods && Object.keys(data.methods).length > 0
                ? data.methods
                : null;
              return (
                <div key={regime} style={{ padding: '0.5rem', borderRadius: '6px', background: 'rgba(255,255,255,0.02)' }}>
                  <div style={{ fontSize: '0.75rem', fontWeight: 600, marginBottom: '0.3rem' }}>
                    {regimeEmoji[regime]} {regime.replace('_', ' ')}
                    <span style={{ fontSize: '0.6rem', color: 'var(--text-tertiary)', marginLeft: '0.5rem' }}>
                      {data.total_records} records
                    </span>
                  </div>
                  {!methods ? (
                    <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)' }}>Default-vikter (samlar data)</div>
                  ) : (
                    <div style={{ display: 'flex', gap: '0.3rem', flexWrap: 'wrap' }}>
                      {Object.entries(methods).map(([method, info]: [string, any]) => (
                        <span key={method} style={{
                          fontSize: '0.6rem', padding: '0.1rem 0.35rem', borderRadius: '3px',
                          background: 'rgba(167,139,246,0.08)', color: '#a78bfa',
                        }}>
                          {methodLabels[method] || method}: {(info.current_weight * 100).toFixed(0)}%
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <div style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>
            {meta?.recommendation || 'Laddar...'}
          </div>
        )}
      </div>

      {/* Confidence Calibration */}
      <div>
        <div style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.75rem', color: 'var(--text-secondary)' }}>
          🎯 Konfidenskalibrering
        </div>
        {confidence?.brier_score !== undefined ? (
          <div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', marginBottom: '0.75rem' }}>
              <MetricCard label="Brier Score" value={confidence.brier_score}
                color={confidence.brier_interpretation === 'BRA' ? '#10b981' : confidence.brier_interpretation === 'MEDEL' ? '#ffa502' : '#ef4444'}
                sub={confidence.brier_interpretation} />
              <MetricCard label="Prediktioner" value={confidence.total_predictions} sub={confidence.diagnosis?.slice(0, 40)} />
            </div>
            {confidence.calibration_bins && Object.keys(confidence.calibration_bins).length > 0 && (
              <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>
                Överkonfident bins: {confidence.overconfident_bins} | Underkonfident: {confidence.underconfident_bins}
              </div>
            )}
          </div>
        ) : (
          <div style={{
            padding: '1rem', borderRadius: '8px', background: 'rgba(255,255,255,0.02)',
            fontSize: '0.8rem', color: 'var(--text-tertiary)', textAlign: 'center',
          }}>
            {confidence?.status === 'OTILLRÄCKLIG_DATA'
              ? `📊 Behöver ${confidence.min_needed}+ prediktioner (har ${confidence.records || 0})`
              : 'Laddar kalibrering...'}
          </div>
        )}
      </div>
    </div>
  );
}

// ---- ADVERSARIAL CHECK SECTION ----
function AdversarialSection() {
  const [asset, setAsset] = useState('SP500');
  const [action, setAction] = useState('KÖP');
  const [reasoning, setReasoning] = useState('Stark teknisk signal + positiv kausal kedja');
  const [result, setResult] = useState<any>(null);
  const [running, setRunning] = useState(false);

  const runCheck = async () => {
    setRunning(true);
    try {
      const res = await api.runAdversarialCheck(asset, action, reasoning);
      setResult(res);
    } catch { /* ignore */ }
    setRunning(false);
  };

  return (
    <div>
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <div>
          <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)', marginBottom: '0.2rem' }}>Tillgång</div>
          <input value={asset} onChange={e => setAsset(e.target.value)} style={{
            width: '80px', padding: '0.5rem', borderRadius: '6px',
            background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
            color: 'var(--text-primary)', fontSize: '0.8rem',
          }} />
        </div>
        <div>
          <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)', marginBottom: '0.2rem' }}>Action</div>
          <select value={action} onChange={e => setAction(e.target.value)} style={{
            padding: '0.5rem', borderRadius: '6px', fontSize: '0.8rem',
            background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
            color: 'var(--text-primary)', cursor: 'pointer',
          }}>
            <option value="KÖP">KÖP</option>
            <option value="SÄLJ">SÄLJ</option>
            <option value="ÖKA">ÖKA</option>
            <option value="MINSKA">MINSKA</option>
          </select>
        </div>
        <div style={{ flex: 1, minWidth: '150px' }}>
          <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)', marginBottom: '0.2rem' }}>Motivering</div>
          <input value={reasoning} onChange={e => setReasoning(e.target.value)} style={{
            width: '100%', padding: '0.5rem', borderRadius: '6px',
            background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
            color: 'var(--text-primary)', fontSize: '0.8rem',
          }} />
        </div>
        <button onClick={runCheck} disabled={running} style={{
          padding: '0.5rem 1rem', borderRadius: '6px', cursor: 'pointer',
          background: 'linear-gradient(135deg, #ff4757 0%, #ff6b81 100%)',
          border: 'none', color: '#fff', fontWeight: 600, fontSize: '0.8rem',
          display: 'flex', alignItems: 'center', gap: '0.3rem',
          opacity: running ? 0.6 : 1,
        }}>
          {running ? <RefreshCw size={14} className="spin" /> : <Shield size={14} />}
          {running ? 'Analyserar...' : 'Devils Advocate'}
        </button>
      </div>

      {result && !result.error && (
        <div style={{ borderRadius: '8px', border: '1px solid rgba(255,71,87,0.15)', overflow: 'hidden' }}>
          {/* Verdict banner */}
          <div style={{
            padding: '0.6rem 1rem',
            background: result.should_proceed ? 'rgba(16,185,129,0.08)' : 'rgba(239,68,68,0.08)',
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          }}>
            <span style={{
              fontWeight: 700, fontSize: '0.85rem',
              color: result.should_proceed ? '#10b981' : '#ef4444',
            }}>
              {result.should_proceed ? '✅ PROCEED' : '⛔ BLOCKED'}
            </span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
              Conviction: {result.original_conviction} → {result.adjusted_conviction}
            </span>
          </div>

          <div style={{ padding: '0.75rem 1rem' }}>
            {/* Challenges */}
            {result.challenges?.map((c: any, i: number) => (
              <div key={i} style={{
                fontSize: '0.78rem', padding: '0.4rem 0', borderBottom: '1px solid rgba(255,255,255,0.04)',
                display: 'flex', gap: '0.5rem', alignItems: 'flex-start',
              }}>
                <span style={{
                  fontSize: '0.6rem', padding: '0.1rem 0.3rem', borderRadius: '3px', fontWeight: 700, whiteSpace: 'nowrap',
                  background: c.severity === 'KRITISK' ? 'rgba(255,71,87,0.15)' : c.severity === 'ALLVARLIG' ? 'rgba(255,165,2,0.15)' : 'rgba(255,255,255,0.05)',
                  color: c.severity === 'KRITISK' ? '#ff4757' : c.severity === 'ALLVARLIG' ? '#ffa502' : 'var(--text-tertiary)',
                }}>{c.severity}</span>
                <span style={{ color: 'var(--text-secondary)' }}>{c.argument}</span>
              </div>
            ))}

            {/* Key info */}
            {result.weakest_assumption && (
              <div style={{ marginTop: '0.5rem', fontSize: '0.75rem' }}>
                <strong style={{ color: '#ffa502' }}>Svagaste antagande:</strong>{' '}
                <span style={{ color: 'var(--text-secondary)' }}>{result.weakest_assumption}</span>
              </div>
            )}
            {result.counter_narrative && (
              <div style={{ marginTop: '0.3rem', fontSize: '0.75rem' }}>
                <strong style={{ color: '#ef4444' }}>Motargument:</strong>{' '}
                <span style={{ color: 'var(--text-secondary)' }}>{result.counter_narrative}</span>
              </div>
            )}

            {/* Red flags */}
            {result.red_flags?.length > 0 && (
              <div style={{ marginTop: '0.5rem', display: 'flex', gap: '0.3rem', flexWrap: 'wrap' }}>
                {result.red_flags.map((flag: string, i: number) => (
                  <span key={i} style={{
                    fontSize: '0.65rem', padding: '0.15rem 0.5rem', borderRadius: '4px',
                    background: 'rgba(255,71,87,0.08)', color: '#ff6b81',
                  }}>⚠️ {flag}</span>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}


// ============================================================
// MAIN PAGE
// ============================================================
export default function PredictivePage() {
  return (
    <main className="container" style={{ paddingTop: '2rem', paddingBottom: '6rem' }}>
      {/* Header */}
      <section className="glass-panel animate-fade-in" style={{
        padding: '1.5rem 2rem', marginBottom: '1.5rem',
        background: 'linear-gradient(135deg, rgba(102,126,234,0.08) 0%, rgba(118,75,162,0.08) 100%)',
        borderLeft: '4px solid #667eea',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <Brain size={32} color="#a78bfa" />
          <div>
            <h2 style={{ margin: 0, fontSize: '1.5rem' }}>
              <span style={{ background: 'linear-gradient(135deg, #667eea, #a78bfa)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                Predictive Intelligence
              </span>
            </h2>
            <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>
              Autonom event-detektion • Kausala kedjor • Aktörsimulering • Adversarial • Meta-learning
            </p>
          </div>
        </div>
      </section>

      {/* Grid Layout */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>

        {/* Row 1: Health + Pipeline */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '1rem' }}>
          <CollapsibleSection title="Systemhälsa" icon={<Activity size={18} color="#00c851" />}>
            <SystemHealthSection />
          </CollapsibleSection>

          <CollapsibleSection
            title="Daglig Pipeline"
            icon={<Zap size={18} color="#667eea" />}
            badge="Live"
            badgeColor="#667eea"
          >
            <PipelineSection />
          </CollapsibleSection>
        </div>

        {/* Row 2: Event Detection */}
        <CollapsibleSection
          title="Event Detection"
          icon={<Eye size={18} color="#ffa502" />}
          badge="Autonom"
          badgeColor="#ffa502"
        >
          <EventDetectionSection />
        </CollapsibleSection>

        {/* Row 3: Actor Simulation */}
        <CollapsibleSection
          title="Aktörsimulering"
          icon={<Users size={18} color="#f5576c" />}
          badge="AI"
          badgeColor="#f5576c"
        >
          <ActorSimulationSection />
        </CollapsibleSection>

        {/* Row 4: Adversarial */}
        <CollapsibleSection
          title="Devils Advocate"
          icon={<Shield size={18} color="#ff4757" />}
          badge="Kvalitetskontroll"
          badgeColor="#ff4757"
        >
          <AdversarialSection />
        </CollapsibleSection>

        {/* Row 5: Meta + Confidence */}
        <CollapsibleSection
          title="Meta-learning & Kalibrering"
          icon={<TrendingUp size={18} color="#a78bfa" />}
          defaultOpen={false}
        >
          <MetaConfidenceSection />
        </CollapsibleSection>
      </div>
    </main>
  );
}
