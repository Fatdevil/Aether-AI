import { useState, useEffect, useCallback } from 'react';
import { api, type APICorrelationData } from '../api/client';

const NAME_MAP: Record<string, string> = {
  btc: 'BTC', sp500: 'S&P 500', gold: 'Guld', silver: 'Silver',
  oil: 'Olja', us10y: '10Y', eurusd: 'EUR/USD', 'global-equity': 'ACWI',
};

const PERIODS = ['7d', '30d', '90d', '180d'] as const;
type Period = typeof PERIODS[number];

function corrToColor(corr: number): string {
  if (corr >= 0.7) return 'rgba(0, 200, 81, 0.85)';
  if (corr >= 0.4) return 'rgba(0, 200, 81, 0.50)';
  if (corr >= 0.15) return 'rgba(0, 200, 81, 0.22)';
  if (corr > -0.15) return 'rgba(255, 255, 255, 0.05)';
  if (corr > -0.4) return 'rgba(255, 71, 87, 0.22)';
  if (corr > -0.7) return 'rgba(255, 71, 87, 0.50)';
  return 'rgba(255, 71, 87, 0.85)';
}

function corrToTextColor(corr: number): string {
  if (Math.abs(corr) >= 0.4) return '#fff';
  if (corr >= 0.15) return '#7bed9f';
  if (corr <= -0.15) return '#ff6b81';
  return 'var(--text-tertiary)';
}

interface SelectedPair {
  a: string;
  b: string;
  corr: number;
}

interface Insight {
  icon: string;
  title: string;
  text: string;
}

