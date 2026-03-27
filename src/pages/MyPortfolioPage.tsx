import { useState, useEffect, useCallback } from 'react';
import { Upload, Search, Plus, Trash2, BarChart2, Briefcase, Camera, ArrowRight, PieChart as PieIcon, TrendingUp } from 'lucide-react';
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, PieChart, Pie, AreaChart, Area } from 'recharts';
import { API_BASE } from '../api/client';

interface Holding {
  name: string;
  ticker: string | null;
  value: number;
  weight_pct: number;
  shares?: number;
  currency?: string;
  current_price?: number;
  change_pct?: number;
}

export default function MyPortfolioPage() {
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [searching, setSearching] = useState(false);
  const [comparing, setComparing] = useState(false);
  const [comparison, setComparison] = useState<any>(null);
  const [riskProfiles, setRiskProfiles] = useState<any>(null);
  const [selectedProfile, setSelectedProfile] = useState('balanced');
  const [frontier, setFrontier] = useState<any>(null);
  const [parsing, setParsing] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [portfolioNews, setPortfolioNews] = useState<any[]>([]);
  const [newsLoading, setNewsLoading] = useState(false);
  const [activeSection, setActiveSection] = useState<'ai' | 'my'>('ai');
  const [composite, setComposite] = useState<any>(null);
  const [compositeLoading, setCompositeLoading] = useState(false);
  const [feedback, setFeedback] = useState<any>(null);

  // Auto-load risk profiles on mount
  useEffect(() => {
    fetch(`${API_BASE}/api/risk-profiles`)
      .then(r => r.json())
      .then(data => {
        setRiskProfiles(data);
        if (data.regime?.recommended_profile) {
          setSelectedProfile(data.regime.recommended_profile);
        }
      })
      .catch(() => {});

    // Load composite backtest
    setCompositeLoading(true);
    fetch(`${API_BASE}/api/composite-portfolio`)
      .then(r => r.json())
      .then(data => {
        if (!data.error) setComposite(data);
        setCompositeLoading(false);
      })
      .catch(() => setCompositeLoading(false));

    // Load feedback stats
    fetch(`${API_BASE}/api/feedback-stats`)
      .then(r => r.json())
      .then(data => { if (!data.error) setFeedback(data); })
      .catch(() => {});
  }, []);

  // Fetch portfolio-specific news when holdings have tickers
  useEffect(() => {
    const tickers = holdings.map(h => h.ticker).filter(Boolean);
    if (tickers.length === 0) { setPortfolioNews([]); return; }

    setNewsLoading(true);
    fetch(`${API_BASE}/api/user-portfolio/news?tickers=${tickers.join(',')}`)
      .then(r => r.json())
      .then(data => {
        setPortfolioNews(data.news || []);
        setNewsLoading(false);
      })
      .catch(() => setNewsLoading(false));
  }, [holdings]);

  // Search ticker
  const doSearch = useCallback(async (q: string) => {
    if (q.length < 2) { setSearchResults([]); return; }
    setSearching(true);
    try {
      const res = await fetch(`${API_BASE}/api/user-portfolio/search?q=${encodeURIComponent(q)}`);
      const data = await res.json();
      setSearchResults(data.results || []);
    } catch { setSearchResults([]); }
    setSearching(false);
  }, []);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => doSearch(searchQuery), 500);
    return () => clearTimeout(timer);
  }, [searchQuery, doSearch]);

  // Add holding from search
  const addHolding = (result: any) => {
    setHoldings(prev => [...prev, {
      name: result.name,
      ticker: result.ticker,
      value: 0,
      weight_pct: 0,
      currency: result.currency,
      current_price: result.price,
    }]);
    setSearchQuery('');
    setSearchResults([]);
  };

  // Add manual holding
  const addManual = () => {
    setHoldings(prev => [...prev, {
      name: '', ticker: null, value: 0, weight_pct: 0,
    }]);
  };

  // Update holding
  const updateHolding = (idx: number, field: string, value: any) => {
    setHoldings(prev => prev.map((h, i) => i === idx ? { ...h, [field]: value } : h));
  };

  // Remove holding
  const removeHolding = (idx: number) => {
    setHoldings(prev => prev.filter((_, i) => i !== idx));
  };

  // Parse image
  const parseImage = async (file: File) => {
    setParsing(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await fetch(`${API_BASE}/api/user-portfolio/parse-image`, {
        method: 'POST', body: formData,
      });
      const data = await res.json();
      if (data.holdings?.length > 0) {
        setHoldings(data.holdings);
      }
    } catch (e) {
      console.error('Image parse failed:', e);
    }
    setParsing(false);
  };

  // Handle file input
  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) parseImage(file);
  };

  // Handle drag & drop
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) parseImage(file);
  };

  // Compare
  const doCompare = async () => {
    setComparing(true);
    try {
      // Fetch comparison + frontier
      const res = await fetch(`${API_BASE}/api/user-portfolio/compare`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ holdings }),
      });
      const data = await res.json();
      setComparison(data.comparison);
      setFrontier(data.frontier);
      if (data.user_holdings) setHoldings(data.user_holdings);

      // Fetch risk profiles
      try {
        const rpRes = await fetch(`${API_BASE}/api/risk-profiles`);
        const rpData = await rpRes.json();
        setRiskProfiles(rpData);
        // Auto-select recommended profile
        if (rpData.regime?.recommended_profile) {
          setSelectedProfile(rpData.regime.recommended_profile);
        }
      } catch { /* risk profiles are supplementary */ }
    } catch (e) {
      console.error('Compare failed:', e);
    }
    setComparing(false);
  };

  const totalValue = holdings.reduce((s, h) => s + (h.value || 0), 0);

  return (
    <main className="container" style={{ padding: '2rem 0' }}>
      {/* Header */}
      <div style={{ marginBottom: '1.5rem' }}>
        <h2 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Briefcase size={24} style={{ color: '#a78bfa' }} />
          Portfölj & AI-Riskprofiler
        </h2>
        <p style={{ margin: '0.25rem 0 0', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
          AI:s rekommenderade allokering baserad på marknadsregim + jämför med din portfölj
        </p>
      </div>

      {/* Section Tabs */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem' }}>
        {[{ id: 'ai' as const, label: '📊 AI-Portföljer', desc: 'Riskprofiler & regim' }, { id: 'my' as const, label: '💼 Min Portfölj', desc: 'Jämför med AI' }].map(tab => (
          <button key={tab.id} onClick={() => setActiveSection(tab.id)} style={{
            flex: 1, padding: '0.75rem 1rem', borderRadius: '10px', cursor: 'pointer',
            background: activeSection === tab.id ? 'rgba(167,139,250,0.12)' : 'rgba(255,255,255,0.03)',
            border: `1px solid ${activeSection === tab.id ? 'rgba(167,139,250,0.4)' : 'var(--glass-border)'}`,
            color: activeSection === tab.id ? '#a78bfa' : 'var(--text-secondary)',
            fontSize: '0.9rem', fontWeight: activeSection === tab.id ? 600 : 400,
            transition: 'all 0.2s', textAlign: 'left',
          }}>
            <div>{tab.label}</div>
            <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)', marginTop: '0.15rem' }}>{tab.desc}</div>
          </button>
        ))}
      </div>

      {/* ===== AI PORTFOLIOS SECTION ===== */}
      {activeSection === 'ai' && (
        <div>
          {/* Regime Banner */}
          {riskProfiles?.regime && (
            <div className="glass-panel" style={{
              padding: '0.75rem 1rem', marginBottom: '1rem',
              background: `${riskProfiles.regime.regime_color}12`,
              border: `1px solid ${riskProfiles.regime.regime_color}35`,
              display: 'flex', alignItems: 'center', gap: '0.75rem',
            }}>
              <div style={{
                width: 40, height: 40, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: `${riskProfiles.regime.regime_color}25`, fontSize: '1.2rem', flexShrink: 0,
              }}>
                {riskProfiles.regime.regime === 'risk_off' ? '⚠️' : riskProfiles.regime.regime === 'risk_on' ? '🚀' : riskProfiles.regime.regime === 'cautious' ? '📊' : '📈'}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: '0.7rem', color: riskProfiles.regime.regime_color, fontWeight: 700, marginBottom: '0.15rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Marknadsregim: {riskProfiles.regime.regime_label} (AI-poäng: {riskProfiles.regime.overall_score > 0 ? '+' : ''}{riskProfiles.regime.overall_score})
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                  {riskProfiles.regime.advice}
                </div>
              </div>
              {riskProfiles.regime.switch_urgency === 'high' && (
                <div style={{
                  padding: '0.25rem 0.5rem', borderRadius: '4px', fontSize: '0.65rem', fontWeight: 700,
                  background: '#ef444430', color: '#ef4444', animation: 'pulse 2s infinite',
                }}>BYT NU</div>
              )}
            </div>
          )}

          {/* 3 Profile Tabs */}
          {riskProfiles?.profiles && (
            <div className="glass-panel" style={{ padding: '1.25rem', marginBottom: '1rem' }}>
              <h3 style={{ margin: '0 0 1rem', fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <PieIcon size={18} style={{ color: 'var(--accent-cyan)' }} />
                AI:s 4 Riskprofiler
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: '0.5rem', marginBottom: '1rem' }}>
                {(['conservative', 'balanced', 'aggressive', 'turbo'] as const).map(pid => {
                  const p = riskProfiles.profiles[pid];
                  if (!p) return null;
                  const isRec = riskProfiles.regime?.recommended_profile === pid;
                  const isSelected = selectedProfile === pid;
                  const borderColor = pid === 'conservative' ? '#3b82f6' : pid === 'balanced' ? '#f59e0b' : pid === 'turbo' ? '#ff6b6b' : '#ef4444';
                  return (
                    <div key={pid}
                      onClick={() => setSelectedProfile(pid)}
                      style={{
                        padding: '0.75rem', borderRadius: '8px', cursor: 'pointer',
                        background: isSelected ? `${borderColor}15` : 'rgba(255,255,255,0.03)',
                        border: `2px solid ${isSelected ? borderColor : isRec ? `${borderColor}60` : 'var(--glass-border)'}`,
                        transition: 'all 0.2s', position: 'relative',
                      }}
                    >
                      {isRec && (
                        <div style={{
                          position: 'absolute', top: -8, right: 8, fontSize: '0.55rem', fontWeight: 700,
                          background: borderColor, color: '#fff', padding: '0.1rem 0.4rem', borderRadius: '3px',
                          textTransform: 'uppercase', letterSpacing: '0.05em',
                        }}>Rekommenderad</div>
                      )}
                      <div style={{ fontSize: '1.1rem', marginBottom: '0.2rem' }}>{p.emoji} {p.name}</div>
                      <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)', lineHeight: 1.3 }}>{p.description}</div>
                      <div style={{ marginTop: '0.4rem', display: 'flex', flexWrap: 'wrap', gap: '0.3rem', fontSize: '0.6rem' }}>
                        {p.expected_return != null && (
                          <span style={{ padding: '0.1rem 0.3rem', borderRadius: '3px', background: 'rgba(16,185,129,0.15)', color: '#10b981' }}>
                            Avk: {p.expected_return}%
                          </span>
                        )}
                        {p.volatility != null && (
                          <span style={{ padding: '0.1rem 0.3rem', borderRadius: '3px', background: 'rgba(245,158,11,0.15)', color: '#f59e0b' }}>
                            Vol: {p.volatility}%
                          </span>
                        )}
                        {p.sharpe_ratio != null && (
                          <span style={{ padding: '0.1rem 0.3rem', borderRadius: '3px', background: 'rgba(0,242,254,0.15)', color: '#00f2fe' }}>
                            Sharpe: {p.sharpe_ratio}
                          </span>
                        )}
                        <span style={{ padding: '0.1rem 0.3rem', borderRadius: '3px', background: 'rgba(255,255,255,0.05)', color: 'var(--text-tertiary)' }}>
                          Cash: {p.cash}%
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Selected profile donut + allocations */}
              {riskProfiles.profiles[selectedProfile] && (() => {
                const prof = riskProfiles.profiles[selectedProfile];
                const pieData = [
                  ...prof.allocations.filter((a: any) => a.weight > 0).map((a: any) => ({ name: a.name, value: a.weight, fill: a.color })),
                  ...(prof.cash > 0 ? [{ name: 'Cash', value: prof.cash, fill: '#2d3436' }] : []),
                ];
                return (
                  <div style={{ display: 'grid', gridTemplateColumns: '200px 1fr', gap: '1.5rem', alignItems: 'center' }}>
                    <div style={{ height: '180px' }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie data={pieData} cx="50%" cy="50%" innerRadius={45} outerRadius={75} paddingAngle={2} dataKey="value" stroke="none">
                            {pieData.map((entry: any, index: number) => (
                              <Cell key={`cell-${index}`} fill={entry.fill} />
                            ))}
                          </Pie>
                          <Tooltip formatter={(value: any) => `${value}%`} contentStyle={{ backgroundColor: '#13141f', borderColor: 'rgba(255,255,255,0.08)', borderRadius: '8px', color: '#f8f9fa' }} />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                    <div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginBottom: '0.75rem' }}>
                        {prof.allocations.filter((a: any) => a.weight > 0).map((a: any, i: number) => (
                          <div key={i} style={{
                            padding: '0.3rem 0.6rem', borderRadius: '4px',
                            background: a.color || 'rgba(255,255,255,0.05)',
                            fontSize: '0.7rem', fontWeight: 600, color: '#fff',
                          }}>
                            {a.name} {a.weight}%
                          </div>
                        ))}
                        {prof.cash > 0 && (
                          <div style={{
                            padding: '0.3rem 0.6rem', borderRadius: '4px',
                            background: '#2d3436', fontSize: '0.7rem', fontWeight: 600, color: '#aaa',
                          }}>Cash {prof.cash}%</div>
                        )}
                      </div>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', lineHeight: 1.5 }}>
                        {prof.allocations.filter((a: any) => a.action === 'buy' && a.weight > 0).length} köppositioner ·{' '}
                        {prof.allocations.filter((a: any) => a.action === 'sell').length} säljpositioner ·{' '}
                        Totalt allokerat: {prof.total_weight}%
                      </div>
                    </div>
                  </div>
                );
              })()}
            </div>
          )}

          {!riskProfiles && (
            <div className="glass-panel" style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-tertiary)' }}>
              Laddar AI-riskprofiler...
            </div>
          )}

          {/* ===== AI COMPOSITE PORTFOLIO ===== */}
          {composite && composite.stats && (
            <div className="glass-panel" style={{ padding: '1.25rem', marginTop: '1rem' }}>
              <h3 style={{ margin: '0 0 0.75rem', fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <TrendingUp size={18} style={{ color: '#10b981' }} />
                AI Composite Portfolio
                <span style={{ fontSize: '0.6rem', color: 'var(--text-tertiary)', fontWeight: 400 }}>
                  Regim-switching backtest · {composite.stats.period_start} → {composite.stats.period_end}
                </span>
              </h3>

              {/* Stats Cards */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.5rem', marginBottom: '1rem' }}>
                <div style={{ padding: '0.6rem', borderRadius: '8px', background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)', textAlign: 'center' }}>
                  <div style={{ fontSize: '0.55rem', color: '#10b981', textTransform: 'uppercase', marginBottom: '0.2rem' }}>AI Avkastning</div>
                  <div style={{ fontSize: '1.3rem', fontWeight: 700, color: composite.stats.total_return >= 0 ? '#10b981' : '#ef4444' }}>
                    {composite.stats.total_return > 0 ? '+' : ''}{composite.stats.total_return}%
                  </div>
                </div>
                <div style={{ padding: '0.6rem', borderRadius: '8px', background: 'rgba(0,242,254,0.06)', border: '1px solid rgba(0,242,254,0.15)', textAlign: 'center' }}>
                  <div style={{ fontSize: '0.55rem', color: 'var(--accent-cyan)', textTransform: 'uppercase', marginBottom: '0.2rem' }}>Alpha vs S&P</div>
                  <div style={{ fontSize: '1.3rem', fontWeight: 700, color: composite.stats.alpha >= 0 ? '#10b981' : '#ef4444' }}>
                    {composite.stats.alpha > 0 ? '+' : ''}{composite.stats.alpha}%
                  </div>
                </div>
                <div style={{ padding: '0.6rem', borderRadius: '8px', background: 'rgba(167,139,250,0.08)', border: '1px solid rgba(167,139,250,0.2)', textAlign: 'center' }}>
                  <div style={{ fontSize: '0.55rem', color: '#a78bfa', textTransform: 'uppercase', marginBottom: '0.2rem' }}>Sharpe Ratio</div>
                  <div style={{ fontSize: '1.3rem', fontWeight: 700, color: '#a78bfa' }}>{composite.stats.sharpe_ratio}</div>
                </div>
                <div style={{ padding: '0.6rem', borderRadius: '8px', background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.15)', textAlign: 'center' }}>
                  <div style={{ fontSize: '0.55rem', color: '#ef4444', textTransform: 'uppercase', marginBottom: '0.2rem' }}>Max Drawdown</div>
                  <div style={{ fontSize: '1.3rem', fontWeight: 700, color: '#ef4444' }}>-{composite.stats.max_drawdown}%</div>
                </div>
              </div>

              {/* Equity Curve Chart */}
              {composite.equity_curve?.length > 0 && (() => {
                const chartData = composite.equity_curve
                  .filter((_: any, i: number) => i % 3 === 0 || i === composite.equity_curve.length - 1)
                  .map((e: any, i: number) => ({
                    date: e.date.slice(5),
                    ai: e.value,
                    sp500: composite.benchmark_curve[Math.min(i * 3, composite.benchmark_curve.length - 1)]?.value || 100,
                    regime: e.regime,
                  }));
                return (
                  <div style={{ height: '220px', marginBottom: '0.75rem' }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={chartData}>
                        <defs>
                          <linearGradient id="aiGrad" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor="#10b981" stopOpacity={0.3} />
                            <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                          </linearGradient>
                          <linearGradient id="spGrad" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor="#6366f1" stopOpacity={0.15} />
                            <stop offset="100%" stopColor="#6366f1" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                        <XAxis dataKey="date" tick={{ fill: '#555', fontSize: 9 }} interval="preserveStartEnd" />
                        <YAxis tick={{ fill: '#555', fontSize: 9 }} domain={['auto', 'auto']} />
                        <Tooltip
                          contentStyle={{ backgroundColor: '#13141f', borderColor: 'rgba(255,255,255,0.08)', borderRadius: '8px', fontSize: '0.75rem' }}
                          formatter={(value: any, name: any) => [
                            typeof value === 'number' ? value.toFixed(1) : value,
                            name === 'ai' ? 'AI Portfölj' : 'S&P 500'
                          ]}
                        />
                        <Area type="monotone" dataKey="ai" stroke="#10b981" strokeWidth={2} fill="url(#aiGrad)" />
                        <Area type="monotone" dataKey="sp500" stroke="#6366f1" strokeWidth={1.5} fill="url(#spGrad)" strokeDasharray="5 3" />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                );
              })()}

              {/* Legend + regime info */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.65rem', color: 'var(--text-tertiary)' }}>
                <div style={{ display: 'flex', gap: '1rem' }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                    <div style={{ width: 12, height: 3, background: '#10b981', borderRadius: 2 }} /> AI Composite
                  </span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                    <div style={{ width: 12, height: 3, background: '#6366f1', borderRadius: 2, borderTop: '1px dashed #6366f1' }} /> S&P 500
                  </span>
                </div>
                <span>{composite.stats.regime_switches} regimskiften · {composite.stats.regime_distribution?.aggressive || 0}% aggressiv, {composite.stats.regime_distribution?.balanced || 0}% balanserad, {composite.stats.regime_distribution?.conservative || 0}% försiktig</span>
              </div>

              {/* Regime Log */}
              {composite.regime_log?.length > 0 && (
                <div style={{ marginTop: '0.75rem', padding: '0.75rem', borderRadius: '8px', background: 'rgba(255,255,255,0.02)' }}>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginBottom: '0.4rem', fontWeight: 600 }}>Regimskiften:</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem' }}>
                    {composite.regime_log.map((l: any, i: number) => {
                      const color = l.to_profile === 'aggressive' ? '#ef4444' : l.to_profile === 'conservative' ? '#3b82f6' : '#f59e0b';
                      return (
                        <div key={i} style={{
                          padding: '0.2rem 0.4rem', borderRadius: '4px', fontSize: '0.55rem',
                          background: `${color}15`, border: `1px solid ${color}30`, color,
                        }}>
                          {l.date.slice(5)} → {l.label}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          )}

          {compositeLoading && (
            <div className="glass-panel" style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--text-tertiary)', marginTop: '1rem', fontSize: '0.8rem' }}>
              📊 Beräknar AI Composite Portfolio backtest...
            </div>
          )}

          {/* ===== AI LEARNING SECTION ===== */}
          {feedback && feedback.insights && (
            <div className="glass-panel" style={{ padding: '1.25rem', marginTop: '1rem' }}>
              <h3 style={{ margin: '0 0 0.75rem', fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                🧠 AI Learning
                <span style={{ fontSize: '0.6rem', color: 'var(--text-tertiary)', fontWeight: 400 }}>
                  Feedback Loop · {feedback.total_switches} regimskiften analyserade
                </span>
              </h3>

              {/* Hit Rate + Per-regime stats */}
              <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: '1rem', marginBottom: '1rem' }}>
                {/* Overall hit rate gauge */}
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '0.5rem', borderRadius: '8px', background: 'rgba(255,255,255,0.02)' }}>
                  <div style={{ fontSize: '2rem', fontWeight: 800, color: feedback.overall_hit_rate >= 60 ? '#10b981' : feedback.overall_hit_rate >= 40 ? '#f59e0b' : '#ef4444' }}>
                    {feedback.overall_hit_rate}%
                  </div>
                  <div style={{ fontSize: '0.55rem', color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>Hit Rate</div>
                </div>

                {/* Per-regime bars */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', justifyContent: 'center' }}>
                  {Object.entries(feedback.hit_rates || {}).map(([regime, hr]: [string, any]) => {
                    const color = regime === 'aggressive' ? '#ef4444' : regime === 'conservative' ? '#3b82f6' : '#f59e0b';
                    const label = regime === 'aggressive' ? '🚀 Aggressiv' : regime === 'conservative' ? '🛡️ Försiktig' : '⚖️ Balanserad';
                    return (
                      <div key={regime} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.65rem' }}>
                        <span style={{ width: 90, color: 'var(--text-secondary)' }}>{label}</span>
                        <div style={{ flex: 1, height: 8, background: 'rgba(255,255,255,0.05)', borderRadius: 4, overflow: 'hidden' }}>
                          <div style={{ width: `${hr.hit_rate}%`, height: '100%', background: color, borderRadius: 4, transition: 'width 0.5s ease' }} />
                        </div>
                        <span style={{ width: 55, textAlign: 'right', color }}>{hr.hit_rate}% ({hr.correct}/{hr.total_switches})</span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Learning Insights */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', marginBottom: '0.75rem' }}>
                {feedback.insights.map((ins: any, i: number) => {
                  const bgMap: any = { good: 'rgba(16,185,129,0.06)', warning: 'rgba(245,158,11,0.06)', bad: 'rgba(239,68,68,0.06)', info: 'rgba(99,102,241,0.06)' };
                  const borderMap: any = { good: 'rgba(16,185,129,0.15)', warning: 'rgba(245,158,11,0.15)', bad: 'rgba(239,68,68,0.15)', info: 'rgba(99,102,241,0.15)' };
                  return (
                    <div key={i} style={{
                      padding: '0.4rem 0.6rem', borderRadius: '6px', fontSize: '0.65rem',
                      background: bgMap[ins.severity] || bgMap.info,
                      border: `1px solid ${borderMap[ins.severity] || borderMap.info}`,
                      color: 'var(--text-secondary)',
                    }}>
                      {ins.icon} {ins.text}
                    </div>
                  );
                })}
              </div>

              {/* Drawdown Episodes */}
              {feedback.drawdown_episodes?.length > 0 && (
                <div style={{ padding: '0.6rem', borderRadius: '8px', background: 'rgba(239,68,68,0.04)', border: '1px solid rgba(239,68,68,0.1)' }}>
                  <div style={{ fontSize: '0.65rem', fontWeight: 600, color: '#ef4444', marginBottom: '0.3rem' }}>📉 Identifierade Nedgångar</div>
                  {feedback.drawdown_episodes.map((ep: any, i: number) => (
                    <div key={i} style={{ fontSize: '0.6rem', color: 'var(--text-secondary)', marginBottom: '0.25rem', paddingLeft: '0.5rem', borderLeft: `2px solid ${ep.was_protective ? '#10b981' : '#ef4444'}` }}>
                      <strong>{ep.start_date} → {ep.end_date}</strong>: -{ep.drawdown_pct}% ({ep.recovery_days}d)
                      <div style={{ color: 'var(--text-tertiary)', fontSize: '0.55rem' }}>{ep.lesson}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ===== MY PORTFOLIO SECTION ===== */}
      {activeSection === 'my' && (
        <div>

      {/* Image Upload Zone */}
      <div
        className="glass-panel"
        onDrop={handleDrop}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        style={{
          padding: '2rem', marginBottom: '1.5rem', textAlign: 'center',
          border: `2px dashed ${dragOver ? '#a78bfa' : 'rgba(255,255,255,0.1)'}`,
          background: dragOver ? 'rgba(167, 139, 250, 0.08)' : 'rgba(255,255,255,0.02)',
          cursor: 'pointer', transition: 'all 0.2s',
        }}
        onClick={() => document.getElementById('portfolio-image-input')?.click()}
      >
        <input id="portfolio-image-input" type="file" accept="image/*" onChange={handleFile} style={{ display: 'none' }} />
        {parsing ? (
          <div style={{ color: '#a78bfa' }}>
            <Camera size={32} style={{ margin: '0 auto 0.5rem', display: 'block' }} className="spin" />
            <p style={{ margin: 0, fontSize: '0.9rem' }}>AI analyserar din portföljbild...</p>
          </div>
        ) : (
          <>
            <Upload size={32} style={{ color: 'var(--text-tertiary)', margin: '0 auto 0.5rem', display: 'block' }} />
            <p style={{ margin: 0, fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
              📸 Dra & släpp en skärmdump från Avanza/Nordnet här
            </p>
            <p style={{ margin: '0.25rem 0 0', fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>
              AI:n läser automatiskt av dina innehav från bilden
            </p>
          </>
        )}
      </div>

      {/* Search & Add */}
      <div className="glass-panel" style={{ padding: '1rem', marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: searchResults.length > 0 ? '0.75rem' : 0 }}>
          <div style={{ flex: 1, position: 'relative' }}>
            <Search size={14} style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-tertiary)' }} />
            <input
              type="text" value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Sök aktie eller fond (t.ex. AAPL, SEB, Avanza Zero)..."
              style={{
                width: '100%', padding: '0.6rem 0.75rem 0.6rem 2rem',
                background: 'rgba(255,255,255,0.05)', border: '1px solid var(--glass-border)',
                borderRadius: '8px', color: 'var(--text-primary)', fontSize: '0.85rem',
                outline: 'none',
              }}
            />
          </div>
          <button onClick={addManual} style={{
            padding: '0.6rem 1rem', background: 'rgba(167,139,250,0.1)',
            border: '1px solid rgba(167,139,250,0.3)', borderRadius: '8px',
            color: '#a78bfa', cursor: 'pointer', fontSize: '0.8rem',
            display: 'flex', alignItems: 'center', gap: '0.3rem',
          }}>
            <Plus size={14} /> Manuell
          </button>
        </div>

        {/* Search results */}
        {searchResults.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
            {searchResults.map((r, i) => (
              <div key={i} onClick={() => addHolding(r)} style={{
                padding: '0.5rem 0.75rem', borderRadius: '6px',
                background: 'rgba(255,255,255,0.03)', cursor: 'pointer',
                border: '1px solid rgba(255,255,255,0.05)',
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                fontSize: '0.8rem',
              }}>
                <div>
                  <span style={{ fontWeight: 600 }}>{r.ticker}</span>
                  <span style={{ color: 'var(--text-secondary)', marginLeft: '0.5rem' }}>{r.name}</span>
                </div>
                <span style={{ color: '#a78bfa' }}>{r.price} {r.currency}</span>
              </div>
            ))}
          </div>
        )}
        {searching && <p style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', margin: '0.5rem 0 0' }}>Söker...</p>}
      </div>

      {/* Holdings Table */}
      {holdings.length > 0 && (
        <div className="glass-panel" style={{ padding: '1.25rem', marginBottom: '1.5rem' }}>
          <h3 style={{ margin: '0 0 1rem', fontSize: '1rem' }}>
            Dina innehav ({holdings.length} st)
            {totalValue > 0 && (
              <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', fontWeight: 400, marginLeft: '0.5rem' }}>
                Totalt: {totalValue.toLocaleString()} kr
              </span>
            )}
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {holdings.map((h, idx) => (
              <div key={idx} style={{
                display: 'flex', gap: '0.5rem', alignItems: 'center',
                padding: '0.5rem', borderRadius: '6px',
                background: 'rgba(255,255,255,0.02)', border: '1px solid var(--glass-border)',
              }}>
                <input
                  type="text" value={h.name} placeholder="Namn"
                  onChange={(e) => updateHolding(idx, 'name', e.target.value)}
                  style={{
                    flex: 2, padding: '0.4rem 0.5rem', background: 'transparent',
                    border: '1px solid rgba(255,255,255,0.08)', borderRadius: '4px',
                    color: 'var(--text-primary)', fontSize: '0.8rem',
                  }}
                />
                <input
                  type="text" value={h.ticker || ''} placeholder="Ticker"
                  onChange={(e) => updateHolding(idx, 'ticker', e.target.value)}
                  style={{
                    width: '80px', padding: '0.4rem 0.5rem', background: 'transparent',
                    border: '1px solid rgba(255,255,255,0.08)', borderRadius: '4px',
                    color: '#a78bfa', fontSize: '0.8rem', fontFamily: 'monospace',
                  }}
                />
                <input
                  type="number" value={h.value || ''} placeholder="Värde (kr)"
                  onChange={(e) => updateHolding(idx, 'value', parseFloat(e.target.value) || 0)}
                  style={{
                    width: '100px', padding: '0.4rem 0.5rem', background: 'transparent',
                    border: '1px solid rgba(255,255,255,0.08)', borderRadius: '4px',
                    color: 'var(--text-primary)', fontSize: '0.8rem',
                  }}
                />
                <input
                  type="number" value={h.weight_pct || ''} placeholder="%"
                  onChange={(e) => updateHolding(idx, 'weight_pct', parseFloat(e.target.value) || 0)}
                  style={{
                    width: '55px', padding: '0.4rem 0.5rem', background: 'transparent',
                    border: '1px solid rgba(255,255,255,0.08)', borderRadius: '4px',
                    color: 'var(--text-primary)', fontSize: '0.8rem',
                  }}
                />
                {h.change_pct !== undefined && h.change_pct !== null && (
                  <span style={{
                    fontSize: '0.7rem', fontWeight: 600, width: '50px', textAlign: 'right',
                    color: h.change_pct >= 0 ? '#10b981' : '#ef4444',
                  }}>
                    {h.change_pct >= 0 ? '+' : ''}{h.change_pct}%
                  </span>
                )}
                <button onClick={() => removeHolding(idx)} style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: 'var(--text-tertiary)', padding: '0.25rem',
                }}>
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>

          {/* Compare Button */}
          <button onClick={doCompare} disabled={comparing || holdings.length === 0} style={{
            marginTop: '1rem', padding: '0.75rem 1.5rem', width: '100%',
            background: 'linear-gradient(135deg, rgba(167,139,250,0.2), rgba(0,242,254,0.1))',
            border: '1px solid rgba(167,139,250,0.3)', borderRadius: '10px',
            color: '#a78bfa', cursor: 'pointer', fontSize: '0.9rem', fontWeight: 600,
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem',
            opacity: comparing ? 0.6 : 1,
          }}>
            {comparing ? (
              <>Analyserar...</>
            ) : (
              <><BarChart2 size={16} /> Jämför med AI-portföljen <ArrowRight size={14} /></>
            )}
          </button>
        </div>
      )}

      {/* Comparison Results */}
      {comparison && (
        <div className="glass-panel" style={{ padding: '1.25rem' }}>
          <h3 style={{ margin: '0 0 1rem', fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <BarChart2 size={18} style={{ color: 'var(--accent-cyan)' }} />
            Jämförelse: Din Portfölj vs AI
          </h3>

          {/* Side by side stats */}
          <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
            <div style={{
              padding: '1rem', borderRadius: '8px',
              background: 'rgba(167,139,250,0.05)', border: '1px solid rgba(167,139,250,0.15)',
            }}>
              <div style={{ fontSize: '0.7rem', color: '#a78bfa', marginBottom: '0.5rem' }}>DIN PORTFÖLJ</div>
              <div style={{ fontSize: '1.2rem', fontWeight: 700 }}>{comparison.user_holdings_count} innehav</div>
              {comparison.user_volatility_annual > 0 && (
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                  Volatilitet: {comparison.user_volatility_annual}%/år
                </div>
              )}
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                Diversifiering: {comparison.diversification_score}/100
              </div>
            </div>
            <div style={{
              padding: '1rem', borderRadius: '8px',
              background: 'rgba(0,242,254,0.05)', border: '1px solid rgba(0,242,254,0.15)',
            }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--accent-cyan)', marginBottom: '0.5rem' }}>AI-PORTFÖLJ</div>
              <div style={{ fontSize: '1.2rem', fontWeight: 700 }}>{comparison.ai_holdings_count} innehav</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                Överlapp: {comparison.overlap_count} tillgångar
              </div>
            </div>
          </div>

          {/* Recommendations */}
          {comparison.recommendations?.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              {comparison.recommendations.map((rec: string, i: number) => (
                <div key={i} style={{
                  padding: '0.5rem 0.75rem', borderRadius: '6px',
                  background: 'rgba(255,255,255,0.03)', border: '1px solid var(--glass-border)',
                  fontSize: '0.8rem', color: 'var(--text-secondary)',
                }}>
                  {rec}
                </div>
              ))}
            </div>
          )}

          {/* Efficient Frontier Chart */}
          {frontier && frontier.frontier?.length > 0 && (
            <div style={{ marginTop: '1.5rem' }}>
              <h4 style={{ margin: '0 0 0.75rem', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                📈 Effektiv Front (Risk vs Avkastning)
              </h4>
              <div style={{
                background: 'rgba(0,0,0,0.2)', borderRadius: '10px', padding: '1rem 0.5rem 0.5rem',
                border: '1px solid rgba(255,255,255,0.05)',
              }}>
                <ResponsiveContainer width="100%" height={350}>
                  <ScatterChart margin={{ top: 10, right: 30, bottom: 20, left: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                    <XAxis
                      type="number" dataKey="risk" name="Risk"
                      label={{ value: 'Risk (volatilitet %/år)', position: 'bottom', offset: 0, fill: 'var(--text-tertiary)', fontSize: 11 }}
                      tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }}
                      stroke="rgba(255,255,255,0.1)"
                    />
                    <YAxis
                      type="number" dataKey="return" name="Avkastning"
                      label={{ value: 'Avkastning (%/år)', angle: -90, position: 'insideLeft', fill: 'var(--text-tertiary)', fontSize: 11 }}
                      tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }}
                      stroke="rgba(255,255,255,0.1)"
                    />
                    <Tooltip
                      content={({ active, payload }: any) => {
                        if (!active || !payload?.length) return null;
                        const d = payload[0]?.payload;
                        return (
                          <div style={{ background: 'rgba(15,15,25,0.95)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', padding: '0.5rem 0.75rem', fontSize: '0.75rem' }}>
                            {d?.label && <div style={{ fontWeight: 600, marginBottom: '0.3rem', color: 'var(--text-primary)' }}>{d.label}</div>}
                            <div style={{ color: '#ef4444' }}>Risk: {Number(d?.risk).toFixed(1)}%</div>
                            <div style={{ color: '#10b981' }}>Avkastning: {Number(d?.return).toFixed(1)}%</div>
                          </div>
                        );
                      }}
                    />
                    {/* All simulated portfolios */}
                    <Scatter name="Möjliga portföljer" data={frontier.frontier} fill="rgba(255,255,255,0.12)">
                      {frontier.frontier.map((_: any, i: number) => (
                        <Cell key={i} fill="rgba(255,255,255,0.12)" r={2} />
                      ))}
                    </Scatter>
                    {/* Efficient frontier curve */}
                    {frontier.efficient?.length > 0 && (
                      <Scatter name="Effektiv front" data={frontier.efficient} fill="#00f2fe" line={{ stroke: '#00f2fe', strokeWidth: 2 }} lineType="fitting">
                        {frontier.efficient.map((_: any, i: number) => (
                          <Cell key={i} fill="#00f2fe" r={3} />
                        ))}
                      </Scatter>
                    )}
                    {/* User portfolio */}
                    {frontier.user_position && (
                      <Scatter name="Din Portfölj" data={[frontier.user_position]} fill="#a78bfa">
                        <Cell fill="#a78bfa" r={8} />
                      </Scatter>
                    )}
                    {/* AI portfolio */}
                    {frontier.ai_position && (
                      <Scatter name="AI-Portfölj" data={[frontier.ai_position]} fill="#10b981">
                        <Cell fill="#10b981" r={8} />
                      </Scatter>
                    )}
                  </ScatterChart>
                </ResponsiveContainer>
                {/* Legend */}
                <div style={{ display: 'flex', justifyContent: 'center', gap: '1.5rem', marginTop: '0.5rem', flexWrap: 'wrap' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.7rem' }}>
                    <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#a78bfa' }} /> Din Portfölj
                    {frontier.user_position && <span style={{ color: 'var(--text-tertiary)' }}>({frontier.user_position.risk}% risk, {frontier.user_position.return}% avkastning)</span>}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.7rem' }}>
                    <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#10b981' }} /> AI-Portfölj
                    {frontier.ai_position && <span style={{ color: 'var(--text-tertiary)' }}>({frontier.ai_position.risk}% risk, {frontier.ai_position.return}% avkastning)</span>}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.7rem' }}>
                    <div style={{ width: 10, height: 3, background: '#00f2fe', borderRadius: 2 }} /> Effektiv front
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Portfolio News Feed */}
      {portfolioNews.length > 0 && (
        <div className="glass-panel animate-fade-in" style={{ padding: '1.5rem', marginTop: '1.5rem' }}>
          <h3 style={{ margin: '0 0 1rem', fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            📰 Nyheter för dina innehav
            <span style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', fontWeight: 400 }}>
              {portfolioNews.length} artiklar • Marketaux
            </span>
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {portfolioNews.slice(0, 10).map((news: any, i: number) => (
              <a
                key={news.id || i}
                href={news.url}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  display: 'block', padding: '0.75rem', borderRadius: '8px',
                  background: 'rgba(255,255,255,0.02)',
                  border: '1px solid rgba(255,255,255,0.04)',
                  textDecoration: 'none', color: 'inherit',
                  transition: 'all 0.2s ease',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.05)')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.02)')}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '0.5rem' }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.3rem', lineHeight: '1.3' }}>
                      {news.title}
                    </div>
                    {news.summary && news.summary !== news.title && (
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', lineHeight: '1.4' }}>
                        {news.summary.slice(0, 150)}{news.summary.length > 150 ? '...' : ''}
                      </div>
                    )}
                    <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.3rem', flexWrap: 'wrap' }}>
                      <span style={{ fontSize: '0.6rem', color: 'var(--text-tertiary)' }}>{news.source}</span>
                      <span style={{ fontSize: '0.6rem', color: 'var(--text-tertiary)' }}>{news.time}</span>
                      {news.tickers?.slice(0, 3).map((t: string) => (
                        <span key={t} style={{
                          fontSize: '0.55rem', padding: '0.1rem 0.3rem', borderRadius: '3px',
                          background: 'rgba(139, 92, 246, 0.15)', color: '#a78bfa',
                          fontFamily: 'monospace',
                        }}>{t}</span>
                      ))}
                    </div>
                  </div>
                  <div style={{
                    padding: '0.15rem 0.4rem', borderRadius: '4px', fontSize: '0.6rem', fontWeight: 700,
                    background: news.sentiment === 'positive' ? 'rgba(16,185,129,0.15)' :
                               news.sentiment === 'negative' ? 'rgba(239,68,68,0.15)' : 'rgba(255,255,255,0.05)',
                    color: news.sentiment === 'positive' ? '#10b981' :
                           news.sentiment === 'negative' ? '#ef4444' : 'var(--text-tertiary)',
                    whiteSpace: 'nowrap',
                  }}>
                    {news.sentiment === 'positive' ? '↑ Positiv' : news.sentiment === 'negative' ? '↓ Negativ' : '— Neutral'}
                  </div>
                </div>
              </a>
            ))}
          </div>
        </div>
      )}

      {newsLoading && holdings.length > 0 && (
        <div style={{ textAlign: 'center', padding: '1rem', fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>
          📰 Laddar nyheter för dina innehav...
        </div>
      )}

      </div>
      )}

    </main>
  );
}
