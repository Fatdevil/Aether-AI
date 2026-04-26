import { useState, useEffect } from 'react';
import { Trophy, Target, RefreshCw, TrendingUp, TrendingDown, Shield } from 'lucide-react';
import { api } from '../api/client';

interface DualData {
  comparison: {
    alpha: {
      name: string;
      cum_return: number;
      sharpe: number;
      max_drawdown: number;
      days_tracked: number;
      best_day: number;
      worst_day: number;
      weights: Record<string, number>;
    };
    omega: {
      name: string;
      cum_return: number;
      sharpe: number;
      max_drawdown: number;
      days_tracked: number;
      best_day: number;
      worst_day: number;
      weights: Record<string, number>;
    };
    winner: string;
    margin: number;
    days_compared: number;
    start_date: string;
  };
  omega_details: {
    scenarios: Array<{
      name: string;
      probability: number;
      description: string;
      asset_returns: Record<string, number>;
    }>;
    omega_portfolio: {
      expected_return: number;
      worst_case_return: number;
      cvar_5pct: number;
      sharpe_estimate: number;
      generated_at: string;
      n_scenarios: number;
    } | null;
    last_generation: string | null;
  };
}

const ASSET_LABELS: Record<string, string> = {
  sp500: 'S&P 500', gold: 'Guld', us10y: 'US 10Y', oil: 'Olja', btc: 'Bitcoin',
  'global-equity': 'Global', eurusd: 'EUR/USD', silver: 'Silver',
  'sector-tech': 'Tech', 'sector-energy': 'Energi', 'sector-finance': 'Finans',
  'sector-health': 'Hälsa', 'region-em': 'EM', 'region-europe': 'Europa',
};