export default function CorrelationHeatmap() {
  const [data, setData] = useState<APICorrelationData | null>(null);
  const [period, setPeriod] = useState<Period>('30d');
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<SelectedPair | null>(null);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [insightsSource, setInsightsSource] = useState('');
  const [insightsLoading, setInsightsLoading] = useState(false);

  const fetchData = useCallback(async (p: Period) => {
    setLoading(true);
    setInsightsLoading(true);
    try {
      const result = await api.getCorrelations(p);
      setData(result);
    } catch {
      setData(null);
    }
    setLoading(false);

    // Fetch AI insights in background
    try {
      const insightsResult = await api.getCorrelationInsights(p);
      setInsights(insightsResult.insights || []);
      setInsightsSource(insightsResult.source || '');
    } catch {
      setInsights([]);
      setInsightsSource('');
    }
    setInsightsLoading(false);
  }, []);

  useEffect(() => {
    fetchData(period);
  }, [period, fetchData]);

  const handlePeriodChange = (p: Period) => {
    setPeriod(p);
    setSelected(null);
  };

  if (!data) {
    return (
      <div className="glass-panel" style={{ padding: '1.5rem' }}>
        <h4 style={{ margin: '0 0 1rem', fontSize: '1.1rem' }}>🔗 Korrelationsmatris</h4>
        <p style={{ color: 'var(--text-tertiary)', margin: 0, fontSize: '0.85rem' }}>
          {loading ? 'Laddar...' : 'Data ej tillgänglig'}
        </p>
      </div>
    );
  }

  const assets = Object.keys(data.matrix);
  const sys = data.systemic;

  // Find fundamental relationship for selected pair
  const fundamentalPairs: Record<string, string> = {
    'gold|us10y': 'Guld faller när räntor stiger (högre reala räntor)',
    'us10y|gold': 'Guld faller när räntor stiger (högre reala räntor)',
    'gold|eurusd': 'Guld och EUR rör sig med svagare USD',
    'eurusd|gold': 'Guld och EUR rör sig med svagare USD',
    'btc|sp500': 'BTC korrelerar med riskaptit sedan 2020',
    'sp500|btc': 'BTC korrelerar med riskaptit sedan 2020',
    'oil|sp500': 'Olja stiger med ekonomisk tillväxt',
    'sp500|oil': 'Olja stiger med ekonomisk tillväxt',
    'gold|btc': 'Båda ses som inflationshedge men BTC är volatilare',
    'btc|gold': 'Båda ses som inflationshedge men BTC är volatilare',
    'sp500|us10y': 'Beror på om räntor stiger pga tillväxt eller inflation',
    'us10y|sp500': 'Beror på om räntor stiger pga tillväxt eller inflation',
  };

  return (
    <div className="glass-panel" style={{ padding: '1.5rem' }}>
      {/* Header */}
      <div className="flex justify-between items-center" style={{ marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div className="flex items-center gap-2">
          <h4 style={{ margin: 0, fontSize: '1.1rem' }}>🔗 Korrelationsmatris</h4>
          {sys && (
            <span style={{
              fontSize: '0.7rem', padding: '0.15rem 0.5rem', borderRadius: '4px',
              background: sys.risk_on_count > sys.risk_off_count ? 'rgba(0,200,81,0.1)' : 'rgba(255,71,87,0.1)',
              color: sys.risk_on_count > sys.risk_off_count ? 'var(--score-positive)' : 'var(--score-negative)',
            }}>
              {sys.risk_on_count} on / {sys.risk_off_count} off
            </span>
          )}
        </div>

        {/* Period Selector */}
        <div className="flex gap-1">
          {PERIODS.map(p => (
            <button
              key={p}
              onClick={() => handlePeriodChange(p)}
              style={{
                padding: '0.3rem 0.6rem', borderRadius: '6px', fontSize: '0.75rem',
                border: 'none', cursor: 'pointer', fontWeight: p === period ? 700 : 400,
                background: p === period ? 'var(--accent-cyan)' : 'rgba(255,255,255,0.06)',
                color: p === period ? '#000' : 'var(--text-secondary)',
                transition: 'all 0.2s',
              }}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Loading overlay */}
      {loading && (
        <div style={{ textAlign: 'center', padding: '1rem', color: 'var(--text-tertiary)', fontSize: '0.85rem' }}>
          Beräknar korrelationer för {period}...
        </div>
      )}

      {/* Heatmap Grid */}
      {!loading && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ borderCollapse: 'separate', borderSpacing: '2px', width: '100%' }}>
            <thead>
              <tr>
                <th style={{ width: '65px' }} />
                {assets.map(a => (
                  <th key={a} style={{
                    fontSize: '0.68rem', fontWeight: 500, color: 'var(--text-secondary)',
                    padding: '0.3rem 0.15rem', textAlign: 'center', whiteSpace: 'nowrap',
                  }}>
                    {NAME_MAP[a] || a}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {assets.map(row => (
                <tr key={row}>
                  <td style={{
                    fontSize: '0.72rem', fontWeight: 500, color: 'var(--text-secondary)',
                    padding: '0.2rem 0.4rem 0.2rem 0', whiteSpace: 'nowrap', textAlign: 'right',
                  }}>
                    {NAME_MAP[row] || row}
                  </td>
                  {assets.map(col => {
                    const corr = data.matrix[row]?.[col] ?? 0;
                    const isDiagonal = row === col;
                    const isSelected = selected && ((selected.a === row && selected.b === col) || (selected.a === col && selected.b === row));

                    return (
                      <td
                        key={col}
                        onClick={() => {
                          if (!isDiagonal) setSelected(isSelected ? null : { a: row, b: col, corr });
                        }}
                        style={{
                          background: isDiagonal ? 'rgba(255,255,255,0.02)' : corrToColor(corr),
                          color: isDiagonal ? 'var(--text-tertiary)' : corrToTextColor(corr),
                          fontSize: '0.72rem', fontWeight: 600,
                          textAlign: 'center', padding: '0.4rem 0.2rem',
                          borderRadius: '4px',
                          cursor: isDiagonal ? 'default' : 'pointer',
                          border: isSelected ? '2px solid var(--accent-cyan)' : '2px solid transparent',
                          transition: 'all 0.15s ease',
                          minWidth: '42px',
                        }}
                        title={isDiagonal ? '' : `${NAME_MAP[row]}↔${NAME_MAP[col]}: ${corr > 0 ? '+' : ''}${corr.toFixed(2)}`}
                      >
                        {isDiagonal ? '—' : `${corr > 0 ? '+' : ''}${corr.toFixed(2)}`}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Legend */}
      <div style={{ display: 'flex', justifyContent: 'center', gap: '0.5rem', marginTop: '0.75rem', fontSize: '0.65rem', color: 'var(--text-tertiary)' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: '0.2rem' }}>
          <span style={{ width: 12, height: 12, borderRadius: 3, background: 'rgba(255,71,87,0.85)', display: 'inline-block' }}/>
          stark neg
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: '0.2rem' }}>
          <span style={{ width: 12, height: 12, borderRadius: 3, background: 'rgba(255,71,87,0.35)', display: 'inline-block' }}/>
          svag neg
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: '0.2rem' }}>
          <span style={{ width: 12, height: 12, borderRadius: 3, background: 'rgba(255,255,255,0.05)', display: 'inline-block', border: '1px solid rgba(255,255,255,0.1)' }}/>
          neutral
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: '0.2rem' }}>
          <span style={{ width: 12, height: 12, borderRadius: 3, background: 'rgba(0,200,81,0.35)', display: 'inline-block' }}/>
          svag pos
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: '0.2rem' }}>
          <span style={{ width: 12, height: 12, borderRadius: 3, background: 'rgba(0,200,81,0.85)', display: 'inline-block' }}/>
          stark pos
        </span>
      </div>

      {/* Selected pair detail */}
      {selected && (
        <div className="animate-fade-in" style={{
          marginTop: '1rem', padding: '1rem', borderRadius: '8px',
          background: 'rgba(0, 242, 254, 0.05)', border: '1px solid rgba(0, 242, 254, 0.15)',
        }}>
          <div className="flex justify-between items-center" style={{ marginBottom: '0.5rem' }}>
            <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>
              {NAME_MAP[selected.a] || selected.a} ↔ {NAME_MAP[selected.b] || selected.b}
            </span>
            <span style={{
              fontSize: '1.1rem', fontWeight: 700,
              color: selected.corr > 0 ? 'var(--score-positive)' : selected.corr < 0 ? 'var(--score-negative)' : 'var(--text-tertiary)',
            }}>
              {selected.corr > 0 ? '+' : ''}{selected.corr.toFixed(3)}
            </span>
          </div>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
            {Math.abs(selected.corr) > 0.7 ? '⚡ Stark korrelation' :
             Math.abs(selected.corr) > 0.4 ? '📊 Måttlig korrelation' :
             Math.abs(selected.corr) > 0.15 ? '🔹 Svag korrelation' : '⚪ Ingen signifikant'}
            {' '} över senaste {period}
          </div>
          {/* Interpretation */}
          <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
            {selected.corr > 0.7
              ? `${NAME_MAP[selected.a]} och ${NAME_MAP[selected.b]} rör sig i samma riktning. Hög exponering mot båda = koncentrationsrisk.`
              : selected.corr < -0.4
              ? `${NAME_MAP[selected.a]} och ${NAME_MAP[selected.b]} rör sig i motsatt riktning. Bra kombination för diversifiering.`
              : selected.corr > 0.3
              ? `Måttlig positiv koppling – inte tillräckligt stark för pålitlig hedge.`
              : selected.corr < -0.15
              ? `Svag negativ koppling – viss diversifieringsnytta men inte pålitlig.`
              : `Ingen meningsfull korrelation under denna period.`}
          </div>
          {/* Fundamental note if available */}
          {fundamentalPairs[`${selected.a}|${selected.b}`] && (
            <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: 'var(--accent-cyan)', fontStyle: 'italic' }}>
              💡 {fundamentalPairs[`${selected.a}|${selected.b}`]}
            </div>
          )}
        </div>
      )}

      {/* AI Insights Panel */}
      {(insights.length > 0 || insightsLoading) && (
        <div style={{
          marginTop: '1rem', padding: '1rem', borderRadius: '8px',
          background: 'rgba(139, 92, 246, 0.05)', border: '1px solid rgba(139, 92, 246, 0.15)',
        }}>
          <div className="flex justify-between items-center" style={{ marginBottom: '0.75rem' }}>
            <h4 style={{ margin: 0, fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              🧠 AI-analys
              <span style={{
                fontSize: '0.6rem', padding: '0.12rem 0.4rem', borderRadius: '4px',
                background: insightsSource === 'ai' ? 'rgba(139, 92, 246, 0.2)' : 'rgba(255,255,255,0.06)',
                color: insightsSource === 'ai' ? '#a78bfa' : 'var(--text-tertiary)',
              }}>
                {insightsSource === 'ai' ? 'Gemini' : 'rule-based'}
              </span>
            </h4>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>
              {period}
            </span>
          </div>

          {insightsLoading ? (
            <div style={{ textAlign: 'center', padding: '0.75rem', color: 'var(--text-tertiary)', fontSize: '0.82rem' }}>
              🔄 Analyserar korrelationsmatris...
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {insights.map((insight, i) => (
                <div key={i} className="animate-fade-in" style={{
                  padding: '0.7rem 0.85rem', borderRadius: '6px',
                  background: 'rgba(255,255,255,0.02)',
                  borderLeft: '3px solid rgba(139, 92, 246, 0.4)',
                  animationDelay: `${i * 0.08}s`,
                }}>
                  <div style={{ fontSize: '0.82rem', fontWeight: 600, marginBottom: '0.25rem' }}>
                    {insight.icon} {insight.title}
                  </div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                    {insight.text}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
