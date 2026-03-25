import { useState, useEffect } from 'react';
import { Calculator, DollarSign, RefreshCw, TrendingDown, ChevronDown, ChevronRight, BarChart3 } from 'lucide-react';
import { api } from '../api/client';

// ============================================================
// OPERATIONAL TOOLS PAGE — /tools
// Skatteoptimering · Valutahedge · Rebalansering · Drawdown
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


// ---- TAX OPTIMIZER SECTION ----
function TaxOptimizerSection() {
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const sampleHoldings = [
    { asset: "OMXS30 ETF", value: 150000, gain_pct: 15, annual_return_est: 0.08, dividend_yield: 0.03, current_account: "ISK", holding_period_months: 24 },
    { asset: "S&P 500 ETF", value: 200000, gain_pct: 35, annual_return_est: 0.10, dividend_yield: 0.015, current_account: "ISK", holding_period_months: 36 },
    { asset: "Bitcoin", value: 100000, gain_pct: 120, annual_return_est: 0.15, dividend_yield: 0, current_account: "DEPÅ", holding_period_months: 18 },
    { asset: "Obligation ETF", value: 80000, gain_pct: -2, annual_return_est: 0.02, dividend_yield: 0.025, current_account: "ISK", holding_period_months: 12 },
    { asset: "Guld ETC", value: 70000, gain_pct: 22, annual_return_est: 0.06, dividend_yield: 0, current_account: "ISK", holding_period_months: 8 },
  ];

  const runAnalysis = async () => {
    setLoading(true);
    try {
      const res = await api.getTaxComparison(sampleHoldings, 600000);
      setResult(res);
    } catch { /* ignore */ }
    setLoading(false);
  };

  useEffect(() => { runAnalysis(); }, []);

  const recColors: Record<string, string> = {
    'ISK': '#10b981', 'DEPÅ': '#f59e0b', 'DEPÅ (BEHÅLL)': '#f59e0b',
    'DEPÅ (FLYTTA EJ)': '#ef4444', 'ISK (FLYTTA)': '#10b981',
  };

  return (
    <div>
      {loading && <div style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>Beräknar skatteoptimal placering...</div>}

      {result && !result.error && (
        <>
          {/* Parameters */}
          <div style={{
            display: 'flex', gap: '1rem', flexWrap: 'wrap', marginBottom: '1rem',
            padding: '0.6rem 1rem', borderRadius: '8px', background: 'rgba(16,185,129,0.04)',
            border: '1px solid rgba(16,185,129,0.1)', fontSize: '0.72rem', color: 'var(--text-tertiary)',
          }}>
            <span>📅 Skatteår: <strong style={{ color: 'var(--text-primary)' }}>2026</strong></span>
            <span>📊 Schablonintäkt: <strong style={{ color: '#10b981' }}>{result.parameters?.schablonintakt}</strong></span>
            <span>💰 Effektiv ISK: <strong style={{ color: '#10b981' }}>{result.parameters?.effektiv_isk_skatt}</strong></span>
            <span>🎯 Breakeven: <strong style={{ color: '#ffa502' }}>{result.parameters?.breakeven_avkastning}</strong></span>
            <span>🛡 Grundnivå: <strong style={{ color: '#a78bfa' }}>{result.parameters?.skattefri_grundniva}</strong></span>
          </div>

          {/* Summary */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '0.5rem', marginBottom: '1rem' }}>
            <MetricCard label="Total portfölj" value={`${(result.summary?.total_portfolio_kr / 1000).toFixed(0)}k kr`} />
            <MetricCard label="ISK-skatt/år" value={`${result.summary?.total_isk_tax_kr?.toLocaleString()} kr`} color="#f59e0b" />
            <MetricCard label="Depå-skatt/år" value={`${result.summary?.total_depa_tax_kr?.toLocaleString()} kr`} color="#ef4444" />
            <MetricCard label="Besparing/år" value={`${result.summary?.total_yearly_saving_kr?.toLocaleString()} kr`} color="#10b981" sub="Med optimal placering" />
          </div>

          {/* Recommendations */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
            {result.recommendations?.map((rec: any, i: number) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.5rem 0.75rem',
                borderRadius: '6px', background: 'rgba(255,255,255,0.015)',
                borderLeft: `3px solid ${recColors[rec.recommended] || '#667eea'}`,
              }}>
                <span style={{ fontSize: '0.8rem', fontWeight: 600, width: '120px', color: 'var(--text-primary)' }}>
                  {rec.asset}
                </span>
                <span style={{
                  fontSize: '0.65rem', padding: '0.1rem 0.5rem', borderRadius: '4px', fontWeight: 700,
                  background: `${recColors[rec.recommended] || '#667eea'}18`,
                  color: recColors[rec.recommended] || '#667eea',
                  whiteSpace: 'nowrap',
                }}>{rec.recommended}</span>
                <span style={{ flex: 1, fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>
                  {rec.reasoning?.slice(0, 80)}
                </span>
                <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#10b981', whiteSpace: 'nowrap' }}>
                  +{rec.yearly_saving_kr?.toLocaleString()} kr
                </span>
              </div>
            ))}
          </div>

          {/* Breakeven Table */}
          {result.breakeven_table && (
            <div style={{ marginTop: '1rem' }}>
              <div style={{ fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--text-secondary)' }}>
                📊 Breakeven ISK vs Depå
              </div>
              <div style={{ display: 'flex', gap: '0.3rem', flexWrap: 'wrap' }}>
                {result.breakeven_table.map((row: any, i: number) => (
                  <div key={i} style={{
                    padding: '0.3rem 0.5rem', borderRadius: '5px', fontSize: '0.65rem', textAlign: 'center',
                    background: row.bast === 'ISK' ? 'rgba(16,185,129,0.08)' : row.bast === 'DEPÅ' ? 'rgba(239,68,68,0.08)' : 'rgba(255,255,255,0.04)',
                    color: row.bast === 'ISK' ? '#10b981' : row.bast === 'DEPÅ' ? '#ef4444' : '#ffa502',
                    border: `1px solid ${row.bast === 'ISK' ? 'rgba(16,185,129,0.15)' : row.bast === 'DEPÅ' ? 'rgba(239,68,68,0.15)' : 'rgba(255,255,255,0.06)'}`,
                  }}>
                    {row.avkastning} → <strong>{row.bast}</strong>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}


// ---- CURRENCY HEDGE SECTION ----
function CurrencyHedgeSection() {
  const [result, setResult] = useState<any>(null);

  useEffect(() => {
    // Use example portfolio weights
    const weights = { sp500: 30, btc: 15, gold: 10, oil: 5, 'us10y': 10, eurusd: 5, silver: 5 };
    api.getCurrencyHedge(weights).then(setResult).catch(() => {});
  }, []);

  if (!result || result.error) {
    return <div style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>Laddar valutaexponering...</div>;
  }

  return (
    <div>
      {/* Overview bar */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: '0.5rem', marginBottom: '1rem' }}>
        <MetricCard label="🇸🇪 SEK" value={`${result.total_sek_pct}%`} color="#10b981" sub="Hem-valuta" />
        <MetricCard label="🌍 Utländsk" value={`${result.total_foreign_pct}%`}
          color={result.total_foreign_pct > 60 ? '#ef4444' : result.total_foreign_pct > 40 ? '#ffa502' : '#10b981'} sub="Valutarisk" />
      </div>

      {/* Exposure bars */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', marginBottom: '1rem' }}>
        {result.exposures?.map((exp: any, i: number) => {
          const isForiegn = exp.currency !== 'SEK';
          const barWidth = Math.min(exp.weight_pct, 100);
          const riskColor = exp.risk?.includes('HÖG') ? '#ef4444' : exp.risk?.includes('MEDEL') ? '#ffa502' : '#10b981';
          return (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.4rem 0.6rem',
              borderRadius: '6px', background: 'rgba(255,255,255,0.015)',
            }}>
              <span style={{ width: '50px', fontSize: '0.8rem', fontWeight: 700, color: isForiegn ? '#f59e0b' : '#10b981' }}>
                {exp.currency}
              </span>
              <div style={{ flex: 1, height: '8px', background: 'rgba(255,255,255,0.04)', borderRadius: '4px' }}>
                <div style={{
                  width: `${barWidth}%`, height: '100%', borderRadius: '4px',
                  background: isForiegn ? `linear-gradient(90deg, ${riskColor}, ${riskColor}80)` : '#10b981',
                  transition: 'width 0.5s ease',
                }} />
              </div>
              <span style={{ width: '45px', fontSize: '0.78rem', fontWeight: 600, textAlign: 'right' }}>
                {exp.weight_pct}%
              </span>
              <span style={{ fontSize: '0.6rem', color: riskColor, width: '90px' }}>
                {exp.risk}
              </span>
            </div>
          );
        })}
      </div>

      {/* FX Impact Scenarios */}
      {result.fx_impact_table && (
        <div>
          <div style={{ fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--text-secondary)' }}>
            💱 Valutascenarier — Påverkan på portföljen
          </div>
          <div style={{ display: 'flex', gap: '0.3rem', flexWrap: 'wrap' }}>
            {result.fx_impact_table.map((s: any, i: number) => (
              <div key={i} style={{
                padding: '0.35rem 0.6rem', borderRadius: '6px', fontSize: '0.72rem', textAlign: 'center',
                background: s.impact_pct > 0 ? 'rgba(16,185,129,0.06)' : 'rgba(239,68,68,0.06)',
                border: `1px solid ${s.impact_pct > 0 ? 'rgba(16,185,129,0.12)' : 'rgba(239,68,68,0.12)'}`,
              }}>
                <div style={{ fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.15rem' }}>{s.name}</div>
                <div style={{ fontWeight: 700, color: s.impact_pct > 0 ? '#10b981' : '#ef4444' }}>
                  {s.impact_pct > 0 ? '+' : ''}{s.impact_pct}%
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recommendations */}
      {result.recommendations?.length > 0 && (
        <div style={{ marginTop: '1rem' }}>
          {result.recommendations.map((rec: any, i: number) => (
            <div key={i} style={{
              padding: '0.5rem 0.75rem', borderRadius: '6px', marginBottom: '0.3rem',
              background: rec.action === 'KRITISKT' ? 'rgba(239,68,68,0.06)' : 'rgba(255,165,2,0.06)',
              borderLeft: `3px solid ${rec.action === 'KRITISKT' ? '#ef4444' : '#ffa502'}`,
              fontSize: '0.78rem', color: 'var(--text-secondary)',
            }}>
              <strong style={{ color: rec.action === 'KRITISKT' ? '#ef4444' : '#ffa502' }}>{rec.action}</strong>: {rec.message}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


// ---- REBALANCE SECTION ----
function RebalanceSection() {
  const [result, setResult] = useState<any>(null);

  useEffect(() => {
    const current = { sp500: 35, btc: 18, gold: 8, oil: 6, bonds: 20, cash: 13 };
    const target = { sp500: 30, btc: 15, gold: 10, oil: 5, bonds: 25, cash: 15 };
    api.shouldRebalance(current, target, false, 600000).then(setResult).catch(() => {});
  }, []);

  if (!result) return <div style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>Kontrollerar rebalansering...</div>;

  const urgencyColors: Record<string, string> = { 'HÖG': '#ef4444', 'MEDEL': '#ffa502', 'LÅG': '#10b981' };

  return (
    <div>
      {/* Decision banner */}
      <div style={{
        padding: '0.75rem 1rem', borderRadius: '8px', marginBottom: '1rem',
        background: result.rebalance ? 'rgba(239,68,68,0.06)' : 'rgba(16,185,129,0.06)',
        border: `1px solid ${result.rebalance ? 'rgba(239,68,68,0.15)' : 'rgba(16,185,129,0.15)'}`,
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <span style={{
          fontSize: '1rem', fontWeight: 700,
          color: result.rebalance ? '#ef4444' : '#10b981',
        }}>
          {result.rebalance ? '⚠️ REBALANSERA' : '✅ OK — Ingen rebalansering behövs'}
        </span>
        <span style={{
          fontSize: '0.7rem', padding: '0.15rem 0.5rem', borderRadius: '6px', fontWeight: 700,
          background: `${urgencyColors[result.urgency]}18`, color: urgencyColors[result.urgency],
        }}>{result.urgency}</span>
      </div>

      {/* Metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: '0.5rem', marginBottom: '1rem' }}>
        <MetricCard label="Max drift" value={`${result.max_drift_pct}%`}
          color={result.max_drift_pct > 5 ? '#ef4444' : '#10b981'} />
        <MetricCard label="Total drift" value={`${result.total_drift_pct}%`}
          color={result.total_drift_pct > 10 ? '#ef4444' : '#ffa502'} />
        <MetricCard label="Dagar sedan" value={result.days_since_last ?? '—'}
          sub={result.days_since_last ? 'dagar' : 'Aldrig'} />
        <MetricCard label="Rek. trades" value={result.recommended_trades || 0} />
      </div>

      {/* Reasons */}
      {result.reasons?.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem', marginBottom: '1rem' }}>
          {result.reasons.map((r: string, i: number) => (
            <div key={i} style={{
              padding: '0.35rem 0.6rem', borderRadius: '5px', fontSize: '0.75rem',
              background: 'rgba(255,255,255,0.02)', color: 'var(--text-secondary)',
              borderLeft: '2px solid #667eea',
            }}>📋 {r}</div>
          ))}
        </div>
      )}

      {/* Drifted positions */}
      {result.drifted_positions?.length > 0 && (
        <div>
          <div style={{ fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--text-secondary)' }}>
            📊 Driftade positioner
          </div>
          <div style={{ display: 'flex', gap: '0.3rem', flexWrap: 'wrap' }}>
            {result.drifted_positions.map((d: any, i: number) => (
              <span key={i} style={{
                padding: '0.2rem 0.5rem', borderRadius: '5px', fontSize: '0.72rem', fontWeight: 600,
                background: 'rgba(239,68,68,0.08)', color: '#ef4444',
              }}>
                {d.asset}: ±{d.drift_pct}%
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}


// ---- DRAWDOWN RECOVERY SECTION ----
function DrawdownSection() {
  const [drawdown, setDrawdown] = useState(12);
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const analyze = async () => {
    setLoading(true);
    try {
      const res = await api.getDrawdownRecovery(drawdown);
      setResult(res);
    } catch { /* ignore */ }
    setLoading(false);
  };

  useEffect(() => { analyze(); }, []);

  const severityColors: Record<string, string> = {
    'LÅG': '#10b981', 'MEDEL': '#ffa502', 'HÖG': '#ef4444', 'EXTREM': '#ff0000',
  };

  return (
    <div>
      {/* Input */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', alignItems: 'center' }}>
        <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>Drawdown %:</div>
        <input
          type="number" value={drawdown} onChange={e => setDrawdown(Number(e.target.value))}
          style={{
            width: '70px', padding: '0.5rem', borderRadius: '6px',
            background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
            color: 'var(--text-primary)', fontSize: '0.85rem', textAlign: 'center',
          }}
        />
        <button onClick={analyze} disabled={loading} style={{
          padding: '0.5rem 1rem', borderRadius: '6px', cursor: 'pointer',
          background: 'linear-gradient(135deg, #f59e0b, #ef4444)', border: 'none',
          color: '#fff', fontWeight: 600, fontSize: '0.8rem',
        }}>
          {loading ? 'Beräknar...' : 'Uppskatta'}
        </button>
      </div>

      {result && result.status !== 'INGEN_DRAWDOWN' && (
        <>
          {/* Severity + metrics */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.5rem', marginBottom: '1rem' }}>
            <MetricCard label="Allvarlighet" value={result.severity}
              color={severityColors[result.severity]} />
            <MetricCard label="Beräknad tid" value={`${result.estimated_recovery_days}d`}
              sub="Matematisk uppskattning" />
            <MetricCard label="Monte Carlo" value={`${result.monte_carlo_median_days}d`}
              sub="Median (5000 sim)" color="#a78bfa" />
            <MetricCard label="Historiskt snitt" value={`${result.historical_avg_days}d`}
              sub={result.historical_range} />
          </div>

          {/* Recovery probabilities */}
          <div style={{ marginBottom: '1rem' }}>
            <div style={{ fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--text-secondary)' }}>
              📈 Sannolikhet för återhämtning
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              {[
                { label: '30 dagar', prob: result.recovery_probability?.within_30_days },
                { label: '90 dagar', prob: result.recovery_probability?.within_90_days },
                { label: '180 dagar', prob: result.recovery_probability?.within_180_days },
              ].map((p, i) => (
                <div key={i} style={{
                  flex: 1, minWidth: '120px', padding: '0.5rem', borderRadius: '8px',
                  background: 'rgba(255,255,255,0.02)', textAlign: 'center',
                }}>
                  <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)', marginBottom: '0.25rem' }}>{p.label}</div>
                  <div style={{
                    fontSize: '1.3rem', fontWeight: 700,
                    color: p.prob > 70 ? '#10b981' : p.prob > 40 ? '#ffa502' : '#ef4444',
                  }}>{p.prob}%</div>
                  {/* Progress bar */}
                  <div style={{ height: '4px', background: 'rgba(255,255,255,0.04)', borderRadius: '2px', marginTop: '0.3rem' }}>
                    <div style={{
                      width: `${p.prob}%`, height: '100%', borderRadius: '2px',
                      background: p.prob > 70 ? '#10b981' : p.prob > 40 ? '#ffa502' : '#ef4444',
                    }} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Advice */}
          {result.advice && (
            <div style={{
              padding: '0.6rem 0.75rem', borderRadius: '6px', fontSize: '0.78rem',
              background: 'rgba(102,126,234,0.06)', borderLeft: '3px solid #667eea',
              color: 'var(--text-secondary)',
            }}>
              💡 {result.advice}
            </div>
          )}
        </>
      )}

      {result?.status === 'INGEN_DRAWDOWN' && (
        <div style={{ padding: '1rem', textAlign: 'center', color: '#10b981', fontSize: '0.85rem' }}>
          ✅ {result.message}
        </div>
      )}
    </div>
  );
}


// ---- API COST SECTION ----
function CostSection() {
  const [cost, setCost] = useState<any>(null);

  useEffect(() => {
    api.getCostSummary().then(setCost).catch(() => {});
  }, []);

  if (!cost) return <div style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>Laddar kostnadsdata...</div>;

  const budgetColor = cost.budget_used_pct > 90 ? '#ef4444' : cost.budget_used_pct > 60 ? '#ffa502' : '#10b981';

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: '0.5rem', marginBottom: '1rem' }}>
        <MetricCard label="Idag" value={`$${cost.today_cost_usd}`} sub={`${cost.today_calls} anrop`} />
        <MetricCard label="Denna månad" value={`$${cost.month_cost_usd}`} sub={`${cost.month_calls} anrop`} color={budgetColor} />
        <MetricCard label="Budget kvar" value={`$${cost.budget_remaining_usd}`} sub={`${cost.budget_used_pct}% använt`} color={budgetColor} />
        <MetricCard label="Prognos" value={`$${cost.projected_month_usd}`}
          sub={cost.over_budget ? '⚠️ Överskrider!' : 'Inom budget'} color={cost.over_budget ? '#ef4444' : '#10b981'} />
      </div>

      {/* Budget progress bar */}
      <div style={{ marginBottom: '1rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', color: 'var(--text-tertiary)', marginBottom: '0.3rem' }}>
          <span>Månadsbudget</span>
          <span>${cost.month_cost_usd} / ${cost.budget_usd}</span>
        </div>
        <div style={{ height: '8px', background: 'rgba(255,255,255,0.04)', borderRadius: '4px' }}>
          <div style={{
            width: `${Math.min(cost.budget_used_pct, 100)}%`, height: '100%', borderRadius: '4px',
            background: budgetColor, transition: 'width 0.5s ease',
          }} />
        </div>
      </div>

      {/* Per API breakdown */}
      {cost.per_api && Object.keys(cost.per_api).length > 0 && (
        <div>
          <div style={{ fontSize: '0.75rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--text-secondary)' }}>Per API</div>
          <div style={{ display: 'flex', gap: '0.3rem', flexWrap: 'wrap' }}>
            {Object.entries(cost.per_api).map(([apiName, apiCost]: [string, any]) => (
              <span key={apiName} style={{
                padding: '0.2rem 0.5rem', borderRadius: '5px', fontSize: '0.65rem',
                background: 'rgba(255,255,255,0.03)', color: 'var(--text-tertiary)',
              }}>
                {apiName}: ${apiCost}
              </span>
            ))}
          </div>
        </div>
      )}

      {cost.warning && (
        <div style={{
          marginTop: '0.75rem', padding: '0.4rem 0.6rem', borderRadius: '5px',
          background: 'rgba(239,68,68,0.06)', borderLeft: '2px solid #ef4444',
          fontSize: '0.75rem', color: '#ef4444',
        }}>⚠️ {cost.warning}</div>
      )}
    </div>
  );
}


// ============================================================
// MAIN PAGE
// ============================================================
export default function ToolsPage() {
  return (
    <main className="container" style={{ paddingTop: '2rem', paddingBottom: '6rem' }}>
      {/* Header */}
      <section className="glass-panel animate-fade-in" style={{
        padding: '1.5rem 2rem', marginBottom: '1.5rem',
        background: 'linear-gradient(135deg, rgba(16,185,129,0.08) 0%, rgba(245,158,11,0.08) 100%)',
        borderLeft: '4px solid #10b981',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <Calculator size={32} color="#10b981" />
          <div>
            <h2 style={{ margin: 0, fontSize: '1.5rem' }}>
              <span style={{ background: 'linear-gradient(135deg, #10b981, #f59e0b)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                Operativa Verktyg
              </span>
            </h2>
            <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>
              Skatteoptimering · Valutahedge · Rebalansering · Drawdown · API-kostnader
            </p>
          </div>
        </div>
      </section>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {/* Tax + Currency */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
          <CollapsibleSection
            title="Skatteoptimering 2026"
            icon={<Calculator size={18} color="#10b981" />}
            badge="ISK vs Depå"
            badgeColor="#10b981"
          >
            <TaxOptimizerSection />
          </CollapsibleSection>

          <CollapsibleSection
            title="Valutahedge"
            icon={<DollarSign size={18} color="#f59e0b" />}
            badge="SEK-exponering"
            badgeColor="#f59e0b"
          >
            <CurrencyHedgeSection />
          </CollapsibleSection>
        </div>

        {/* Rebalance + Drawdown */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
          <CollapsibleSection
            title="Smart Rebalansering"
            icon={<RefreshCw size={18} color="#667eea" />}
            badge="Drift-analys"
            badgeColor="#667eea"
          >
            <RebalanceSection />
          </CollapsibleSection>

          <CollapsibleSection
            title="Drawdown & Återhämtning"
            icon={<TrendingDown size={18} color="#ef4444" />}
            badge="Monte Carlo"
            badgeColor="#ef4444"
          >
            <DrawdownSection />
          </CollapsibleSection>
        </div>

        {/* API Costs */}
        <CollapsibleSection
          title="AI-kostnader"
          icon={<BarChart3 size={18} color="#a78bfa" />}
          badge="Budget"
          badgeColor="#a78bfa"
          defaultOpen={false}
        >
          <CostSection />
        </CollapsibleSection>
      </div>
    </main>
  );
}
