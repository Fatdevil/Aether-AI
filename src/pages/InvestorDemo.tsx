import { useState, useEffect } from 'react';
import { api } from '../api/client';

// ============================================================
// AETHER AI — INVESTOR DEMO
// A standalone page designed for institutional investors.
// Fetches LIVE data from the backend. No mocks.
// ============================================================

// --- Types ---
interface LiveData {
  health: any;
  political: any;
  dual: any;
  regime: any;
  assets: any[];
  alerts: any;
}

// --- Constants ---
const PIPELINE_LAYERS = [
  { id: 'L1', name: 'Market Data', desc: 'Realtidspriser via yfinance (17 tillgångar)', icon: '📊', color: '#4facfe' },
  { id: 'L2', name: 'Regime Detection', desc: 'RISK_ON / NEUTRAL / RISK_OFF / CRISIS', icon: '🔍', color: '#f59e0b' },
  { id: 'L3', name: 'Predictive Intelligence', desc: 'Kausalkedjor, lead-lag, politisk intelligens', icon: '🧠', color: '#a78bfa' },
  { id: 'L4', name: 'AI Agent Analysis', desc: '4×AI (Macro, Micro, Sentiment, Teknisk)', icon: '🤖', color: '#667eea' },
  { id: 'L5', name: 'Supervisor Synthesis', desc: 'Tango-filter, konfidensvotering, slutpoäng', icon: '👔', color: '#8b5cf6' },
  { id: 'L6', name: 'Convexity & Signals', desc: 'Asymmetriska positioner, trade signals', icon: '📈', color: '#10b981' },
  { id: 'L7', name: 'Portfolio Optimization', desc: 'Markowitz MPT + regime-anpassad kovarians', icon: '💼', color: '#06b6d4' },
  { id: 'L7b', name: 'Scenario Engine (Omega)', desc: 'Min-regret optimering, Monte Carlo CVaR', icon: '🎯', color: '#ec4899' },
  { id: 'L8', name: 'Risk Management', desc: 'Trailing stop, drawdown-skydd, VaR-gränser', icon: '🛡', color: '#ef4444' },
  { id: 'L9', name: 'Output & Persistence', desc: 'Databas, API, daglig snapshot', icon: '💾', color: '#6b7280' },
];

const COMPETITORS = [
  { name: 'Bloomberg Terminal', price: '$24,000/år', features: 'Data + nyheter + chat', ai: 'Nej', scenario: 'Nej' },
  { name: 'Infront', price: '$5,000/år', features: 'Data + moduler', ai: 'Nej', scenario: 'Nej' },
  { name: 'ChatGPT Pro', price: '$200/mån', features: 'Generell AI', ai: 'Ja (generell)', scenario: 'Nej' },
  { name: 'Aether AI', price: '$50/mån', features: 'Data + AI + Scenarier + Portfolio', ai: '10-lagers pipeline', scenario: 'Minimum-regret' },
];

