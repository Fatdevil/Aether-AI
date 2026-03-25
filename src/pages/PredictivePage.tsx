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
// ---- CAUSAL FLOW DIAGRAM ----
function CausalFlowDiagram() {
  const [chains, setChains] = useState<any>(null);
  const [selected, setSelected] = useState<number>(0);

  useEffect(() => {
    api.getCausalChainsActive().then(setChains).catch(() => {});
  }, []);

  if (!chains || !chains.chains?.length) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-tertiary)', fontSize: '0.85rem' }}>
        {chains?.total === 0 ? '🔗 Inga aktiva kausala kedjor. Kör pipeline för att bygga kedjor.' : 'Laddar kedjor...'}
      </div>
    );
  }

  const chain = chains.chains[selected];
  const links = chain?.links || [];
  const nodeW = 160, nodeH = 50, gapX = 60;
  const svgW = (links.length + 1) * (nodeW + gapX) + 40;
  const svgH = 180;

  // Build nodes: trigger + all effects
  const nodes = [
    { label: chain.trigger_event?.slice(0, 22) || 'Trigger', type: 'trigger', x: 20, y: 60 },
    ...links.map((l: any, i: number) => ({
      label: l.effect?.slice(0, 22) || `Effekt ${i + 1}`,
      type: l.status === 'CONFIRMED' ? 'confirmed' : l.status === 'INVALIDATED' ? 'invalid' : 'pending',
      x: 20 + (i + 1) * (nodeW + gapX),
      y: 60,
      prob: l.probability,
      delay: l.delay,
    })),
  ];

  const statusColors: Record<string, string> = {
    trigger: '#a78bfa', confirmed: '#10b981', invalid: '#ef4444', pending: '#667eea',
  };

  return (
    <div>
      {/* Chain selector */}
      {chains.chains.length > 1 && (
        <div style={{ display: 'flex', gap: '0.3rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
          {chains.chains.map((c: any, i: number) => (
            <button key={i} onClick={() => setSelected(i)} style={{
              padding: '0.3rem 0.7rem', borderRadius: '6px', fontSize: '0.72rem', fontWeight: 600,
              background: i === selected ? 'rgba(102,126,234,0.2)' : 'rgba(255,255,255,0.03)',
              border: `1px solid ${i === selected ? '#667eea' : 'rgba(255,255,255,0.06)'}`,
              color: i === selected ? '#a78bfa' : 'var(--text-tertiary)', cursor: 'pointer',
            }}>
              {c.trigger_event?.slice(0, 30)}
            </button>
          ))}
        </div>
      )}

      {/* SVG Flow Diagram */}
      <div style={{ overflowX: 'auto', borderRadius: '8px', background: 'rgba(0,0,0,0.2)', padding: '0.5rem' }}>
        <svg width={svgW} height={svgH} viewBox={`0 0 ${svgW} ${svgH}`}>
          <defs>
            <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
              <polygon points="0 0, 10 3.5, 0 7" fill="#667eea" />
            </marker>
          </defs>

          {/* Edges (arrows) */}
          {nodes.slice(0, -1).map((node, i) => {
            const next = nodes[i + 1];
            const link = links[i];
            return (
              <g key={`edge-${i}`}>
                <line
                  x1={node.x + nodeW} y1={node.y + nodeH / 2}
                  x2={next.x} y2={next.y + nodeH / 2}
                  stroke="#667eea" strokeWidth={2} strokeDasharray={link?.status === 'PENDING' ? '5,5' : 'none'}
                  markerEnd="url(#arrowhead)" opacity={0.7}
                />
                {link && (
                  <text
                    x={(node.x + nodeW + next.x) / 2} y={node.y + nodeH / 2 - 8}
                    textAnchor="middle" fontSize="10" fill="#a78bfa" fontWeight="600"
                  >
                    {(link.probability * 100).toFixed(0)}% • {link.delay || '?'}
                  </text>
                )}
              </g>
            );
          })}

          {/* Nodes */}
          {nodes.map((node, i) => (
            <g key={`node-${i}`}>
              <rect
                x={node.x} y={node.y} width={nodeW} height={nodeH} rx={8}
                fill={`${statusColors[node.type]}12`}
                stroke={statusColors[node.type]} strokeWidth={1.5}
              />
              <text
                x={node.x + nodeW / 2} y={node.y + nodeH / 2 + 4}
                textAnchor="middle" fontSize="11" fill={statusColors[node.type]} fontWeight="600"
              >
                {node.label}
              </text>
              {node.type === 'trigger' && (
                <text x={node.x + nodeW / 2} y={node.y - 6} textAnchor="middle" fontSize="9" fill="#a78bfa">
                  ⚡ TRIGGER
                </text>
              )}
            </g>
          ))}
        </svg>
      </div>

      {/* Chain info bar */}
      <div style={{
        display: 'flex', gap: '1rem', marginTop: '0.75rem', fontSize: '0.72rem', color: 'var(--text-tertiary)',
        flexWrap: 'wrap',
      }}>
        <span>Sannolikhet: <strong style={{ color: '#a78bfa' }}>{(chain.probability * 100).toFixed(0)}%</strong></span>
        <span>Länkar: <strong>{links.length}</strong></span>
        <span style={{ display: 'flex', gap: '0.3rem' }}>
          {Object.entries(chain.portfolio_impact || {}).slice(0, 4).map(([asset, impact]: [string, any]) => (
            <span key={asset} style={{
              padding: '0.1rem 0.3rem', borderRadius: '3px', fontSize: '0.65rem',
              background: impact > 0 ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)',
              color: impact > 0 ? '#10b981' : '#ef4444',
            }}>{asset}: {impact > 0 ? '+' : ''}{typeof impact === 'number' ? impact.toFixed(1) : impact}</span>
          ))}
        </span>
      </div>
    </div>
  );
}


