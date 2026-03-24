import { useState } from 'react';
import { Factory, TrendingUp, TrendingDown, Minus, ChevronDown, ChevronUp, Info } from 'lucide-react';
import type { APISector } from '../api/client';
import { getScoreColor, scoreToPercent } from '../types';

interface SectorsPageProps {
  sectors: APISector[];
}

export default function SectorsPage({ sectors }: SectorsPageProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const overweight = sectors.filter(s => s.rotationSignal === 'Övervikt');
  const neutral = sectors.filter(s => s.rotationSignal === 'Neutralvikt');
  const underweight = sectors.filter(s => s.rotationSignal === 'Undervikt');

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

  if (sectors.length === 0) {
    return (
      <main className="container" style={{ paddingTop: '2rem', paddingBottom: '6rem' }}>
        <div className="glass-panel" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-tertiary)' }}>
          <Factory size={48} style={{ marginBottom: '1rem', opacity: 0.5 }} />
          <p>Sektordata laddas... Starta backend för realtidsdata.</p>
        </div>
      </main>
    );
  }

  return (
    <main className="container" style={{ paddingTop: '2rem', paddingBottom: '6rem' }}>

      {/* Header */}
      <div className="flex items-center gap-2" style={{ marginBottom: '0.5rem' }}>
        <Factory size={28} color="var(--accent-purple)" />
        <h2 style={{ margin: 0, fontSize: '1.8rem' }}>Sektorrotation & Branschanalys</h2>
      </div>
      <p style={{ color: 'var(--text-tertiary)', marginBottom: '2rem', fontSize: '0.9rem' }}>
        AI analyserar 12 sektorer baserat på makromiljö, räntor, geopolitik och nyhetssentiment.
        Överviktade sektorer har starkast makro-drivers i rådande marknadsläge.
      </p>

      {/* Summary Cards */}
      <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
        <div className="glass-panel" style={{
          padding: '1.5rem', textAlign: 'center',
          borderLeft: '3px solid var(--score-positive)',
        }}>
          <div style={{ fontSize: '2.5rem', fontWeight: 700, color: 'var(--score-positive)' }}>
            {overweight.length}
          </div>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>Övervikt</div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.3rem' }}>
            {overweight.map(s => s.emoji).join(' ')}
          </div>
        </div>
        <div className="glass-panel" style={{
          padding: '1.5rem', textAlign: 'center',
          borderLeft: '3px solid var(--score-neutral)',
        }}>
          <div style={{ fontSize: '2.5rem', fontWeight: 700, color: 'var(--score-neutral)' }}>
            {neutral.length}
          </div>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>Neutralvikt</div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.3rem' }}>
            {neutral.map(s => s.emoji).join(' ')}
          </div>
        </div>
        <div className="glass-panel" style={{
          padding: '1.5rem', textAlign: 'center',
          borderLeft: '3px solid var(--score-negative)',
        }}>
          <div style={{ fontSize: '2.5rem', fontWeight: 700, color: 'var(--score-negative)' }}>
            {underweight.length}
          </div>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>Undervikt</div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.3rem' }}>
            {underweight.map(s => s.emoji).join(' ')}
          </div>
        </div>
        <div className="glass-panel" style={{
          padding: '1.5rem', textAlign: 'center',
          borderLeft: '3px solid var(--accent-purple)',
        }}>
          <div style={{ fontSize: '2.5rem', fontWeight: 700, color: 'var(--accent-purple)' }}>
            {sectors.length}
          </div>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>Totalt analyserade</div>
        </div>
      </div>

      {/* Heatmap Bar */}
      <div className="glass-panel" style={{ padding: '1.5rem', marginBottom: '2rem' }}>
        <h3 style={{ marginBottom: '1rem', fontSize: '1.1rem' }}>Sektor-heatmap (sorterad efter AI-poäng)</h3>
        <div style={{ display: 'flex', gap: '4px', height: '60px', borderRadius: '8px', overflow: 'hidden' }}>
          {sectors.map(sector => {
            const colorClass = getScoreColor(sector.score);
            const barWidth = Math.max(4, 100 / sectors.length);
            return (
              <div
                key={sector.id}
                title={`${sector.emoji} ${sector.name}: ${sector.score > 0 ? '+' : ''}${sector.score}`}
                style={{
                  flex: `0 0 ${barWidth}%`,
                  background: `var(--score-${colorClass})`,
                  opacity: 0.2 + Math.abs(sector.score) * 0.08,
                  borderRadius: '4px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  fontSize: '1.2rem',
                }}
                onClick={() => setExpandedId(expandedId === sector.id ? null : sector.id)}
              >
                {sector.emoji}
              </div>
            );
          })}
        </div>
        <div className="flex justify-between" style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>
          <span>← Starkast</span>
          <span>Svagast →</span>
        </div>
      </div>

      {/* Sector Cards */}
      <div className="flex flex-col gap-4">
        {sectors.map((sector, index) => {
          const isExpanded = expandedId === sector.id;
          const colorClass = getScoreColor(sector.score);

          return (
            <div
              key={sector.id}
              className="glass-panel animate-fade-in"
              style={{
                padding: '0',
                animationDelay: `${index * 0.05}s`,
                border: isExpanded ? `1px solid ${sector.color}` : undefined,
                overflow: 'hidden',
              }}
            >
              {/* Main row */}
              <div
                onClick={() => setExpandedId(isExpanded ? null : sector.id)}
                style={{
                  padding: '1.25rem 1.5rem',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '1rem',
                  transition: 'background 0.2s ease',
                }}
              >
                <div className="flex items-center gap-4" style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontSize: '2rem', width: '48px', height: '48px',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    borderRadius: '12px',
                    background: `${sector.color}15`,
                    border: `1px solid ${sector.color}30`,
                    flexShrink: 0,
                  }}>
                    {sector.emoji}
                  </div>
                  <div style={{ minWidth: 0 }}>
                    <h4 style={{ margin: 0, fontSize: '1.1rem' }}>{sector.name}</h4>
                    <div className="flex items-center gap-2" style={{ marginTop: '0.2rem', flexWrap: 'wrap' }}>
                      <span style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>
                        {sector.ticker}
                      </span>
                      {sector.price > 0 && (
                        <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                          ${sector.price.toFixed(2)}
                          <span style={{
                            color: sector.changePct >= 0 ? 'var(--score-positive)' : 'var(--score-negative)',
                            marginLeft: '0.3rem',
                          }}>
                            ({sector.changePct >= 0 ? '+' : ''}{sector.changePct.toFixed(2)}%)
                          </span>
                        </span>
                      )}
                      {getSignalBadge(sector.rotationSignal)}
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
                      {sector.score > 0 ? '+' : ''}{sector.score}
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
                        <Info size={14} /> AI Sektoranalys
                      </h5>
                      <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.7, margin: '0 0 1rem' }}>
                        "{sector.reasoning}"
                      </p>
                      <div className="score-progress" style={{ marginBottom: '0.5rem' }}>
                        <div className={`score-progress-bar ${colorClass}`} style={{ width: scoreToPercent(sector.score) }} />
                      </div>
                      <div className="flex justify-between" style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>
                        <span>-10 Sälj</span>
                        <span>0 Neutral</span>
                        <span>+10 Köp</span>
                      </div>
                    </div>

                    {/* Sector Details */}
                    <div className="glass-panel" style={{ padding: '1.25rem', background: 'rgba(255,255,255,0.02)' }}>
                      <h5 style={{ margin: '0 0 0.75rem' }}>Sektorprofil</h5>
                      <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', margin: '0 0 0.75rem' }}>
                        {sector.description}
                      </p>
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)', marginBottom: '0.75rem' }}>
                        <strong>Exempel:</strong> {sector.examples}
                      </div>
                      <h5 style={{ margin: '0 0 0.5rem', fontSize: '0.85rem' }}>Makro-Drivers</h5>
                      <div className="flex" style={{ gap: '0.4rem', flexWrap: 'wrap' }}>
                        {sector.macroDrivers.map((driver, i) => (
                          <span key={i} className="badge" style={{
                            fontSize: '0.7rem', padding: '0.2rem 0.5rem',
                            background: `${sector.color}15`,
                            border: `1px solid ${sector.color}30`,
                            color: sector.color,
                          }}>
                            {driver}
                          </span>
                        ))}
                      </div>
                      {sector.keyDrivers.length > 0 && (
                        <div style={{ marginTop: '0.75rem' }}>
                          <h5 style={{ margin: '0 0 0.5rem', fontSize: '0.85rem' }}>AI Nyckelfaktorer</h5>
                          <ul style={{ margin: 0, paddingLeft: '1.2rem', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                            {sector.keyDrivers.map((f, i) => (
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
