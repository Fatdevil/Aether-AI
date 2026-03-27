import { useState, useEffect } from 'react';
import { Briefcase, TrendingUp, TrendingDown, Minus, ShieldAlert, Activity } from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, AreaChart, Area, XAxis, YAxis, CartesianGrid } from 'recharts';
import type { Asset } from '../types';
import { getScoreColor, getRecommendation } from '../types';
import { API_BASE } from '../api/client';

interface PortfolioPageProps {
  portfolio: {
    allocations: Array<{
      assetId: string;
      name: string;
      weight: number;
      action: 'buy' | 'sell' | 'hold';
      color: string;
      score?: number;
    }>;
    cash: number;
    motivation: string;
  };
  assets: Asset[];
  marketState: {
    overallScore: number;
    overallSummary: string;
    lastUpdated: string;
  };
}

/* ===== Risk Panel Component ===== */
function RiskPanel() {
  const [risk, setRisk] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/portfolio/risk`)
      .then(r => r.json())
      .then(data => {
        setRisk(data?.risk_metrics || null);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="glass-panel" style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--text-tertiary)' }}>
      Beräknar riskmetriker...
    </div>
  );

  if (!risk || !risk.cvar) return null;

  const cvar = risk.cvar;
  const mc = risk.monte_carlo;
  const fanChart = mc?.fan_chart || [];

  const riskColor = risk.risk_level === 'hög' ? '#ef4444'
    : risk.risk_level === 'medel' ? '#f59e0b' : '#10b981';

  return (
    <div style={{ marginTop: '2rem' }}>
      <h3 style={{ margin: '0 0 1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <Activity size={20} style={{ color: riskColor }} />
        Matematisk Riskanalys
        <span style={{
          fontSize: '0.7rem', padding: '0.15rem 0.5rem', borderRadius: '4px',
          background: `${riskColor}22`, color: riskColor, fontWeight: 600,
        }}>
          {risk.risk_level?.toUpperCase()}
        </span>
      </h3>

      {/* CVaR + Sharpe + MaxDD + Volatility */}
      <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '0.75rem', marginBottom: '1.5rem' }}>
        <div className="glass-panel" style={{ padding: '1rem', textAlign: 'center' }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', marginBottom: '0.3rem' }}>CVaR 95%</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#ef4444' }}>{cvar.cvar_95}%</div>
          <div style={{ fontSize: '0.6rem', color: 'var(--text-tertiary)' }}>Genomsn. förlust vid kris</div>
        </div>
        <div className="glass-panel" style={{ padding: '1rem', textAlign: 'center' }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', marginBottom: '0.3rem' }}>VaR 95%</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#f59e0b' }}>{cvar.var_95}%</div>
          <div style={{ fontSize: '0.6rem', color: 'var(--text-tertiary)' }}>Max daglig förlust (95%)</div>
        </div>
        <div className="glass-panel" style={{ padding: '1rem', textAlign: 'center' }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', marginBottom: '0.3rem' }}>Sharpe Ratio</div>
          <div style={{
            fontSize: '1.5rem', fontWeight: 700,
            color: risk.sharpe_ratio > 1 ? '#10b981' : risk.sharpe_ratio > 0 ? '#f59e0b' : '#ef4444',
          }}>{risk.sharpe_ratio}</div>
          <div style={{ fontSize: '0.6rem', color: 'var(--text-tertiary)' }}>
            {risk.sharpe_ratio > 2 ? 'Utmärkt' : risk.sharpe_ratio > 1 ? 'Bra' : risk.sharpe_ratio > 0 ? 'Svag' : 'Negativ'}
          </div>
        </div>
        <div className="glass-panel" style={{ padding: '1rem', textAlign: 'center' }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', marginBottom: '0.3rem' }}>Max Drawdown</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#ef4444' }}>
            {risk.max_drawdown?.max_drawdown_pct}%
          </div>
          <div style={{ fontSize: '0.6rem', color: 'var(--text-tertiary)' }}>Största fall (90d)</div>
        </div>
        <div className="glass-panel" style={{ padding: '1rem', textAlign: 'center' }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', marginBottom: '0.3rem' }}>Volatilitet</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--accent-cyan)' }}>
            {risk.annualized_volatility}%
          </div>
          <div style={{ fontSize: '0.6rem', color: 'var(--text-tertiary)' }}>Årlig (annualiserad)</div>
        </div>
      </div>

      {/* Monte Carlo Section */}
      {mc && fanChart.length > 0 && (
        <div className="glass-panel" style={{ padding: '1.25rem' }}>
          <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            🎲 Monte Carlo Simulering
            <span style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)', fontWeight: 400 }}>
              {mc.simulations?.toLocaleString()} scenarier · {mc.days} dagar
            </span>
          </h4>

          {/* Probability indicator */}
          <div className="flex items-center gap-4" style={{ marginBottom: '1rem', flexWrap: 'wrap' }}>
            <div style={{
              padding: '0.5rem 1rem', borderRadius: '8px',
              background: mc.positive_prob > 0.5 ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)',
              border: `1px solid ${mc.positive_prob > 0.5 ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}`,
            }}>
              <span style={{ fontSize: '1.2rem', fontWeight: 700, color: mc.positive_prob > 0.5 ? '#10b981' : '#ef4444' }}>
                {(mc.positive_prob * 100).toFixed(0)}%
              </span>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginLeft: '0.4rem' }}>
                chans att vara positiv om {mc.days}d
              </span>
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>
              Median: <b style={{ color: mc.median_return_pct > 0 ? '#10b981' : '#ef4444' }}>{mc.median_return_pct > 0 ? '+' : ''}{mc.median_return_pct}%</b>
              {' · '}Worst 5%: <b style={{ color: '#ef4444' }}>{mc.worst_5pct}%</b>
              {' · '}Best 5%: <b style={{ color: '#10b981' }}>+{mc.best_5pct}%</b>
            </div>
          </div>

          {/* Fan chart */}
          <div style={{ height: '250px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={fanChart}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis
                  dataKey="day" tick={{ fill: 'var(--text-tertiary)', fontSize: 11 }}
                  tickFormatter={(d) => `${d}d`}
                />
                <YAxis
                  tick={{ fill: 'var(--text-tertiary)', fontSize: 11 }}
                  tickFormatter={(v) => `${v}%`}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#13141f', borderColor: 'rgba(255,255,255,0.08)',
                    borderRadius: '8px', fontSize: '0.75rem',
                  }}
                  formatter={(value: any, name: any) => {
                    const labels: Record<string, string> = {
                      p5: 'Worst 5%', p25: '25:e percentil', p50: 'Median',
                      p75: '75:e percentil', p95: 'Best 5%',
                    };
                    return [`${value}%`, labels[name] || name];
                  }}
                  labelFormatter={(d) => `Dag ${d}`}
                />
                <Area type="monotone" dataKey="p95" stackId="1" stroke="none" fill="rgba(16,185,129,0.08)" />
                <Area type="monotone" dataKey="p5" stackId="2" stroke="none" fill="rgba(239,68,68,0.08)" />
                <Area type="monotone" dataKey="p75" stroke="none" fill="rgba(16,185,129,0.15)" />
                <Area type="monotone" dataKey="p25" stroke="none" fill="rgba(239,68,68,0.15)" />
                <Area
                  type="monotone" dataKey="p50"
                  stroke="var(--accent-cyan)" strokeWidth={2}
                  fill="rgba(0,242,254,0.05)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div style={{ textAlign: 'center', fontSize: '0.65rem', color: 'var(--text-tertiary)', marginTop: '0.5rem' }}>
            Sannolikhetskon baserad på {mc.simulations?.toLocaleString()} simulerade scenarier
          </div>
        </div>
      )}
    </div>
  );
}

/* ===== Main Page ===== */
export default function PortfolioPage({ portfolio, assets, marketState }: PortfolioPageProps) {
  const { allocations, cash, motivation } = portfolio;
  const activeAllocations = allocations.filter(a => a.weight > 0);
  const totalBuy = allocations.filter(a => a.action === 'buy').reduce((s, a) => s + a.weight, 0);
  const totalSell = allocations.filter(a => a.action === 'sell').reduce((s, a) => s + a.weight, 0);

  const pieData = [
    ...activeAllocations.map(a => ({ name: a.name, value: a.weight, fill: a.color })),
    ...(cash > 0 ? [{ name: 'Cash', value: cash, fill: '#2d3436' }] : []),
  ];

  return (
    <main className="container" style={{ paddingTop: '2rem', paddingBottom: '6rem' }}>

      <div className="flex items-center gap-2" style={{ marginBottom: '2rem' }}>
        <Briefcase size={28} color="var(--accent-purple)" />
        <h2 style={{ margin: 0, fontSize: '1.8rem' }}>AI-Rekommenderad Portfölj</h2>
      </div>

      {/* Summary Cards */}
      <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
        <div className="glass-panel" style={{ padding: '1.5rem', textAlign: 'center' }}>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)', marginBottom: '0.5rem' }}>Marknadssyn</div>
          <div style={{ fontSize: '2rem', fontWeight: 700, color: `var(--score-${getScoreColor(marketState.overallScore)})` }}>
            {getRecommendation(marketState.overallScore)}
          </div>
        </div>
        <div className="glass-panel" style={{ padding: '1.5rem', textAlign: 'center' }}>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)', marginBottom: '0.5rem' }}>Allokerat</div>
          <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--accent-cyan)' }}>{100 - cash}%</div>
        </div>
        <div className="glass-panel" style={{ padding: '1.5rem', textAlign: 'center' }}>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)', marginBottom: '0.5rem' }}>Köp-vikt</div>
          <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--score-positive)' }}>{totalBuy}%</div>
        </div>
        <div className="glass-panel" style={{ padding: '1.5rem', textAlign: 'center' }}>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)', marginBottom: '0.5rem' }}>Sälj-vikt</div>
          <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--score-negative)' }}>{totalSell}%</div>
        </div>
      </div>

      <div className="dashboard-grid">
        {/* Pie Chart */}
        <div className="asset-list-col">
          <div className="glass-panel" style={{ padding: '2rem' }}>
            <h3 style={{ marginBottom: '1.5rem' }}>Tillgångsfördelning</h3>
            <div style={{ height: '300px' }}>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={pieData} cx="50%" cy="50%" innerRadius={70} outerRadius={120} paddingAngle={2} dataKey="value" stroke="none">
                    {pieData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.fill} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value) => `${value}%`}
                    contentStyle={{ backgroundColor: '#13141f', borderColor: 'rgba(255,255,255,0.08)', borderRadius: '8px', color: '#f8f9fa' }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="flex" style={{ flexWrap: 'wrap', gap: '0.75rem', justifyContent: 'center', marginTop: '1rem' }}>
              {pieData.map(entry => (
                <div key={entry.name} className="flex items-center gap-2" style={{ fontSize: '0.8rem' }}>
                  <div style={{ width: 10, height: 10, borderRadius: '50%', background: entry.fill }} />
                  <span style={{ color: 'var(--text-secondary)' }}>{entry.name}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Allocation Details */}
        <div className="detail-col">
          <div className="glass-panel" style={{ padding: '2rem' }}>
            <h3 style={{ marginBottom: '1.5rem' }}>Köp- & Säljråd per Tillgång</h3>
            <div className="flex flex-col gap-4">
              {allocations.map(alloc => {
                const score = alloc.score ?? (assets.find(a => a.id === alloc.assetId)?.finalScore ?? 0);
                const actionIcon = alloc.action === 'buy'
                  ? <TrendingUp size={16} style={{ color: 'var(--score-positive)' }} />
                  : alloc.action === 'sell'
                    ? <TrendingDown size={16} style={{ color: 'var(--score-negative)' }} />
                    : <Minus size={16} style={{ color: 'var(--score-neutral)' }} />;
                const actionLabel = alloc.action === 'buy' ? 'KÖP' : alloc.action === 'sell' ? 'SÄLJ' : 'HÅLL';
                const actionColor = alloc.action === 'buy' ? 'positive' : alloc.action === 'sell' ? 'negative' : 'neutral';

                return (
                  <div key={alloc.assetId} className="glass-panel" style={{ padding: '1rem', background: 'rgba(255,255,255,0.02)' }}>
                    <div className="flex justify-between items-center">
                      <div className="flex items-center gap-4">
                        <div style={{ width: 8, height: 36, borderRadius: 4, background: alloc.color }} />
                        <div>
                          <h4 style={{ margin: 0 }}>{alloc.name}</h4>
                          <span style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>
                            AI Poäng: <span style={{ color: `var(--score-${getScoreColor(score)})` }}>
                              {score > 0 ? '+' : ''}{score.toFixed(1)}
                            </span>
                            {((alloc.action === 'buy' && score < -3) || (alloc.action === 'sell' && score > 3)) && (
                              <span style={{ fontSize: '0.7rem', color: 'var(--accent-cyan)', marginLeft: '0.5rem' }}>
                                ⓘ Inverterad signal
                              </span>
                            )}
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        <div style={{ textAlign: 'right' }}>
                          <div style={{ fontSize: '1.3rem', fontWeight: 700 }}>{alloc.weight}%</div>
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>vikt</span>
                        </div>
                        <span className={`badge ${actionColor}`} style={{ minWidth: '60px', justifyContent: 'center' }}>
                          {actionIcon} {actionLabel}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="glass-panel" style={{
              padding: '1.25rem', marginTop: '1.5rem',
              background: 'rgba(0, 242, 254, 0.05)', border: '1px solid rgba(0, 242, 254, 0.2)',
            }}>
              <h4 style={{ color: 'var(--accent-cyan)', margin: '0 0 0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <ShieldAlert size={16} /> Portfölj-AI Motivering
              </h4>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.7, margin: 0 }}>
                "{motivation}"
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Risk Analysis Panel */}
      <RiskPanel />

      {/* Score History Chart */}
      <ScoreHistory />
    </main>
  );
}

/* ===== Score History Component ===== */
function ScoreHistory() {
  const [history, setHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/portfolio/history?days=7`)
      .then(r => r.json())
      .then(data => {
        setHistory(data?.history || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  if (loading || history.length < 2) return null;

  const chartData = history.map((h: any) => ({
    time: h.timestamp.slice(5, 16).replace('T', ' '),
    score: h.avg_score,
    buy: h.buy_signals,
    sell: h.sell_signals,
  }));

  return (
    <div className="glass-panel" style={{ padding: '1.25rem', marginTop: '1.5rem' }}>
      <h3 style={{ margin: '0 0 1rem', fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <Activity size={18} style={{ color: '#a78bfa' }} />
        AI Score-historik
        <span style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)', fontWeight: 400 }}>
          Snittpoäng per analyskörning · 7 dagar
        </span>
      </h3>
      <ResponsiveContainer width="100%" height={200}>
        <AreaChart data={chartData}>
          <defs>
            <linearGradient id="scoreGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#a78bfa" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#a78bfa" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          <XAxis dataKey="time" tick={{ fill: '#555', fontSize: 10 }} interval="preserveStartEnd" />
          <YAxis tick={{ fill: '#555', fontSize: 10 }} domain={['auto', 'auto']} />
          <Tooltip
            contentStyle={{
              backgroundColor: '#13141f', borderColor: 'rgba(255,255,255,0.08)',
              borderRadius: '8px', fontSize: '0.75rem',
            }}
            formatter={(value: any, name: any) => {
              const labels: Record<string, string> = {
                score: 'Snittpoäng', buy: 'Köpsignaler', sell: 'Säljsignaler',
              };
              return [typeof value === 'number' ? value.toFixed(2) : value, labels[name] || name];
            }}
          />
          <Area type="monotone" dataKey="score" stroke="#a78bfa" strokeWidth={2} fill="url(#scoreGrad)" />
        </AreaChart>
      </ResponsiveContainer>
      <div style={{ display: 'flex', justifyContent: 'center', gap: '2rem', marginTop: '0.5rem', fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>
        <span>📈 Snitt köpsignaler/körning: {(chartData.reduce((s: number, d: any) => s + d.buy, 0) / chartData.length).toFixed(1)}</span>
        <span>📉 Snitt säljsignaler/körning: {(chartData.reduce((s: number, d: any) => s + d.sell, 0) / chartData.length).toFixed(1)}</span>
      </div>
    </div>
  );
}