// ---- LEAD-LAG NETWORK GRAPH ----
function LeadLagNetwork() {
  const [network, setNetwork] = useState<any>(null);

  useEffect(() => {
    api.getLeadLagNetwork().then(setNetwork).catch(() => {});
  }, []);

  if (!network || (!network.edges?.length && !network.nodes?.length)) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-tertiary)', fontSize: '0.85rem' }}>
        {network?.nodes?.length === 0 ? '📊 Ingen historisk data för lead-lag-analys ännu.' : 'Laddar nätverksdata...'}
      </div>
    );
  }

  const nodes = network.nodes || [];
  const edges = network.edges || [];
  const svgW = 600, svgH = 350;
  const centerX = svgW / 2, centerY = svgH / 2;
  const radius = 140;

  // Position nodes in a circle
  const nodePositions = nodes.map((n: any, i: number) => {
    const angle = (2 * Math.PI * i) / nodes.length - Math.PI / 2;
    return {
      ...n,
      x: centerX + radius * Math.cos(angle),
      y: centerY + radius * Math.sin(angle),
    };
  });

  const groupColors: Record<string, string> = {
    crypto: '#f7931a', equity: '#10b981', commodity: '#a78bfa',
  };

  const getNodePos = (id: string) => nodePositions.find((n: any) => n.id === id) || { x: centerX, y: centerY };

  return (
    <div style={{ borderRadius: '8px', background: 'rgba(0,0,0,0.2)', padding: '0.75rem' }}>
      <svg width="100%" viewBox={`0 0 ${svgW} ${svgH}`}>
        <defs>
          <marker id="arrow-ll" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
            <polygon points="0 0, 8 3, 0 6" fill="#667eea" opacity="0.6" />
          </marker>
        </defs>

        {/* Edges */}
        {edges.map((e: any, i: number) => {
          const src = getNodePos(e.source);
          const tgt = getNodePos(e.target);
          const isPositive = e.direction === 'positive';
          const dx = tgt.x - src.x, dy = tgt.y - src.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          const nx = dx / dist, ny = dy / dist;
          // Shorten arrows to not overlap nodes
          const sx = src.x + nx * 30, sy = src.y + ny * 30;
          const tx = tgt.x - nx * 30, ty = tgt.y - ny * 30;
          const midX = (sx + tx) / 2, midY = (sy + ty) / 2;

          return (
            <g key={`edge-${i}`}>
              <line
                x1={sx} y1={sy} x2={tx} y2={ty}
                stroke={isPositive ? '#10b981' : '#ef4444'}
                strokeWidth={Math.max(1, Math.abs(e.correlation) * 3)}
                opacity={0.5} markerEnd="url(#arrow-ll)"
              />
              <text x={midX} y={midY - 6} textAnchor="middle" fontSize="9" fill="var(--text-tertiary)">
                {e.lag_days}d lag
              </text>
            </g>
          );
        })}

        {/* Nodes */}
        {nodePositions.map((n: any, i: number) => {
          const color = groupColors[n.group] || '#667eea';
          const hasEdge = edges.some((e: any) => e.source === n.id || e.target === n.id);
          return (
            <g key={`node-${i}`}>
              <circle
                cx={n.x} cy={n.y} r={hasEdge ? 24 : 18}
                fill={`${color}20`} stroke={color} strokeWidth={hasEdge ? 2 : 1}
              />
              <text x={n.x} y={n.y + 4} textAnchor="middle" fontSize="9" fill={color} fontWeight="700">
                {n.id?.slice(0, 6)}
              </text>
            </g>
          );
        })}

        {/* Legend */}
        <g transform={`translate(10, ${svgH - 50})`}>
          {Object.entries(groupColors).map(([group, color], i) => (
            <g key={group} transform={`translate(${i * 90}, 0)`}>
              <circle cx={8} cy={8} r={6} fill={`${color}40`} stroke={color} strokeWidth={1} />
              <text x={18} y={12} fontSize="9" fill="var(--text-tertiary)">{group}</text>
            </g>
          ))}
        </g>
      </svg>
    </div>
  );
}


