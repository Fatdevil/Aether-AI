import { useState } from 'react';
import { Globe2, TrendingUp, TrendingDown, Minus, ChevronDown, ChevronUp, Info, MapPin } from 'lucide-react';
import type { APIRegion } from '../api/client';
import { getScoreColor, scoreToPercent } from '../types';

interface RegionsPageProps {
  regions: APIRegion[];
}

export default function RegionsPage({ regions }: RegionsPageProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const overweight = regions.filter(r => r.allocationSignal === 'Övervikt');
  const neutral = regions.filter(r => r.allocationSignal === 'Neutralvikt');
  const underweight = regions.filter(r => r.allocationSignal === 'Undervikt');

  const getSignalBadge = (signal: string) => {
    switch (signal) {
      case 'Övervikt':
        return <span className="badge positive" style={{ fontSize: '0.75rem' }}>
          <TrendingUp size={12} /> Övervikt
        </span>;
      case 'Undervikt':
        return <span className="badge negative" style={{ fontSize: '0.75rem' }}>
          <TrendingDown size={12} /> Undervikt
        </span>;
      default:
        return <span className="badge" style={{ fontSize: '0.75rem' }}>
          <Minus size={12} /> Neutralvikt
        </span>;
    }
  };

  if (regions.length === 0) {
    return (
      <main className="container" style={{ paddingTop: '2rem', paddingBottom: '6rem' }}>
        <div className="glass-panel" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-tertiary)' }}>
          <Globe2 size={48} style={{ marginBottom: '1rem', opacity: 0.5 }} />
          <p>Regiondata laddas... Starta backend för realtidsdata.</p>
        </div>
      </main>
    );
  }

  return (
    <main className="container" style={{ paddingTop: '2rem', paddingBottom: '6rem' }}>

      {/* Header */}
      <div className="flex items-center gap-2" style={{ marginBottom: '0.5rem' }}>
        <Globe2 size={28} color="var(--accent-cyan)" />
        <h2 style={{ margin: 0, fontSize: '1.8rem' }}>Geografiska Marknader</h2>
      </div>
      <p style={{ color: 'var(--text-tertiary)', marginBottom: '2rem', fontSize: '0.9rem' }}>
        AI analyserar 8 globala regioner baserat på makrofaktorer, centralbankspolitik, geopolitik och tillväxtutsikter.
      </p>

      {/* World Map Bar */}
      <div className="glass-panel" style={{ padding: '1.5rem', marginBottom: '2rem' }}>
        <h3 style={{ marginBottom: '1rem', fontSize: '1.1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <MapPin size={16} /> Regional Heatmap
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))', gap: '8px' }}>
          {regions.map(region => {
            const colorClass = getScoreColor(region.score);
            return (
              <div
                key={region.id}
                onClick={() => setExpandedId(expandedId === region.id ? null : region.id)}
                style={{
                  padding: '0.75rem',
                  borderRadius: '12px',
                  background: `${region.color}${Math.min(40, 15 + Math.abs(region.score) * 3).toString(16).padStart(2, '0')}`,
                  border: `1px solid ${region.color}40`,
                  cursor: 'pointer',
                  textAlign: 'center',
                  transition: 'all 0.2s ease',
                  transform: expandedId === region.id ? 'scale(1.05)' : 'scale(1)',
                }}
              >
                <div style={{ fontSize: '1.5rem', marginBottom: '0.25rem' }}>{region.flag}</div>
                <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                  {region.name}
                </div>
                <div style={{
                  fontSize: '1.1rem', fontWeight: 700,
                  color: `var(--score-${colorClass})`,
                  marginTop: '0.2rem',
                }}>
                  {region.score > 0 ? '+' : ''}{region.score}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Summary */}
      <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
        <div className="glass-panel" style={{
          padding: '1.5rem', textAlign: 'center',
          borderLeft: '3px solid var(--score-positive)',
        }}>
          <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--score-positive)' }}>
            {overweight.length}
          </div>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>Övervikt</div>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.3rem' }}>
            {overweight.map(r => r.flag).join(' ') || '—'}
          </div>
        </div>
        <div className="glass-panel" style={{
          padding: '1.5rem', textAlign: 'center',
          borderLeft: '3px solid var(--score-neutral)',
        }}>
          <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--score-neutral)' }}>
            {neutral.length}
          </div>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>Neutralvikt</div>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.3rem' }}>
            {neutral.map(r => r.flag).join(' ') || '—'}
          </div>
        </div>
        <div className="glass-panel" style={{
          padding: '1.5rem', textAlign: 'center',
          borderLeft: '3px solid var(--score-negative)',
        }}>
          <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--score-negative)' }}>
            {underweight.length}
          </div>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>Undervikt</div>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.3rem' }}>
            {underweight.map(r => r.flag).join(' ') || '—'}
          </div>
        </div>
      </div>

      {/* Region Cards */}
      <div className="flex flex-col gap-4">
        {regions.map((region, index) => {
          const isExpanded = expandedId === region.id;
          const colorClass = getScoreColor(region.score);

          return (
            <div
              key={region.id}
              className="glass-panel animate-fade-in"
              style={{
                padding: 0,
                animationDelay: `${index * 0.05}s`,
                border: isExpanded ? `1px solid ${region.color}` : undefined,
                overflow: 'hidden',
              }}
            >
              {/* Main row */}
              <div
                onClick={() => setExpandedId(isExpanded ? null : region.id)}
                style={{
                  padding: '1.25rem 1.5rem',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '1rem',
                }}
              >
                <div className="flex items-center gap-4" style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontSize: '2.2rem', width: '52px', height: '52px',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    borderRadius: '12px',
                    background: `${region.color}15`,
                    border: `1px solid ${region.color}30`,
                    flexShrink: 0,
                  }}>
                    {region.flag}
                  </div>
                  <div style={{ minWidth: 0 }}>
                    <h4 style={{ margin: 0, fontSize: '1.1rem' }}>{region.name}</h4>
                    <div className="flex items-center gap-2" style={{ marginTop: '0.2rem', flexWrap: 'wrap' }}>
                      <span style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>
                        {region.ticker} • {region.indexName}
                      </span>
                      {region.price > 0 && (
                        <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                          ${region.price.toFixed(2)}
                          <span style={{
                            color: region.changePct >= 0 ? 'var(--score-positive)' : 'var(--score-negative)',
                            marginLeft: '0.3rem',
                          }}>
                            ({region.changePct >= 0 ? '+' : ''}{region.changePct.toFixed(2)}%)
                          </span>
                        </span>
                      )}
                      {getSignalBadge(region.allocationSignal)}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-4">
                  <div style={{ textAlign: 'right' }}>
                    <div style={{
                      fontSize: '1.8rem', fontWeight: 700,
                      color: `var(--score-${colorClass})`,
                      lineHeight: 1,
                    }}>
                      {region.score > 0 ? '+' : ''}{region.score}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>AI Poäng</div>
                  </div>
                  {isExpanded ? <ChevronUp size={20} color="var(--text-tertiary)" /> : <ChevronDown size={20} color="var(--text-tertiary)" />}
                </div>
              </div>

              {/* Expanded details */}
              {isExpanded && (
                <div style={{
                  padding: '0 1.5rem 1.5rem',
                  borderTop: '1px solid var(--glass-border)',
                }}>
                  <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem', marginTop: '1rem' }}>
                    {/* AI Reasoning */}
                    <div className="glass-panel" style={{ padding: '1.25rem', background: 'rgba(255,255,255,0.02)' }}>
                      <h5 style={{ margin: '0 0 0.75rem', color: 'var(--accent-cyan)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <Info size={14} /> AI Regionanalys
                      </h5>
                      <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.7, margin: '0 0 1rem' }}>
                        "{region.reasoning}"
                      </p>
                      <div className="score-progress" style={{ marginBottom: '0.5rem' }}>
                        <div className={`score-progress-bar ${colorClass}`} style={{ width: scoreToPercent(region.score) }} />
                      </div>
                      <div className="flex justify-between" style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>
                        <span>-10 Undvik</span>
                        <span>0 Neutral</span>
                        <span>+10 Stark köp</span>
                      </div>
                    </div>

                    {/* Region Details */}
                    <div className="glass-panel" style={{ padding: '1.25rem', background: 'rgba(255,255,255,0.02)' }}>
                      <h5 style={{ margin: '0 0 0.75rem' }}>Regionprofil</h5>
                      <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', margin: '0 0 0.75rem' }}>
                        {region.description}
                      </p>
                      <h5 style={{ margin: '0 0 0.5rem', fontSize: '0.85rem' }}>Makro-Drivers</h5>
                      <div className="flex" style={{ gap: '0.4rem', flexWrap: 'wrap' }}>
                        {region.macroDrivers.map((driver, i) => (
                          <span key={i} className="badge" style={{
                            fontSize: '0.7rem', padding: '0.2rem 0.5rem',
                            background: `${region.color}15`,
                            border: `1px solid ${region.color}30`,
                            color: region.color,
                          }}>
                            {driver}
                          </span>
                        ))}
                      </div>
                      {region.keyDrivers.length > 0 && (
                        <div style={{ marginTop: '0.75rem' }}>
                          <h5 style={{ margin: '0 0 0.5rem', fontSize: '0.85rem' }}>AI Nyckelfaktorer</h5>
                          <ul style={{ margin: 0, paddingLeft: '1.2rem', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                            {region.keyDrivers.map((f, i) => (
                              <li key={i}>{f}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </main>
  );
}