export default function DualPortfolioPanel() {
  const [data, setData] = useState<DualData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [showScenarios, setShowScenarios] = useState(false);

  useEffect(() => {
    api.getDualPortfolio()
      .then(setData)
      .catch((err) => console.warn('[DualPortfolio] fetch failed:', err))
      .finally(() => setLoading(false));
  }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await api.refreshScenarios();
      const fresh = await api.getDualPortfolio();
      setData(fresh);
    } catch (err) {
      console.warn('[DualPortfolio] refresh failed:', err);
    }
    setRefreshing(false);
  };

  if (loading) {
    return (
      <div className="glass-panel" style={{ padding: '1.25rem', opacity: 0.6 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Target size={16} />
          <span style={{ fontSize: '0.85rem' }}>Laddar Alpha vs Omega...</span>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const { comparison, omega_details } = data;
  const { alpha, omega, winner, days_compared } = comparison;
  const omega_port = omega_details?.omega_portfolio;
  const scenarios = omega_details?.scenarios || [];

  const noData = days_compared < 1 && !omega_port;

  // Winner styling
  const alphaWins = winner === 'alpha';
  const omegaWins = winner === 'omega';
  const tooEarly = winner === 'too_early' || days_compared < 5;

  const fmtPct = (v: number) => `${v >= 0 ? '+' : ''}${(v * 100).toFixed(2)}%`;
  const fmtPct1 = (v: number) => `${v >= 0 ? '+' : ''}${(v * 100).toFixed(1)}%`;

  return (
    <div className="glass-panel" style={{
      padding: '1.25rem 1.5rem',
      background: 'linear-gradient(135deg, rgba(102,126,234,0.03) 0%, rgba(118,75,162,0.03) 100%)',
      borderLeft: '3px solid #667eea',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
        <Trophy size={16} color="#ffd700" />
        <h4 style={{ margin: 0, fontSize: '0.85rem', flex: 1 }}>Alpha vs Omega</h4>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          style={{
            background: 'rgba(102,126,234,0.1)',
            border: '1px solid rgba(102,126,234,0.2)',
            borderRadius: '6px',
            padding: '0.25rem 0.5rem',
            cursor: refreshing ? 'wait' : 'pointer',
            display: 'flex', alignItems: 'center', gap: '0.3rem',
            fontSize: '0.7rem', color: '#667eea', fontWeight: 600,
          }}
        >
          <RefreshCw size={12} className={refreshing ? 'animate-spin' : ''} />
          {refreshing ? 'Genererar...' : 'Nya scenarier'}
        </button>
      </div>

      {noData ? (
        <div style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)', padding: '0.5rem 0' }}>
          Inga scenarier genererade ännu. Klicka "Nya scenarier" för att starta — eller vänta till nästa söndag.
        </div>
      ) : (
        <>
          {/* Head-to-head comparison */}
          <div style={{
            display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: '0.75rem',
            marginBottom: '1rem', alignItems: 'stretch',
          }}>
            {/* Alpha card */}
            <div style={{
              padding: '0.75rem',
              borderRadius: '8px',
              background: alphaWins ? 'rgba(16,185,129,0.06)' : 'rgba(255,255,255,0.02)',
              border: `1px solid ${alphaWins ? 'rgba(16,185,129,0.2)' : 'rgba(255,255,255,0.06)'}`,
            }}>
              <div style={{ fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#667eea', marginBottom: '0.4rem' }}>
                🤖 Alpha (Pipeline)
              </div>
              <div style={{ fontSize: '1.1rem', fontWeight: 800, color: alpha.cum_return >= 0 ? '#10b981' : '#ef4444' }}>
                {fmtPct(alpha.cum_return)}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.15rem', marginTop: '0.3rem' }}>
                <Stat label="Sharpe" value={alpha.sharpe?.toFixed(2) || '—'} />
                <Stat label="Max DD" value={fmtPct1(-alpha.max_drawdown)} negative />
                <Stat label="Dagar" value={String(alpha.days_tracked)} />
              </div>
            </div>

            {/* VS */}
            <div style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center',
              justifyContent: 'center', gap: '0.2rem',
            }}>
              <div style={{
                fontSize: '0.75rem', fontWeight: 900, color: 'var(--text-tertiary)',
                padding: '0.3rem 0.5rem', borderRadius: '12px',
                background: 'rgba(255,255,255,0.04)',
              }}>
                VS
              </div>
              {!tooEarly && (
                <div style={{
                  fontSize: '0.6rem', fontWeight: 700,
                  color: alphaWins ? '#667eea' : '#a78bfa',
                }}>
                  {alphaWins ? '← Leder' : 'Leder →'}
                </div>
              )}
              {tooEarly && (
                <div style={{ fontSize: '0.6rem', color: 'var(--text-tertiary)' }}>
                  Tidigt
                </div>
              )}
            </div>

            {/* Omega card */}
            <div style={{
              padding: '0.75rem',
              borderRadius: '8px',
              background: omegaWins ? 'rgba(167,139,250,0.06)' : 'rgba(255,255,255,0.02)',
              border: `1px solid ${omegaWins ? 'rgba(167,139,250,0.2)' : 'rgba(255,255,255,0.06)'}`,
            }}>
              <div style={{ fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#a78bfa', marginBottom: '0.4rem' }}>
                🎯 Omega (Scenarier)
              </div>
              <div style={{ fontSize: '1.1rem', fontWeight: 800, color: omega.cum_return >= 0 ? '#10b981' : '#ef4444' }}>
                {fmtPct(omega.cum_return)}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.15rem', marginTop: '0.3rem' }}>
                <Stat label="Sharpe" value={omega.sharpe?.toFixed(2) || '—'} />
                <Stat label="Max DD" value={fmtPct1(-omega.max_drawdown)} negative />
                <Stat label="Dagar" value={String(omega.days_tracked)} />
              </div>
            </div>
          </div>

          {/* Omega portfolio details */}
          {omega_port && (
            <div style={{
              padding: '0.6rem 0.75rem', borderRadius: '8px',
              background: 'rgba(167,139,250,0.04)',
              border: '1px solid rgba(167,139,250,0.1)',
              marginBottom: '0.75rem',
            }}>
              <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                  <MiniStat icon={<TrendingUp size={12} color="#10b981" />} label="Förväntad" value={fmtPct1(omega_port.expected_return)} positive />
                  <MiniStat icon={<TrendingDown size={12} color="#ef4444" />} label="Worst case" value={fmtPct1(omega_port.worst_case_return)} />
                  <MiniStat icon={<Shield size={12} color="#f59e0b" />} label="CVaR 5%" value={fmtPct1(-omega_port.cvar_5pct)} />
                </div>
                <div style={{ fontSize: '0.6rem', color: 'var(--text-tertiary)' }}>
                  {omega_port.n_scenarios} scenarier
                </div>
              </div>

              {/* Top weights bar */}
              {omega.weights && Object.keys(omega.weights).length > 0 && (
                <div style={{ marginTop: '0.5rem' }}>
                  <div style={{ fontSize: '0.6rem', color: 'var(--text-tertiary)', marginBottom: '0.25rem' }}>
                    Omega-allokering
                  </div>
                  <div style={{ display: 'flex', gap: '1px', height: '16px', borderRadius: '4px', overflow: 'hidden' }}>
                    {Object.entries(omega.weights)
                      .filter(([, w]) => w > 0.03)
                      .sort(([, a], [, b]) => b - a)
                      .map(([asset, weight]) => (
                        <div
                          key={asset}
                          style={{
                            flex: weight,
                            background: getAssetColor(asset),
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            fontSize: '0.55rem', fontWeight: 700, color: '#fff',
                            minWidth: weight > 0.08 ? 'auto' : 0,
                          }}
                          title={`${ASSET_LABELS[asset] || asset}: ${(weight * 100).toFixed(0)}%`}
                        >
                          {weight > 0.08 ? `${ASSET_LABELS[asset] || asset}` : ''}
                        </div>
                      ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Scenarios toggle */}
          {scenarios.length > 0 && (
            <>
              <button
                onClick={() => setShowScenarios(!showScenarios)}
                style={{
                  background: showScenarios ? 'rgba(167,139,250,0.08)' : 'transparent',
                  border: '1px solid rgba(167,139,250,0.12)',
                  borderRadius: '6px',
                  padding: '0.35rem 0.7rem',
                  cursor: 'pointer',
                  fontSize: '0.72rem',
                  color: '#a78bfa',
                  fontWeight: 600,
                  width: '100%',
                  transition: 'all 0.2s ease',
                }}
              >
                {showScenarios ? '▾ Dölj scenarier' : `▸ Visa ${scenarios.length} scenarier`}
              </button>

              {showScenarios && (
                <div className="animate-fade-in" style={{ marginTop: '0.5rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                  {scenarios.map((s, i) => (
                    <div key={i} style={{
                      padding: '0.5rem 0.6rem',
                      borderRadius: '6px',
                      background: 'rgba(255,255,255,0.02)',
                      border: '1px solid rgba(255,255,255,0.04)',
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.2rem' }}>
                        <span style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                          {s.name}
                        </span>
                        <span style={{
                          fontSize: '0.65rem', fontWeight: 800, padding: '0.1rem 0.4rem',
                          borderRadius: '4px', background: getProbColor(s.probability),
                          color: '#fff',
                        }}>
                          {(s.probability * 100).toFixed(0)}%
                        </span>
                      </div>
                      <p style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', margin: 0, lineHeight: 1.5 }}>
                        {s.description}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}

// Helper components

function Stat({ label, value, negative }: { label: string; value: string; negative?: boolean }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem' }}>
      <span style={{ color: 'var(--text-tertiary)' }}>{label}</span>
      <span style={{ fontWeight: 600, color: negative ? '#ef4444' : 'var(--text-secondary)' }}>{value}</span>
    </div>
  );
}

function MiniStat({ icon, label, value, positive }: { icon: React.ReactNode; label: string; value: string; positive?: boolean }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
      {icon}
      <span style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)' }}>{label}:</span>
      <span style={{ fontSize: '0.72rem', fontWeight: 700, color: positive ? '#10b981' : 'var(--text-secondary)' }}>{value}</span>
    </div>
  );
}

function getAssetColor(asset: string): string {
  const colors: Record<string, string> = {
    sp500: '#6c5ce7', gold: '#ffd700', us10y: '#9d4edd', oil: '#636e72',
    btc: '#f7931a', 'global-equity': '#4facfe', eurusd: '#00f2fe', silver: '#c0c0c0',
    'sector-tech': '#3498db', 'sector-energy': '#e67e22', 'sector-finance': '#2ecc71',
    'sector-health': '#e74c3c', 'region-em': '#e84393', 'region-europe': '#0984e3',
  };
  return colors[asset] || '#888';
}

function getProbColor(prob: number): string {
  if (prob >= 0.4) return '#10b981';
  if (prob >= 0.25) return '#f59e0b';
  return '#6b7280';
}