// ---- CALIBRATION PLOT ----
function CalibrationPlot() {
  const [confidence, setConfidence] = useState<any>(null);

  useEffect(() => {
    api.getConfidence().then(setConfidence).catch(() => {});
  }, []);

  const svgW = 320, svgH = 320;
  const pad = 45;
  const chartW = svgW - 2 * pad, chartH = svgH - 2 * pad;

  if (!confidence?.calibration_bins || Object.keys(confidence.calibration_bins).length === 0) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-tertiary)', fontSize: '0.85rem' }}>
        <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>🎯</div>
        {confidence?.status === 'OTILLRÄCKLIG_DATA'
          ? `Behöver ${confidence.min_needed}+ prediktioner (har ${confidence.records || 0}). Systemet loggar nu automatiskt.`
          : 'Laddar kalibrering...'}
        <div style={{ marginTop: '0.75rem', fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>
          Kalibreringsplotten visar hur väl systemets konfidensangivelser stämmer med verkligheten.
          Perfekt kalibrering = alla punkter på 45°-linjen.
        </div>
      </div>
    );
  }

  const bins = confidence.calibration_bins;
  const points = Object.entries(bins).map(([key, val]: [string, any]) => ({
    predicted: val.mean_predicted || parseFloat(key),
    actual: val.mean_actual || 0,
    count: val.count || 0,
  }));

  return (
    <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'flex-start', flexWrap: 'wrap' }}>
      <div style={{ borderRadius: '8px', background: 'rgba(0,0,0,0.2)', padding: '0.5rem' }}>
        <svg width={svgW} height={svgH} viewBox={`0 0 ${svgW} ${svgH}`}>
          {/* Axes */}
          <line x1={pad} y1={pad} x2={pad} y2={pad + chartH} stroke="rgba(255,255,255,0.1)" />
          <line x1={pad} y1={pad + chartH} x2={pad + chartW} y2={pad + chartH} stroke="rgba(255,255,255,0.1)" />

          {/* Perfect calibration diagonal */}
          <line x1={pad} y1={pad + chartH} x2={pad + chartW} y2={pad}
            stroke="#667eea" strokeWidth={1} strokeDasharray="6,4" opacity={0.4} />

          {/* Grid lines */}
          {[0.2, 0.4, 0.6, 0.8].map(v => (
            <g key={v}>
              <line x1={pad} y1={pad + chartH * (1 - v)} x2={pad + chartW} y2={pad + chartH * (1 - v)}
                stroke="rgba(255,255,255,0.03)" />
              <text x={pad - 6} y={pad + chartH * (1 - v) + 3} textAnchor="end" fontSize="9" fill="var(--text-tertiary)">
                {(v * 100).toFixed(0)}%
              </text>
              <text x={pad + chartW * v} y={pad + chartH + 15} textAnchor="middle" fontSize="9" fill="var(--text-tertiary)">
                {(v * 100).toFixed(0)}%
              </text>
            </g>
          ))}

          {/* Axis labels */}
          <text x={pad + chartW / 2} y={svgH - 3} textAnchor="middle" fontSize="10" fill="var(--text-tertiary)">
            Predicerad sannolikhet
          </text>
          <text x={12} y={pad + chartH / 2} textAnchor="middle" fontSize="10" fill="var(--text-tertiary)"
            transform={`rotate(-90, 12, ${pad + chartH / 2})`}>
            Faktiskt utfall
          </text>

          {/* Data points */}
          {points.map((p, i) => {
            const cx = pad + p.predicted * chartW;
            const cy = pad + chartH * (1 - p.actual);
            const r = Math.max(4, Math.min(12, p.count * 2));
            const isOver = p.predicted > p.actual + 0.05;
            const isUnder = p.actual > p.predicted + 0.05;
            const color = isOver ? '#ef4444' : isUnder ? '#10b981' : '#667eea';
            return (
              <g key={i}>
                <circle cx={cx} cy={cy} r={r} fill={`${color}40`} stroke={color} strokeWidth={1.5} />
                <text x={cx} y={cy - r - 3} textAnchor="middle" fontSize="8" fill={color}>
                  n={p.count}
                </text>
              </g>
            );
          })}

          {/* Legend */}
          <text x={pad + chartW - 5} y={pad + 15} textAnchor="end" fontSize="8" fill="#667eea" opacity={0.5}>
            Perfekt kalibrering ↗
          </text>
        </svg>
      </div>

      {/* Stats panel */}
      <div style={{ flex: 1, minWidth: '150px' }}>
        <div style={{ marginBottom: '0.75rem' }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>Brier Score</div>
          <div style={{
            fontSize: '1.5rem', fontWeight: 700,
            color: confidence.brier_score < 0.15 ? '#10b981' : confidence.brier_score < 0.25 ? '#ffa502' : '#ef4444',
          }}>{confidence.brier_score?.toFixed(3)}</div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>{confidence.brier_interpretation}</div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
          <MetricCard label="Prediktioner" value={confidence.total_predictions || 0} />
          <MetricCard label="Överkonfident" value={confidence.overconfident_bins || 0} color="#ef4444" />
          <MetricCard label="Underkonfident" value={confidence.underconfident_bins || 0} color="#10b981" />
        </div>
        {confidence.diagnosis && (
          <div style={{ marginTop: '0.5rem', fontSize: '0.72rem', color: 'var(--text-tertiary)', fontStyle: 'italic' }}>
            {confidence.diagnosis}
          </div>
        )}
      </div>
    </div>
  );
}


