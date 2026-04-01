import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { PieChart, TrendingDown, TrendingUp, Minus, AlertTriangle } from 'lucide-react';
import type { Asset } from '../types';

interface ScenarioChartProps {
  asset: Asset;
}

const SCENARIO_CONFIG = {
  bull: {
    label: 'Bull',
    color: '#00e676',
    gradient: 'colorBull',
    Icon: TrendingUp,
    bg: 'rgba(0, 230, 118, 0.06)',
    border: 'rgba(0, 230, 118, 0.2)',
  },
  base: {
    label: 'Bas',
    color: '#00f2fe',
    gradient: 'colorBase',
    Icon: Minus,
    bg: 'rgba(0, 242, 254, 0.06)',
    border: 'rgba(0, 242, 254, 0.2)',
  },
  bear: {
    label: 'Bear',
    color: '#ff1744',
    gradient: 'colorBear',
    Icon: TrendingDown,
    bg: 'rgba(255, 23, 68, 0.06)',
    border: 'rgba(255, 23, 68, 0.2)',
  },
} as const;

export default function ScenarioChart({ asset }: ScenarioChartProps) {
  const { scenarioData, scenarioProbabilities, scenarioNarratives, scenarioDrivers, scenarioWorstCasePct, scenarioLevel, scenarioKeyTrigger, scenarioWorstCaseCatalyst } = asset;

  const hasNarratives = !!scenarioNarratives;

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
        <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', margin: 0, fontSize: '1rem' }}>
          <PieChart size={18} color="var(--accent-purple)" /> Framtida Scenariomodellering (6 månader)
        </h3>
        {scenarioLevel && (
          <span style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)', background: 'rgba(255,255,255,0.05)', padding: '0.15rem 0.5rem', borderRadius: '6px' }}>
            Nivå {scenarioLevel}
          </span>
        )}
      </div>

      {/* Probability badges */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
        {(['bull', 'base', 'bear'] as const).map(s => (
          <span key={s} className={`badge ${s === 'bull' ? 'positive' : s === 'bear' ? 'negative' : 'neutral'}`}>
            {SCENARIO_CONFIG[s].label}: {scenarioProbabilities[s]}%
          </span>
        ))}
      </div>

      {/* Price path chart */}
      <div style={{ height: '240px', width: '100%', marginBottom: '1.5rem' }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={scenarioData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
            <defs>
              {(['bull', 'base', 'bear'] as const).map(s => (
                <linearGradient key={s} id={SCENARIO_CONFIG[s].gradient} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={SCENARIO_CONFIG[s].color} stopOpacity={0.3} />
                  <stop offset="95%" stopColor={SCENARIO_CONFIG[s].color} stopOpacity={0} />
                </linearGradient>
              ))}
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
            <XAxis dataKey="name" stroke="#6c757d" fontSize={11} tickLine={false} axisLine={false} />
            <YAxis stroke="#6c757d" fontSize={10} tickLine={false} axisLine={false} width={55}
              tickFormatter={v => v > 1000 ? `${(v/1000).toFixed(0)}k` : v > 1 ? v.toFixed(0) : v.toFixed(3)} />
            <Tooltip
              contentStyle={{ backgroundColor: '#13141f', borderColor: 'rgba(255,255,255,0.08)', borderRadius: '8px', color: '#f8f9fa' }}
              itemStyle={{ fontSize: '0.8rem' }}
            />
            {(['bull', 'base', 'bear'] as const).map(s => (
              <Area
                key={s}
                type="monotone"
                dataKey={s}
                name={`${SCENARIO_CONFIG[s].label} (${scenarioProbabilities[s]}%)`}
                stroke={SCENARIO_CONFIG[s].color}
                fillOpacity={1}
                fill={`url(#${SCENARIO_CONFIG[s].gradient})`}
                strokeWidth={2}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Narrative cards — only shown when live data is available */}
      {hasNarratives && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginBottom: '1rem' }}>
          {(['bull', 'base', 'bear'] as const).map(scenario => {
            const cfg = SCENARIO_CONFIG[scenario];
            const Icon = cfg.Icon;
            const narrative = scenarioNarratives[scenario];
            const drivers = scenarioDrivers?.[scenario] ?? [];

            return (
              <div
                key={scenario}
                style={{
                  background: cfg.bg,
                  border: `1px solid ${cfg.border}`,
                  borderRadius: '10px',
                  padding: '0.85rem',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem', marginBottom: '0.4rem' }}>
                  <Icon size={15} color={cfg.color} style={{ marginTop: '2px', flexShrink: 0 }} />
                  <div>
                    <span style={{ color: cfg.color, fontWeight: 600, fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                      {cfg.label} — {scenarioProbabilities[scenario]}%
                    </span>
                    <p style={{ margin: '0.25rem 0 0', color: 'var(--text-secondary)', fontSize: '0.82rem', lineHeight: 1.5 }}>
                      {narrative}
                    </p>
                  </div>
                </div>

                {drivers.length > 0 && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem', marginTop: '0.4rem', paddingLeft: '1.4rem' }}>
                    {drivers.map((d, i) => (
                      <span
                        key={i}
                        style={{
                          fontSize: '0.7rem',
                          color: 'var(--text-tertiary)',
                          background: 'rgba(255,255,255,0.05)',
                          borderRadius: '6px',
                          padding: '0.15rem 0.45rem',
                        }}
                      >
                        {d}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Key Trigger + Worst-case Catalyst */}
      {(scenarioKeyTrigger || scenarioWorstCaseCatalyst) && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', marginBottom: '0.75rem' }}>
          {scenarioKeyTrigger && (
            <div style={{
              display: 'flex', alignItems: 'flex-start', gap: '0.5rem',
              padding: '0.55rem 0.75rem',
              background: 'rgba(0,230,118,0.05)',
              border: '1px solid rgba(0,230,118,0.15)',
              borderRadius: '8px', fontSize: '0.78rem',
            }}>
              <span style={{ color: '#00e676', fontWeight: 700, flexShrink: 0 }}>🔑</span>
              <span style={{ color: 'var(--text-secondary)' }}>
                <strong style={{ color: '#00e676' }}>Bull-trigger:</strong> {scenarioKeyTrigger}
              </span>
            </div>
          )}
          {scenarioWorstCaseCatalyst && (
            <div style={{
              display: 'flex', alignItems: 'flex-start', gap: '0.5rem',
              padding: '0.55rem 0.75rem',
              background: 'rgba(255,23,68,0.05)',
              border: '1px solid rgba(255,23,68,0.15)',
              borderRadius: '8px', fontSize: '0.78rem',
            }}>
              <span style={{ color: '#ff1744', fontWeight: 700, flexShrink: 0 }}>⚡</span>
              <span style={{ color: 'var(--text-secondary)' }}>
                <strong style={{ color: '#ff1744' }}>Bear-katalysator:</strong> {scenarioWorstCaseCatalyst}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Worst-case historical info */}
      {scenarioWorstCasePct !== undefined && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: '0.5rem',
          padding: '0.6rem 0.85rem',
          background: 'rgba(255, 23, 68, 0.05)',
          border: '1px solid rgba(255, 23, 68, 0.15)',
          borderRadius: '8px',
          fontSize: '0.78rem',
        }}>
          <AlertTriangle size={13} color="#ff1744" />
          <span style={{ color: 'var(--text-tertiary)' }}>
            Historiskt värsta utfall (2 år):{'  '}
            <span style={{ color: '#ff1744', fontWeight: 600 }}>
              {scenarioWorstCasePct.toFixed(0)}%
            </span>
          </span>
        </div>
      )}

      {/* Note when using mock data */}
      {!hasNarratives && (
        <p style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', textAlign: 'center', margin: '0.5rem 0 0' }}>
          Scenarioanalys genereras vid nästa analyscykel
        </p>
      )}
    </div>
  );
}