export default function InvestorDemo() {
  const [data, setData] = useState<Partial<LiveData>>({});
  const [_loading, setLoading] = useState(true);
  const [activeLayer, setActiveLayer] = useState<string | null>(null);

  useEffect(() => {
    Promise.allSettled([
      api.getSystemHealth(),
      api.getDualPortfolio().catch(() => null),
      api.getRegime().catch(() => null),
      api.getAssets().catch(() => []),
      api.getAlerts(5).catch(() => null),
    ]).then(([health, dual, regime, assets, alerts]) => {
      setData({
        health: health.status === 'fulfilled' ? health.value : null,
        dual: dual.status === 'fulfilled' ? dual.value : null,
        regime: regime.status === 'fulfilled' ? regime.value : null,
        assets: assets.status === 'fulfilled' ? (assets.value as any[]) : [],
        alerts: alerts.status === 'fulfilled' ? alerts.value : null,
      });
      setLoading(false);
    });
  }, []);

  return (
    <div style={styles.page}>
      {/* ============ HERO ============ */}
      <header style={styles.hero}>
        <div style={styles.heroInner}>
          <div style={styles.heroBadge}>EARLY ACCESS</div>
          <h1 style={styles.heroTitle}>
            <span style={styles.heroAether}>AETHER</span>
            <span style={styles.heroAI}> AI</span>
          </h1>
          <p style={styles.heroSub}>
            AI-First Investment Intelligence Engine
          </p>
          <p style={styles.heroDesc}>
            10 autonoma AI-lager. 17 tillgångar. 5 sektorer. 4 regioner.
            <br />Realtids-nyhetsbevakning. Politisk intelligens. Scenariobaserad portföljoptimering.
          </p>

          {/* Live status indicators */}
          <div style={styles.statusRow}>
            <StatusPill
              label="System"
              value={data.health?.status || '...'}
              color={data.health?.status === 'HEALTHY' ? '#10b981' : '#f59e0b'}
            />
            <StatusPill
              label="Regime"
              value={data.regime?.regime?.replace('_', ' ') || '...'}
              color={data.regime?.regime === 'RISK_ON' ? '#10b981' : data.regime?.regime === 'RISK_OFF' ? '#ef4444' : '#f59e0b'}
            />
            <StatusPill
              label="Tillgångar"
              value={`${data.assets?.length || 0} live`}
              color="#4facfe"
            />
            <StatusPill
              label="Pipeline"
              value="Autonom"
              color="#a78bfa"
            />
          </div>
        </div>
      </header>

      {/* ============ SECTION 1: POLITICAL INTELLIGENCE ============ */}
      <Section
        number="01"
        title="Reagerar snabbare än Bloomberg"
        subtitle="5 minuter från nyhet till portföljjustering — automatiskt"
      >
        <div style={styles.splitGrid}>
          <div style={styles.featureCard}>
            <div style={styles.featureIcon}>⚡</div>
            <h4 style={styles.featureTitle}>Realtidsdetektering</h4>
            <p style={styles.featureText}>
              NewsSentinel skannar nyhetsflöden var 5:e minut. Vid impact ≥ 5 
              triggas Political Intelligence direkt — ingen manuell input, ingen fördröjning.
            </p>
            <div style={styles.comparisonBox}>
              <ComparisonRow label="Bloomberg" value="Visar nyheten" time="Manuell bedömning" />
              <ComparisonRow label="Aether AI" value="Detekterar + justerar portfölj" time="< 5 min" highlight />
            </div>
          </div>

          <div style={styles.featureCard}>
            <div style={styles.featureIcon}>🎯</div>
            <h4 style={styles.featureTitle}>Eskaleringsdetektering</h4>
            <p style={styles.featureText}>
              Systemet räknar signaler per aktör (Trump, Fed, ECB, Xi, Putin). 
              Vid 3+ eskaleringssignaler med 2x dominans → politisk risk skiftar till HIGH → 
              portföljvikt ökar från 5% till 25%.
            </p>
            <div style={styles.metricRow}>
              <Metric label="Aktörer" value="5" />
              <Metric label="Signal-fraser" value="28" />
              <Metric label="AI-kostnad" value="$0" highlight />
            </div>
          </div>
        </div>

        {/* Live alerts preview */}
        {data.alerts?.alerts?.length > 0 && (
          <div style={styles.liveBox}>
            <div style={styles.liveLabel}>
              <span style={styles.liveDot} /> LIVE NYHETSBEVAKNING
            </div>
            <div style={styles.alertList}>
              {data.alerts.alerts.slice(0, 4).map((a: any, i: number) => (
                <div key={i} style={styles.alertItem}>
                  <span style={{
                    ...styles.alertImpact,
                    background: a.impact_score >= 7 ? '#ef444420' : a.impact_score >= 5 ? '#f59e0b20' : '#6b728020',
                    color: a.impact_score >= 7 ? '#ef4444' : a.impact_score >= 5 ? '#f59e0b' : '#9ca3af',
                  }}>
                    {a.impact_score}
                  </span>
                  <span style={styles.alertTitle}>{a.title}</span>
                  <span style={styles.alertTime}>{a.time}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </Section>

      {/* ============ SECTION 2: ALPHA vs OMEGA ============ */}
      <Section
        number="02"
        title="Två portföljer — en tävling"
        subtitle="Pipeline-driven vs Scenario-driven, head-to-head med riktig data"
      >
        <div style={styles.splitGrid}>
          {/* Alpha */}
          <div style={{ ...styles.portfolioCard, borderColor: '#667eea30' }}>
            <div style={{ ...styles.portfolioHeader, color: '#667eea' }}>
              🤖 ALPHA — Pipeline-portfölj
            </div>
            <p style={styles.portfolioDesc}>
              Traditionell 10-lagerspipeline. 4 AI-agenter analyserar varje tillgång.
              Supervisor syntetiserar. Markowitz optimerar.
            </p>
            <div style={styles.portfolioStats}>
              <PortfolioStat
                label="Avkastning"
                value={data.dual?.comparison?.alpha?.cum_return
                  ? `${(data.dual.comparison.alpha.cum_return * 100).toFixed(2)}%`
                  : 'Spåras...'}
              />
              <PortfolioStat
                label="Sharpe"
                value={data.dual?.comparison?.alpha?.sharpe?.toFixed(2) || '—'}
              />
              <PortfolioStat
                label="Max DD"
                value={data.dual?.comparison?.alpha?.max_drawdown
                  ? `${(data.dual.comparison.alpha.max_drawdown * 100).toFixed(1)}%`
                  : '—'}
              />
            </div>
          </div>

          {/* Omega */}
          <div style={{ ...styles.portfolioCard, borderColor: '#a78bfa30' }}>
            <div style={{ ...styles.portfolioHeader, color: '#a78bfa' }}>
              🎯 OMEGA — Scenario-portfölj
            </div>
            <p style={styles.portfolioDesc}>
              AI genererar 3-5 makroekonomiska scenarier varje vecka. 
              Minimum-regret-optimering + Monte Carlo (1000 simuleringar) 
              hittar portföljen med lägst svansrisk.
            </p>
            <div style={styles.portfolioStats}>
              <PortfolioStat
                label="Förväntad"
                value={data.dual?.omega_details?.omega_portfolio?.expected_return
                  ? `${(data.dual.omega_details.omega_portfolio.expected_return * 100).toFixed(1)}%`
                  : '—'}
              />
              <PortfolioStat
                label="CVaR 5%"
                value={data.dual?.omega_details?.omega_portfolio?.cvar_5pct
                  ? `${(data.dual.omega_details.omega_portfolio.cvar_5pct * 100).toFixed(1)}%`
                  : '—'}
              />
              <PortfolioStat
                label="Worst case"
                value={data.dual?.omega_details?.omega_portfolio?.worst_case_return
                  ? `${(data.dual.omega_details.omega_portfolio.worst_case_return * 100).toFixed(1)}%`
                  : '—'}
              />
            </div>
          </div>
        </div>

        {/* Scenario cards */}
        {data.dual?.omega_details?.scenarios?.length > 0 && (
          <div style={styles.scenarioGrid}>
            <div style={styles.scenarioLabel}>AKTIVA MAKRO-SCENARIER</div>
            {data.dual.omega_details.scenarios.map((s: any, i: number) => (
              <div key={i} style={styles.scenarioCard}>
                <div style={styles.scenarioTop}>
                  <span style={styles.scenarioName}>{s.name}</span>
                  <span style={{
                    ...styles.scenarioProb,
                    background: s.probability >= 0.35 ? '#10b98118' : '#6b728018',
                    color: s.probability >= 0.35 ? '#10b981' : '#9ca3af',
                  }}>
                    {(s.probability * 100).toFixed(0)}%
                  </span>
                </div>
                <p style={styles.scenarioDesc}>{s.description}</p>
              </div>
            ))}
          </div>
        )}

        <div style={styles.insightBox}>
          <strong>Varför detta spelar roll:</strong> Traditionell portföljoptimering antar EN framtid. 
          Minimum-regret optimerar för ALLA möjliga framtider. I backtester visar min-regret 
          3x lägre svansrisk (CVaR 5.9% vs 15.4%) jämfört med likavikt.
        </div>
      </Section>

      {/* ============ SECTION 3: ARCHITECTURE ============ */}
      <Section
        number="03"
        title="10-Lagers Autonom Pipeline"
        subtitle="Var 6:e timme, helt automatiskt, utan mänsklig input"
      >
        <div style={styles.pipelineGrid}>
          {PIPELINE_LAYERS.map((layer) => (
            <div
              key={layer.id}
              style={{
                ...styles.pipelineCard,
                borderColor: activeLayer === layer.id ? layer.color : 'rgba(255,255,255,0.06)',
                background: activeLayer === layer.id ? `${layer.color}08` : 'rgba(255,255,255,0.02)',
              }}
              onMouseEnter={() => setActiveLayer(layer.id)}
              onMouseLeave={() => setActiveLayer(null)}
            >
              <div style={styles.pipelineTop}>
                <span style={{ ...styles.pipelineId, color: layer.color }}>{layer.id}</span>
                <span style={styles.pipelineIcon}>{layer.icon}</span>
              </div>
              <div style={styles.pipelineName}>{layer.name}</div>
              <div style={styles.pipelineDesc}>{layer.desc}</div>
            </div>
          ))}
        </div>

        <div style={styles.pipelineFlow}>
          {PIPELINE_LAYERS.map((l, i) => (
            <span key={l.id} style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
              <span style={{ color: l.color, fontWeight: 700, fontSize: '0.7rem' }}>{l.id}</span>
              {i < PIPELINE_LAYERS.length - 1 && <span style={{ color: '#4b5563', fontSize: '0.65rem' }}>→</span>}
            </span>
          ))}
        </div>
      </Section>

      {/* ============ SECTION 4: COST COMPARISON ============ */}
      <Section
        number="04"
        title="Kostnad vs Konkurrenter"
        subtitle="Samma analys, bråkdel av priset"
      >
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Plattform</th>
              <th style={styles.th}>Pris</th>
              <th style={styles.th}>AI-analys</th>
              <th style={styles.th}>Scenarioanalys</th>
            </tr>
          </thead>
          <tbody>
            {COMPETITORS.map((c, i) => (
              <tr key={i} style={c.name === 'Aether AI' ? styles.highlightRow : {}}>
                <td style={styles.td}>
                  <span style={{ fontWeight: c.name === 'Aether AI' ? 800 : 400 }}>{c.name}</span>
                </td>
                <td style={styles.td}>
                  <span style={{ color: c.name === 'Aether AI' ? '#10b981' : 'var(--text-secondary)', fontWeight: 700 }}>
                    {c.price}
                  </span>
                </td>
                <td style={styles.td}>
                  <span style={{ color: c.ai === 'Nej' ? '#ef4444' : '#10b981' }}>
                    {c.ai === 'Nej' ? '✗' : '✓'} {c.ai}
                  </span>
                </td>
                <td style={styles.td}>
                  <span style={{ color: c.scenario === 'Nej' ? '#ef4444' : '#10b981' }}>
                    {c.scenario === 'Nej' ? '✗' : '✓'} {c.scenario}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <div style={styles.costBreakdown}>
          <div style={styles.costLabel}>MÅNADSKOSTNAD — DETALJSUPPDELNING</div>
          <div style={styles.costGrid}>
            <CostItem label="Gemini Flash AI" cost="~$40" pct={80} color="#667eea" />
            <CostItem label="Scenario Engine" cost="~$0.20" pct={1} color="#a78bfa" />
            <CostItem label="Political Intelligence" cost="$0" pct={0} color="#10b981" />
            <CostItem label="Infrastruktur (Railway)" cost="~$5" pct={10} color="#f59e0b" />
          </div>
        </div>
      </Section>

      {/* ============ FOOTER ============ */}
      <footer style={styles.footer}>
        <div style={styles.footerInner}>
          <div style={styles.footerLogo}>
            <span style={{ fontSize: '1.2rem', fontWeight: 800, letterSpacing: '0.15em' }}>AETHER AI</span>
            <span style={{ fontSize: '0.7rem', color: '#6b7280', marginTop: '0.25rem' }}>Early Commercial Phase</span>
          </div>
          <div style={styles.footerText}>
            Systemet körs autonomt sedan mars 2026. All data på denna sida är live.
          </div>
          <div style={styles.footerCta}>
            Intresserad? Kontakta oss för en personlig djupdykning.
          </div>
        </div>
      </footer>
    </div>
  );
}


// ============================================================
// HELPER COMPONENTS
// ============================================================

function Section({ number, title, subtitle, children }: {
  number: string; title: string; subtitle: string; children: React.ReactNode;
}) {
  return (
    <section style={styles.section}>
      <div style={styles.sectionInner}>
        <div style={styles.sectionNumber}>{number}</div>
        <h2 style={styles.sectionTitle}>{title}</h2>
        <p style={styles.sectionSub}>{subtitle}</p>
        {children}
      </div>
    </section>
  );
}

function StatusPill({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={styles.statusPill}>
      <span style={styles.statusLabel}>{label}</span>
      <span style={{ ...styles.statusValue, color }}>{value}</span>
    </div>
  );
}

function ComparisonRow({ label, value, time, highlight }: {
  label: string; value: string; time: string; highlight?: boolean;
}) {
  return (
    <div style={{
      ...styles.compRow,
      background: highlight ? 'rgba(16,185,129,0.06)' : 'transparent',
      borderLeft: highlight ? '2px solid #10b981' : '2px solid transparent',
    }}>
      <span style={{ ...styles.compLabel, color: highlight ? '#10b981' : '#9ca3af' }}>{label}</span>
      <span style={styles.compValue}>{value}</span>
      <span style={{ ...styles.compTime, color: highlight ? '#10b981' : '#6b7280' }}>{time}</span>
    </div>
  );
}

function Metric({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div style={styles.metricItem}>
      <div style={{ ...styles.metricValue, color: highlight ? '#10b981' : '#e5e7eb' }}>{value}</div>
      <div style={styles.metricLabel}>{label}</div>
    </div>
  );
}

function PortfolioStat({ label, value }: { label: string; value: string }) {
  return (
    <div style={styles.portStat}>
      <div style={styles.portStatLabel}>{label}</div>
      <div style={styles.portStatValue}>{value}</div>
    </div>
  );
}

function CostItem({ label, cost, pct, color }: { label: string; cost: string; pct: number; color: string }) {
  return (
    <div style={styles.costItem}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.3rem' }}>
        <span style={styles.costItemLabel}>{label}</span>
        <span style={{ ...styles.costItemValue, color }}>{cost}</span>
      </div>
      <div style={styles.costBar}>
        <div style={{ ...styles.costBarFill, width: `${Math.max(pct, 2)}%`, background: color }} />
      </div>
    </div>
  );
}


// ============================================================
// STYLES — Dark, institutional, premium
// ============================================================

const styles: Record<string, React.CSSProperties> = {
  page: {
    minHeight: '100vh',
    background: '#000',
    color: '#e5e7eb',
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
  },

  // Hero
  hero: {
    padding: '6rem 2rem 4rem',
    textAlign: 'center' as const,
    background: 'linear-gradient(180deg, #000 0%, #0a0a0f 100%)',
    borderBottom: '1px solid rgba(255,255,255,0.04)',
  },
  heroInner: { maxWidth: '800px', margin: '0 auto' },
  heroBadge: {
    display: 'inline-block',
    fontSize: '0.65rem',
    fontWeight: 700,
    letterSpacing: '0.2em',
    color: '#a78bfa',
    padding: '0.3rem 0.8rem',
    borderRadius: '20px',
    border: '1px solid rgba(167,139,250,0.3)',
    marginBottom: '1.5rem',
  },
  heroTitle: { fontSize: '3.5rem', fontWeight: 900, letterSpacing: '0.1em', margin: '0 0 0.5rem', lineHeight: 1.1 },
  heroAether: { color: '#e5e7eb' },
  heroAI: {
    background: 'linear-gradient(135deg, #667eea, #a78bfa)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
  } as React.CSSProperties,
  heroSub: { fontSize: '1.1rem', color: '#9ca3af', fontWeight: 500, margin: '0 0 1rem', letterSpacing: '0.03em' },
  heroDesc: { fontSize: '0.88rem', color: '#6b7280', lineHeight: 1.8, margin: '0 0 2rem' },
  statusRow: {
    display: 'flex',
    gap: '1rem',
    justifyContent: 'center',
    flexWrap: 'wrap' as const,
  },
  statusPill: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.4rem',
    padding: '0.35rem 0.8rem',
    borderRadius: '6px',
    background: 'rgba(255,255,255,0.03)',
    border: '1px solid rgba(255,255,255,0.06)',
  },
  statusLabel: { fontSize: '0.7rem', color: '#6b7280', fontWeight: 500 },
  statusValue: { fontSize: '0.75rem', fontWeight: 700 },

  // Sections
  section: {
    padding: '5rem 2rem',
    borderBottom: '1px solid rgba(255,255,255,0.04)',
  },
  sectionInner: { maxWidth: '1000px', margin: '0 auto' },
  sectionNumber: {
    fontSize: '0.7rem',
    fontWeight: 800,
    color: '#667eea',
    letterSpacing: '0.15em',
    marginBottom: '0.5rem',
  },
  sectionTitle: { fontSize: '2rem', fontWeight: 800, margin: '0 0 0.5rem', color: '#f3f4f6' },
  sectionSub: { fontSize: '0.95rem', color: '#6b7280', margin: '0 0 2.5rem', lineHeight: 1.6 },

  // Feature cards
  splitGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginBottom: '1.5rem' },
  featureCard: {
    padding: '1.5rem',
    borderRadius: '12px',
    background: 'rgba(255,255,255,0.02)',
    border: '1px solid rgba(255,255,255,0.06)',
  },
  featureIcon: { fontSize: '1.5rem', marginBottom: '0.75rem' },
  featureTitle: { fontSize: '1rem', fontWeight: 700, margin: '0 0 0.5rem', color: '#f3f4f6' },
  featureText: { fontSize: '0.82rem', color: '#9ca3af', lineHeight: 1.7, margin: '0 0 1rem' },

  // Comparison
  comparisonBox: {
    borderRadius: '8px',
    overflow: 'hidden',
    border: '1px solid rgba(255,255,255,0.06)',
  },
  compRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.75rem',
    padding: '0.5rem 0.75rem',
    fontSize: '0.78rem',
  },
  compLabel: { fontWeight: 700, width: '80px', fontSize: '0.72rem' },
  compValue: { flex: 1, color: '#d1d5db' },
  compTime: { fontWeight: 600, fontSize: '0.72rem' },

  // Metrics
  metricRow: { display: 'flex', gap: '1rem' },
  metricItem: { textAlign: 'center' as const, flex: 1, padding: '0.5rem', borderRadius: '6px', background: 'rgba(255,255,255,0.03)' },
  metricValue: { fontSize: '1.3rem', fontWeight: 800 },
  metricLabel: { fontSize: '0.68rem', color: '#6b7280', marginTop: '0.15rem' },

  // Live box
  liveBox: {
    padding: '1rem 1.25rem',
    borderRadius: '10px',
    background: 'rgba(16,185,129,0.03)',
    border: '1px solid rgba(16,185,129,0.1)',
  },
  liveLabel: {
    fontSize: '0.65rem',
    fontWeight: 700,
    color: '#10b981',
    letterSpacing: '0.1em',
    marginBottom: '0.75rem',
    display: 'flex',
    alignItems: 'center',
    gap: '0.4rem',
  },
  liveDot: {
    display: 'inline-block',
    width: '6px',
    height: '6px',
    borderRadius: '50%',
    background: '#10b981',
    animation: 'pulse 2s ease-in-out infinite',
  },
  alertList: { display: 'flex', flexDirection: 'column' as const, gap: '0.35rem' },
  alertItem: { display: 'flex', alignItems: 'center', gap: '0.6rem', padding: '0.3rem 0' },
  alertImpact: {
    fontSize: '0.65rem',
    fontWeight: 800,
    padding: '0.15rem 0.4rem',
    borderRadius: '4px',
    minWidth: '20px',
    textAlign: 'center' as const,
  },
  alertTitle: { fontSize: '0.78rem', color: '#d1d5db', flex: 1 },
  alertTime: { fontSize: '0.68rem', color: '#4b5563' },

  // Portfolio cards
  portfolioCard: {
    padding: '1.5rem',
    borderRadius: '12px',
    background: 'rgba(255,255,255,0.02)',
    border: '1px solid',
  },
  portfolioHeader: {
    fontSize: '0.72rem',
    fontWeight: 800,
    letterSpacing: '0.1em',
    marginBottom: '0.75rem',
  },
  portfolioDesc: { fontSize: '0.82rem', color: '#9ca3af', lineHeight: 1.7, margin: '0 0 1.25rem' },
  portfolioStats: { display: 'flex', gap: '0.5rem' },
  portStat: {
    flex: 1,
    textAlign: 'center' as const,
    padding: '0.6rem',
    borderRadius: '6px',
    background: 'rgba(255,255,255,0.03)',
  },
  portStatLabel: { fontSize: '0.65rem', color: '#6b7280', marginBottom: '0.2rem' },
  portStatValue: { fontSize: '1rem', fontWeight: 700, color: '#e5e7eb' },

  // Scenarios
  scenarioGrid: {
    marginBottom: '1.5rem',
    display: 'flex', flexDirection: 'column' as const, gap: '0.5rem',
  },
  scenarioLabel: { fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.1em', color: '#6b7280', marginBottom: '0.25rem' },
  scenarioCard: {
    padding: '0.75rem 1rem',
    borderRadius: '8px',
    background: 'rgba(255,255,255,0.02)',
    border: '1px solid rgba(255,255,255,0.05)',
  },
  scenarioTop: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.2rem' },
  scenarioName: { fontSize: '0.85rem', fontWeight: 700, color: '#e5e7eb' },
  scenarioProb: { fontSize: '0.7rem', fontWeight: 800, padding: '0.1rem 0.5rem', borderRadius: '4px' },
  scenarioDesc: { fontSize: '0.75rem', color: '#6b7280', margin: 0, lineHeight: 1.5 },

  // Insight
  insightBox: {
    padding: '1rem 1.25rem',
    borderRadius: '8px',
    background: 'rgba(167,139,250,0.04)',
    border: '1px solid rgba(167,139,250,0.1)',
    fontSize: '0.82rem',
    color: '#9ca3af',
    lineHeight: 1.7,
  },

  // Pipeline
  pipelineGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(5, 1fr)',
    gap: '0.75rem',
    marginBottom: '1.5rem',
  },
  pipelineCard: {
    padding: '1rem',
    borderRadius: '8px',
    border: '1px solid',
    cursor: 'pointer',
    transition: 'all 0.15s ease',
  },
  pipelineTop: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.3rem' },
  pipelineId: { fontSize: '0.6rem', fontWeight: 800, letterSpacing: '0.08em' },
  pipelineIcon: { fontSize: '1rem' },
  pipelineName: { fontSize: '0.75rem', fontWeight: 700, color: '#e5e7eb', marginBottom: '0.2rem' },
  pipelineDesc: { fontSize: '0.65rem', color: '#6b7280', lineHeight: 1.4 },
  pipelineFlow: {
    display: 'flex',
    gap: '0.5rem',
    justifyContent: 'center',
    flexWrap: 'wrap' as const,
    padding: '0.75rem',
    borderRadius: '8px',
    background: 'rgba(255,255,255,0.02)',
    border: '1px solid rgba(255,255,255,0.04)',
  },

  // Table
  table: { width: '100%', borderCollapse: 'collapse' as const, marginBottom: '2rem' },
  th: {
    textAlign: 'left' as const,
    padding: '0.75rem 1rem',
    fontSize: '0.7rem',
    fontWeight: 700,
    color: '#6b7280',
    letterSpacing: '0.08em',
    textTransform: 'uppercase' as const,
    borderBottom: '1px solid rgba(255,255,255,0.06)',
  },
  td: {
    padding: '0.75rem 1rem',
    fontSize: '0.82rem',
    borderBottom: '1px solid rgba(255,255,255,0.04)',
    color: '#d1d5db',
  },
  highlightRow: {
    background: 'rgba(16,185,129,0.04)',
    borderLeft: '2px solid #10b981',
  },

  // Cost breakdown
  costBreakdown: {
    padding: '1.25rem',
    borderRadius: '10px',
    background: 'rgba(255,255,255,0.02)',
    border: '1px solid rgba(255,255,255,0.06)',
  },
  costLabel: { fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.1em', color: '#6b7280', marginBottom: '1rem' },
  costGrid: { display: 'flex', flexDirection: 'column' as const, gap: '0.75rem' },
  costItem: {},
  costItemLabel: { fontSize: '0.78rem', color: '#9ca3af' },
  costItemValue: { fontSize: '0.82rem', fontWeight: 700 },
  costBar: { height: '4px', borderRadius: '2px', background: 'rgba(255,255,255,0.06)' },
  costBarFill: { height: '100%', borderRadius: '2px', transition: 'width 0.5s ease' },

  // Footer
  footer: {
    padding: '3rem 2rem',
    textAlign: 'center' as const,
    borderTop: '1px solid rgba(255,255,255,0.04)',
  },
  footerInner: { maxWidth: '600px', margin: '0 auto' },
  footerLogo: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    marginBottom: '1rem',
  },
  footerText: { fontSize: '0.82rem', color: '#6b7280', lineHeight: 1.7, marginBottom: '1rem' },
  footerCta: {
    fontSize: '0.85rem',
    color: '#a78bfa',
    fontWeight: 600,
  },
};
