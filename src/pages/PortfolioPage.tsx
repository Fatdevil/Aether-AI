import { useState, useEffect } from 'react';
import { Briefcase, Shield, Zap, Wallet, TrendingUp, TrendingDown, RefreshCw, Info } from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { api } from '../api/client';

// ============================================================
// CORE-SATELLITE PORTFOLIO PAGE
// 3-lagers portfölj: Kärna (60-70%) + Satellit (20-30%) + Kassa (10-20%)
// ============================================================

interface CorePos {
  asset_id: string;
  name: string;
  weight: number;
  instrument: string;
  courtage_pct: number;
  category: string;
  layer: string;
  regime_weight?: number;
  amount_sek?: number;
}

interface SatPos extends CorePos {
  direction: string;
  score: number;
  consensus: number;
  priority: number;
  reason: string;
}

interface CSPortfolio {
  core: CorePos[];
  satellites: SatPos[];
  cash: { weight: number; instrument: string; amount_sek?: number };
  core_total_pct: number;
  satellite_total_pct: number;
  cash_pct: number;
  total_positions: number;
  regime: string;
  conviction: number;
  trailing_stop_active: boolean;
  broker?: string;
  courtage_details?: {
    total_courtage_sek: number;
    total_fx_fee_sek: number;
    total_cost_sek: number;
    broker: string;
  };
  portfolio_value?: number;
  tier?: string;
  suggested_trades?: any[];
}

const LAYER_COLORS = {
  CORE: '#667eea',
  SATELLITE: '#f59e0b',
  CASH: '#10b981',
};

const CATEGORY_ICONS: Record<string, string> = {
  equity: '📈', safe_haven: '🛡️', cash_alt: '💰', diversifier: '🌍',
  geopolitik: '🎯', sektor_rotation: '🔄', momentum: '⚡', tillvaxt: '🚀',
  safe_haven_satellite: '🥈', contrarian: '🔮',
};

const REGIME_LABELS: Record<string, { label: string; color: string; icon: string }> = {
  'risk-on': { label: 'RISK ON', color: '#10b981', icon: '🟢' },
  'neutral': { label: 'NEUTRAL', color: '#f59e0b', icon: '🟡' },
  'risk-off': { label: 'RISK OFF', color: '#ef4444', icon: '🔴' },
  'crisis': { label: 'KRIS', color: '#dc2626', icon: '🚨' },
};