// ---- NARRATIVE TIMELINE ----
function NarrativeTimeline() {
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    api.getNarratives().then(setData).catch(() => {});
  }, []);

  if (!data) {
    return <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-tertiary)', fontSize: '0.85rem' }}>Laddar narrativ...</div>;
  }

  const narratives = data.narratives || [];
  if (narratives.length === 0) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-tertiary)', fontSize: '0.85rem' }}>
        📰 Inga aktiva narrativ. Kör pipeline för att upptäcka marknadstrender.
      </div>
    );
  }

  const phaseColors: Record<string, string> = {
    EMERGENCE: '#a78bfa', ACCELERATION: '#10b981', CONSENSUS: '#f59e0b',
    EXTREME_CONSENSUS: '#ef4444', REVERSAL: '#ff0000',
  };

  // risk_level is an object: {level: "HÖG", message: "..."}
  const riskLevel = typeof data.risk_level === 'object' ? data.risk_level?.level : data.risk_level;
  const riskColor = riskLevel === 'HÖG' ? '#ef4444' : riskLevel === 'FÖRHÖJD' ? '#ffa502' : '#10b981';

  return (
    <div>
      <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', marginBottom: '0.75rem' }}>
        Riskbedömning: <strong style={{ color: riskColor }}>{riskLevel || 'NORMAL'}</strong> • {data.active_narratives || 0} aktiva narrativ
      </div>

      {/* Timeline */}
      <div style={{ position: 'relative', paddingLeft: '20px' }}>
        <div style={{
          position: 'absolute', left: '8px', top: 0, bottom: 0, width: '2px',
          background: 'linear-gradient(180deg, #a78bfa, #667eea, #10b981)',
          borderRadius: '2px',
        }} />

        {narratives.slice(0, 6).map((n: any, i: number) => {
          const phase = n.phase || 'EMERGENCE';
          const color = phaseColors[phase] || '#667eea';
          return (
            <div key={i} style={{ position: 'relative', marginBottom: '0.75rem', paddingLeft: '1.25rem' }}>
              <div style={{
                position: 'absolute', left: '-4px', top: '6px', width: '10px', height: '10px',
                borderRadius: '50%', background: color, border: '2px solid var(--bg-primary)',
              }} />

              <div style={{
                padding: '0.5rem 0.75rem', borderRadius: '6px',
                background: `${color}08`, borderLeft: `2px solid ${color}`,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem', flexWrap: 'wrap' }}>
                  <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {n.phase_icon || '📊'} {n.title || `Narrativ ${i + 1}`}
                  </span>
                  <span style={{
                    fontSize: '0.6rem', padding: '0.1rem 0.4rem', borderRadius: '4px',
                    background: `${color}20`, color, fontWeight: 700,
                  }}>{phase}</span>
                  <span style={{ fontSize: '0.6rem', color: 'var(--text-tertiary)' }}>
                    {n.consensus_pct?.toFixed(0)}% konsensus
                  </span>
                  {n.direction && (
                    <span style={{
                      fontSize: '0.55rem', padding: '0.1rem 0.3rem', borderRadius: '3px',
                      background: n.direction === 'BULLISH' ? 'rgba(16,185,129,0.1)' : n.direction === 'BEARISH' ? 'rgba(239,68,68,0.1)' : 'rgba(255,255,255,0.04)',
                      color: n.direction === 'BULLISH' ? '#10b981' : n.direction === 'BEARISH' ? '#ef4444' : 'var(--text-tertiary)',
                    }}>{n.direction}</span>
                  )}
                </div>
                {n.assets?.length > 0 && (
                  <div style={{ display: 'flex', gap: '0.2rem', flexWrap: 'wrap' }}>
                    {n.assets.map((a: string, j: number) => (
                      <span key={j} style={{
                        fontSize: '0.6rem', padding: '0.08rem 0.3rem', borderRadius: '3px',
                        background: 'rgba(255,255,255,0.04)', color: 'var(--text-tertiary)',
                      }}>{a}</span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Signals */}
      {data.signals?.length > 0 && (
        <div style={{ marginTop: '0.75rem' }}>
          <div style={{ fontSize: '0.75rem', fontWeight: 600, marginBottom: '0.4rem', color: 'var(--text-secondary)' }}>
            📡 Handlingssignaler
          </div>
          <div style={{ display: 'flex', gap: '0.3rem', flexWrap: 'wrap' }}>
            {data.signals.slice(0, 5).map((s: any, i: number) => (
              <span key={i} style={{
                padding: '0.2rem 0.5rem', borderRadius: '5px', fontSize: '0.65rem',
                background: s.direction === 'BULLISH' ? 'rgba(16,185,129,0.08)' : s.direction === 'BEARISH' ? 'rgba(239,68,68,0.08)' : 'rgba(255,255,255,0.04)',
                color: s.direction === 'BULLISH' ? '#10b981' : s.direction === 'BEARISH' ? '#ef4444' : 'var(--text-tertiary)',
                fontWeight: 600,
              }}>
                {s.narrative}: {s.action}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}


// ---- CONVEXITY POSITIONS ----
function ConvexitySection() {
  const [positions, setPositions] = useState<any[]>([]);

  useEffect(() => {
    api.getConvexPositions().then(data => {
      setPositions(Array.isArray(data) ? data : []);
    }).catch(() => {});
  }, []);

  if (positions.length === 0) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-tertiary)', fontSize: '0.85rem' }}>
        🎯 Inga konvexa positioner hittade. Kör pipeline och bygg event trees för att identifiera positioner som tjänar i alla scenarier.
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
      <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', marginBottom: '0.25rem' }}>
        Positioner som tjänar i de flesta scenarier (konvexitet):
      </div>
      {positions.slice(0, 6).map((p: any, i: number) => {
        const score = p.convexity_score || p.avg_impact || 0;
        const barWidth = Math.min(Math.abs(score) * 20, 100);
        return (
          <div key={i} style={{
            display: 'flex', alignItems: 'center', gap: '0.5rem',
            padding: '0.5rem 0.75rem', borderRadius: '6px',
            background: 'rgba(16,185,129,0.04)', borderLeft: '3px solid #10b981',
          }}>
            <span style={{ width: '80px', fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              {p.asset || `Position ${i + 1}`}
            </span>
            <span style={{
              fontSize: '0.65rem', padding: '0.1rem 0.4rem', borderRadius: '4px',
              background: 'rgba(16,185,129,0.12)', color: '#10b981', fontWeight: 700,
            }}>
              {p.action || 'ÖKA'}
            </span>
            <div style={{ flex: 1, height: '6px', background: 'rgba(255,255,255,0.04)', borderRadius: '3px' }}>
              <div style={{
                width: `${barWidth}%`, height: '100%', borderRadius: '3px',
                background: 'linear-gradient(90deg, #10b981, #a78bfa)',
              }} />
            </div>
            <span style={{ fontSize: '0.72rem', fontWeight: 600, color: '#10b981' }}>
              {score > 0 ? '+' : ''}{typeof score === 'number' ? score.toFixed(1) : score}
            </span>
            {p.scenarios_positive && (
              <span style={{ fontSize: '0.6rem', color: 'var(--text-tertiary)' }}>
                {p.scenarios_positive}/{p.scenarios_total} scenarier
              </span>
            )}
          </div>
        );
      })}
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

        {/* Row 5: Narrative + Convexity */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
          <CollapsibleSection
            title="Marknadnarrativ"
            icon={<Eye size={18} color="#a78bfa" />}
            badge="Livscykel"
            badgeColor="#a78bfa"
          >
            <NarrativeTimeline />
          </CollapsibleSection>

          <CollapsibleSection
            title="Konvexa Positioner"
            icon={<TrendingUp size={18} color="#10b981" />}
            badge="Alla scenarier"
            badgeColor="#10b981"
          >
            <ConvexitySection />
          </CollapsibleSection>
        </div>

        {/* Row 6: Causal Flow + Lead-Lag Network */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
          <CollapsibleSection
            title="Kausala Kedjor"
            icon={<Activity size={18} color="#667eea" />}
            badge="Flödesdiagram"
            badgeColor="#667eea"
          >
            <CausalFlowDiagram />
          </CollapsibleSection>

          <CollapsibleSection
            title="Lead-Lag Nätverk"
            icon={<TrendingUp size={18} color="#10b981" />}
            badge="Nätverksgraf"
            badgeColor="#10b981"
          >
            <LeadLagNetwork />
          </CollapsibleSection>
        </div>

        {/* Row 7: Calibration + Meta */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
          <CollapsibleSection
            title="Konfidenskalibrering"
            icon={<Eye size={18} color="#a78bfa" />}
            badge="Kalibreringsplot"
            badgeColor="#a78bfa"
          >
            <CalibrationPlot />
          </CollapsibleSection>

          <CollapsibleSection
            title="Meta-learning & Vikter"
            icon={<TrendingUp size={18} color="#a78bfa" />}
            defaultOpen={false}
          >
            <MetaConfidenceSection />
          </CollapsibleSection>
        </div>
      </div>
    </main>
  );
}