export default function PortfolioPage() {
  const [portfolio, setPortfolio] = useState<CSPortfolio | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchPortfolio = async () => {
    try {
      setLoading(true);
      const data = await api.getCoreSatellite(700000, 'avanza');
      setPortfolio(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Kunde inte hämta portfölj');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchPortfolio(); }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchPortfolio();
    setRefreshing(false);
  };

  if (loading) return (
    <main className="container" style={{ paddingTop: '2rem', textAlign: 'center', color: 'var(--text-tertiary)' }}>
      <RefreshCw size={24} className="spin" style={{ margin: '4rem auto' }} />
      <p>Beräknar Core-Satellite allokering...</p>
    </main>
  );

  if (error || !portfolio) return (
    <main className="container" style={{ paddingTop: '2rem', textAlign: 'center', color: '#ef4444' }}>
      <p>⚠️ {error || 'Ingen portföljdata'}</p>
      <button onClick={handleRefresh} className="glass-panel" style={{ padding: '0.5rem 1rem', cursor: 'pointer', border: 'none', color: 'var(--text-primary)', marginTop: '1rem' }}>
        Försök igen
      </button>
    </main>
  );

  const regime = REGIME_LABELS[portfolio.regime] || REGIME_LABELS.neutral;

  // Pie chart data
  const pieData = [
    ...portfolio.core.map(c => ({
      name: c.name, value: c.weight, fill: LAYER_COLORS.CORE,
    })),
    ...portfolio.satellites.map(s => ({
      name: s.name, value: s.weight, fill: LAYER_COLORS.SATELLITE,
    })),
    { name: 'Kassa', value: portfolio.cash_pct, fill: LAYER_COLORS.CASH },
  ].filter(d => d.value > 0);

  return (
    <main className="container" style={{ paddingTop: '2rem', paddingBottom: '6rem' }}>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <Briefcase size={28} color="var(--accent-purple)" />
          <div>
            <h2 style={{ margin: 0, fontSize: '1.6rem' }}>Core-Satellite Portfölj</h2>
            <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>
              3-lagers intelligent allokering · {portfolio.broker || 'Avanza'}
            </p>
          </div>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          style={{
            display: 'flex', alignItems: 'center', gap: '0.5rem',
            padding: '0.5rem 1rem', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.1)',
            background: 'rgba(255,255,255,0.05)', color: 'var(--text-secondary)',
            cursor: 'pointer', fontSize: '0.8rem',
          }}
        >
          <RefreshCw size={14} className={refreshing ? 'spin' : ''} />
          Uppdatera
        </button>
      </div>

      {/* Regime + Conviction bar */}
      <div className="glass-panel" style={{
        padding: '1rem 1.25rem', marginBottom: '1.5rem', display: 'flex',
        alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem',
        borderLeft: `3px solid ${regime.color}`,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span style={{ fontSize: '1.2rem' }}>{regime.icon}</span>
          <div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Marknadsregim</div>
            <div style={{ fontSize: '1.1rem', fontWeight: 700, color: regime.color }}>{regime.label}</div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '2rem', alignItems: 'center' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)' }}>Conviction</div>
            <div style={{ fontSize: '1.1rem', fontWeight: 700, color: portfolio.conviction > 0.6 ? '#10b981' : '#f59e0b' }}>
              {(portfolio.conviction * 100).toFixed(0)}%
            </div>
          </div>
          {portfolio.trailing_stop_active && (
            <div style={{
              padding: '0.3rem 0.75rem', borderRadius: '6px',
              background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)',
              fontSize: '0.7rem', fontWeight: 600, color: '#ef4444',
            }}>
              ⚠️ TRAILING STOP AKTIV
            </div>
          )}
          {portfolio.tier && (
            <div style={{
              padding: '0.3rem 0.75rem', borderRadius: '6px',
              background: 'rgba(102,126,234,0.15)', border: '1px solid rgba(102,126,234,0.3)',
              fontSize: '0.7rem', color: '#667eea',
            }}>
              {typeof portfolio.tier === 'string' ? portfolio.tier : (portfolio.tier as any)?.name || 'Premium'}
            </div>
          )}
        </div>
      </div>

      {/* Layer summary cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem', marginBottom: '1.5rem' }}>
        <LayerCard
          icon={<Shield size={20} />}
          label="KÄRNA"
          pct={portfolio.core_total_pct}
          count={portfolio.core.length}
          color={LAYER_COLORS.CORE}
          description="Strategiska positioner"
        />
        <LayerCard
          icon={<Zap size={20} />}
          label="SATELLIT"
          pct={portfolio.satellite_total_pct}
          count={portfolio.satellites.length}
          color={LAYER_COLORS.SATELLITE}
          description="AI-valda taktiska"
        />
        <LayerCard
          icon={<Wallet size={20} />}
          label="KASSA"
          pct={portfolio.cash_pct}
          count={1}
          color={LAYER_COLORS.CASH}
          description="Säkerhetsbuffert"
        />
      </div>

      {/* Main grid: Pie + Positions */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', gap: '1.5rem', marginBottom: '1.5rem' }}>

        {/* Pie Chart */}
        <div className="glass-panel" style={{ padding: '1.5rem' }}>
          <h3 style={{ margin: '0 0 0.5rem', fontSize: '1rem' }}>Tillgångsfördelning</h3>
          <div style={{ height: '280px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData} cx="50%" cy="50%"
                  innerRadius={65} outerRadius={110}
                  paddingAngle={2} dataKey="value" stroke="none"
                >
                  {pieData.map((entry, i) => (
                    <Cell key={i} fill={entry.fill} opacity={0.85} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value: any) => `${value}%`}
                  contentStyle={{
                    backgroundColor: '#13141f', borderColor: 'rgba(255,255,255,0.08)',
                    borderRadius: '8px', color: '#f8f9fa', fontSize: '0.8rem',
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          {/* Legend */}
          <div style={{ display: 'flex', justifyContent: 'center', gap: '1.5rem', marginTop: '0.5rem' }}>
            {Object.entries(LAYER_COLORS).map(([k, c]) => (
              <div key={k} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                <div style={{ width: 10, height: 10, borderRadius: '50%', background: c }} />
                {k === 'CORE' ? 'Kärna' : k === 'SATELLITE' ? 'Satellit' : 'Kassa'}
              </div>
            ))}
          </div>
        </div>

        {/* Positions list */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>

          {/* CORE positions */}
          <div className="glass-panel" style={{ padding: '1.25rem' }}>
            <h3 style={{ margin: '0 0 0.75rem', fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Shield size={16} color={LAYER_COLORS.CORE} />
              Kärna — {portfolio.core_total_pct}%
              <span style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)', fontWeight: 400, marginLeft: 'auto' }}>
                Ändras vid regimskifte
              </span>
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {portfolio.core.map(pos => (
                <PositionRow key={pos.asset_id} pos={pos} color={LAYER_COLORS.CORE} />
              ))}
            </div>
          </div>

          {/* SATELLITE positions */}
          <div className="glass-panel" style={{ padding: '1.25rem' }}>
            <h3 style={{ margin: '0 0 0.75rem', fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Zap size={16} color={LAYER_COLORS.SATELLITE} />
              Satelliter — {portfolio.satellite_total_pct}%
              <span style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)', fontWeight: 400, marginLeft: 'auto' }}>
                AI-roterade baserat på signaler
              </span>
            </h3>
            {portfolio.satellites.length === 0 ? (
              <p style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)', margin: '0.5rem 0' }}>
                Inga satelliter aktiverade — otillräcklig conviction eller regim
              </p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {portfolio.satellites.map(sat => (
                  <SatelliteRow key={sat.asset_id} sat={sat} />
                ))}
              </div>
            )}
          </div>

          {/* CASH */}
          <div className="glass-panel" style={{
            padding: '1rem 1.25rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            borderLeft: `3px solid ${LAYER_COLORS.CASH}`,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Wallet size={16} color={LAYER_COLORS.CASH} />
              <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>Kassa</span>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>{portfolio.cash.instrument}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
              {portfolio.cash.amount_sek && (
                <span style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>
                  {portfolio.cash.amount_sek.toLocaleString('sv-SE')} kr
                </span>
              )}
              <span style={{ fontSize: '1.2rem', fontWeight: 700, color: LAYER_COLORS.CASH }}>
                {portfolio.cash_pct}%
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Courtage info */}
      {portfolio.courtage_details && (
        <div className="glass-panel" style={{
          padding: '1rem 1.25rem', marginBottom: '1.5rem',
          background: 'rgba(102,126,234,0.05)', borderLeft: '3px solid rgba(102,126,234,0.3)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Info size={14} color="#667eea" />
              <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#667eea' }}>Courtage-estimat ({portfolio.broker || 'Avanza'})</span>
            </div>
            <div style={{ display: 'flex', gap: '2rem', fontSize: '0.8rem' }}>
              <span style={{ color: 'var(--text-tertiary)' }}>
                Courtage: <b style={{ color: 'var(--text-primary)' }}>{portfolio.courtage_details.total_courtage_sek?.toFixed(0)} kr</b>
              </span>
              <span style={{ color: 'var(--text-tertiary)' }}>
                Valutaväxling: <b style={{ color: 'var(--text-primary)' }}>{portfolio.courtage_details.total_fx_fee_sek?.toFixed(0)} kr</b>
              </span>
              <span style={{ color: 'var(--text-tertiary)' }}>
                Totalt: <b style={{ color: '#667eea' }}>{portfolio.courtage_details.total_cost_sek?.toFixed(0)} kr</b>
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Suggested trades */}
      {portfolio.suggested_trades && portfolio.suggested_trades.length > 0 && (
        <div className="glass-panel" style={{ padding: '1.25rem', marginBottom: '1.5rem' }}>
          <h3 style={{ margin: '0 0 0.75rem', fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <RefreshCw size={16} color="var(--accent-cyan)" />
            Föreslagna Rebalanseringar
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {portfolio.suggested_trades.map((trade: any, i: number) => (
              <div key={i} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '0.6rem 0.75rem', borderRadius: '6px',
                background: trade.action === 'KÖP' ? 'rgba(16,185,129,0.08)' : 'rgba(239,68,68,0.08)',
                border: `1px solid ${trade.action === 'KÖP' ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)'}`,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  {trade.action === 'KÖP' ? <TrendingUp size={14} color="#10b981" /> : <TrendingDown size={14} color="#ef4444" />}
                  <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>{trade.asset}</span>
                  <span style={{
                    fontSize: '0.6rem', padding: '0.1rem 0.4rem', borderRadius: '3px',
                    background: trade.layer === 'CORE' ? 'rgba(102,126,234,0.2)' : 'rgba(245,158,11,0.2)',
                    color: trade.layer === 'CORE' ? '#667eea' : '#f59e0b',
                  }}>
                    {trade.layer}
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem', fontSize: '0.75rem' }}>
                  <span style={{ color: 'var(--text-tertiary)' }}>{trade.current_pct}% → {trade.target_pct}%</span>
                  <span style={{ fontWeight: 600, color: trade.action === 'KÖP' ? '#10b981' : '#ef4444' }}>
                    {trade.action} {trade.diff_pct > 0 ? '+' : ''}{trade.diff_pct}%
                  </span>
                  {trade.trade_value_sek && (
                    <span style={{ color: 'var(--text-tertiary)' }}>
                      {trade.trade_value_sek.toLocaleString('sv-SE')} kr
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

    </main>
  );
}


// ============================================================
// SUB-COMPONENTS
// ============================================================

function LayerCard({ icon, label, pct, count, color, description }: {
  icon: React.ReactNode; label: string; pct: number; count: number;
  color: string; description: string;
}) {
  return (
    <div className="glass-panel" style={{
      padding: '1.25rem', textAlign: 'center',
      borderTop: `2px solid ${color}`,
    }}>
      <div style={{ color, marginBottom: '0.3rem' }}>{icon}</div>
      <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</div>
      <div style={{ fontSize: '2rem', fontWeight: 700, color }}>{pct}%</div>
      <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>
        {count} position{count !== 1 ? 'er' : ''} · {description}
      </div>
    </div>
  );
}


function PositionRow({ pos, color }: { pos: CorePos; color: string }) {
  const icon = CATEGORY_ICONS[pos.category] || '📊';
  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      padding: '0.5rem 0.6rem', borderRadius: '6px', background: 'rgba(255,255,255,0.02)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <span style={{ fontSize: '0.9rem' }}>{icon}</span>
        <div>
          <div style={{ fontSize: '0.82rem', fontWeight: 600 }}>{pos.name}</div>
          <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)' }}>
            {pos.instrument}
            {pos.courtage_pct === 0 && (
              <span style={{ color: '#10b981', marginLeft: '0.4rem' }}>0 kr courtage</span>
            )}
          </div>
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        {pos.amount_sek && (
          <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>
            {pos.amount_sek.toLocaleString('sv-SE')} kr
          </span>
        )}
        <span style={{ fontSize: '1.1rem', fontWeight: 700, color, minWidth: '3rem', textAlign: 'right' }}>
          {pos.weight}%
        </span>
      </div>
    </div>
  );
}


function SatelliteRow({ sat }: { sat: SatPos }) {
  const icon = CATEGORY_ICONS[sat.category] || '🎯';
  const scoreColor = sat.score > 0 ? '#10b981' : '#ef4444';
  return (
    <div style={{
      padding: '0.6rem 0.75rem', borderRadius: '6px',
      background: 'rgba(245,158,11,0.04)', border: '1px solid rgba(245,158,11,0.12)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.3rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontSize: '0.9rem' }}>{icon}</span>
          <span style={{ fontSize: '0.82rem', fontWeight: 600 }}>{sat.name}</span>
          <span style={{
            fontSize: '0.6rem', padding: '0.1rem 0.3rem', borderRadius: '3px',
            background: sat.direction === 'LONG' ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)',
            color: sat.direction === 'LONG' ? '#10b981' : '#ef4444',
          }}>
            {sat.direction}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>
            Score: <b style={{ color: scoreColor }}>{sat.score > 0 ? '+' : ''}{sat.score}</b>
          </span>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>
            Konsensus: <b>{(sat.consensus * 100).toFixed(0)}%</b>
          </span>
          {sat.amount_sek && (
            <span style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>
              {sat.amount_sek.toLocaleString('sv-SE')} kr
            </span>
          )}
          <span style={{ fontSize: '1.1rem', fontWeight: 700, color: LAYER_COLORS.SATELLITE, minWidth: '3rem', textAlign: 'right' }}>
            {sat.weight}%
          </span>
        </div>
      </div>
      <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>
        {sat.instrument} · {sat.reason}
      </div>
    </div>
  );
}
