import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, Search, Plus, Trash2, BarChart2, Briefcase, Camera, ArrowRight } from 'lucide-react';
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { API_BASE } from '../api/client';
import CoreSatellitePanel from './PortfolioPage';

type ActiveTab = 'ai' | 'my';

export default function MyPortfolioPage() {
  const [activeSection, setActiveSection] = useState<ActiveTab>('ai');

  return (
    <main className="container" style={{ padding: '1.5rem 1.25rem 6rem' }}>
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        style={{ marginBottom: '1.5rem' }}
      >
        <h1 style={{ fontSize: '1.8rem', marginBottom: '0.25rem' }}>
          <span className="text-gradient">Portfölj</span>
        </h1>
        <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
          AI-rekommenderad allokering & jämför med dina egna innehav
        </p>
      </motion.div>

      {/* Section Tabs */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem' }}>
        {[
          { id: 'ai' as const, label: '📊 AI-Portfölj', desc: 'Core-Satellite rekommendation' },
          { id: 'my' as const, label: '💼 Min Portfölj', desc: 'Jämför med AI' },
        ].map(tab => (
          <button key={tab.id} onClick={() => setActiveSection(tab.id)} style={{
            flex: 1, padding: '0.85rem 1rem', borderRadius: '10px', cursor: 'pointer',
            background: activeSection === tab.id
              ? 'linear-gradient(135deg, rgba(79, 172, 254, 0.1), rgba(157, 78, 221, 0.1))'
              : 'rgba(255,255,255,0.03)',
            border: `1px solid ${activeSection === tab.id ? 'rgba(79, 172, 254, 0.3)' : 'var(--glass-border)'}`,
            color: activeSection === tab.id ? 'var(--text-primary)' : 'var(--text-secondary)',
            fontSize: '0.9rem', fontWeight: activeSection === tab.id ? 600 : 400,
            transition: 'all 0.2s', textAlign: 'left',
            fontFamily: 'var(--font-body)',
          }}>
            <div>{tab.label}</div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', marginTop: '0.15rem' }}>{tab.desc}</div>
          </button>
        ))}
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={activeSection}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.2 }}
        >
          {activeSection === 'ai' && <CoreSatellitePanel />}
          {activeSection === 'my' && <MyHoldingsPanel />}
        </motion.div>
      </AnimatePresence>
    </main>
  );
}

/* ── Local Types ── */
interface SearchResult {
  name: string;
  ticker: string;
  currency?: string;
  price?: number;
}

interface PortfolioComparison {
  ai_score: number;
  user_score: number;
  overlap_pct: number;
  suggestions: string[];
  analysis: string;
}

interface FrontierData {
  frontier: Array<{ risk: number; return: number }>;
  efficient: Array<{ risk: number; return: number }>;
  user_position?: { risk: number; return: number };
}

/* ── My Holdings Panel ── */
function MyHoldingsPanel() {
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [comparing, setComparing] = useState(false);
  const [comparison, setComparison] = useState<PortfolioComparison | null>(null);
  const [frontier, setFrontier] = useState<FrontierData | null>(null);
  const [parsing, setParsing] = useState(false);
  const [dragOver, setDragOver] = useState(false);

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

  useEffect(() => {
    const timer = setTimeout(() => doSearch(searchQuery), 500);
    return () => clearTimeout(timer);
  }, [searchQuery, doSearch]);

  const addHolding = (result: SearchResult) => {
    setHoldings(prev => [...prev, {
      name: result.name, ticker: result.ticker, value: 0, weight_pct: 0,
      currency: result.currency, current_price: result.price,
    }]);
    setSearchQuery('');
    setSearchResults([]);
  };

  const addManual = () => {
    setHoldings(prev => [...prev, { name: '', ticker: null, value: 0, weight_pct: 0 }]);
  };

  const updateHolding = (idx: number, field: string, value: string | number) => {
    setHoldings(prev => prev.map((h, i) => i === idx ? { ...h, [field]: value } : h));
  };

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
      if (data.holdings?.length > 0) setHoldings(data.holdings);
    } catch (e) {
      console.error('Image parse failed:', e);
    }
    setParsing(false);
  };

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) parseImage(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) parseImage(file);
  };

  const doCompare = async () => {
    setComparing(true);
    try {
      const res = await fetch(`${API_BASE}/api/user-portfolio/compare`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ holdings }),
      });
      const data = await res.json();
      setComparison(data.comparison);
      setFrontier(data.frontier);
      if (data.user_holdings) setHoldings(data.user_holdings);
    } catch (e) {
      console.error('Compare failed:', e);
    }
    setComparing(false);
  };

  const totalValue = holdings.reduce((s, h) => s + (h.value || 0), 0);

  return (
    <div>
      {/* Image Upload Zone */}
      <div
        className="glass-panel"
        onDrop={handleDrop}
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        style={{
          padding: '2rem', marginBottom: '1.5rem', textAlign: 'center',
          border: `2px dashed ${dragOver ? 'var(--accent-cyan)' : 'rgba(255,255,255,0.1)'}`,
          background: dragOver ? 'rgba(0, 242, 254, 0.05)' : 'rgba(255,255,255,0.02)',
          cursor: 'pointer', transition: 'all 0.2s',
        }}
        onClick={() => document.getElementById('portfolio-image-input')?.click()}
      >
        <input id="portfolio-image-input" type="file" accept="image/*" onChange={handleFile} style={{ display: 'none' }} />
        {parsing ? (
          <div style={{ color: 'var(--accent-cyan)' }}>
            <Camera size={32} style={{ margin: '0 auto 0.5rem', display: 'block' }} className="spin-animation" />
            <p style={{ margin: 0, fontSize: '0.9rem' }}>AI analyserar din portföljbild...</p>
          </div>
        ) : (
          <>
            <Upload size={32} style={{ color: 'var(--text-tertiary)', margin: '0 auto 0.5rem', display: 'block' }} />
            <p style={{ margin: 0, fontSize: '0.95rem', color: 'var(--text-secondary)' }}>
              📸 Dra & släpp en skärmdump från Avanza/Nordnet
            </p>
            <p style={{ margin: '0.25rem 0 0', fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>
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
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Sök aktie eller fond (t.ex. AAPL, SEB, Avanza Zero)..."
              style={{
                width: '100%', padding: '0.6rem 0.75rem 0.6rem 2rem',
                background: 'rgba(255,255,255,0.05)', border: '1px solid var(--glass-border)',
                borderRadius: '8px', color: 'var(--text-primary)', fontSize: '0.85rem', outline: 'none',
                fontFamily: 'var(--font-body)',
              }}
            />
          </div>
          <button onClick={addManual} style={{
            padding: '0.6rem 1rem', background: 'rgba(79,172,254,0.1)',
            border: '1px solid rgba(79,172,254,0.3)', borderRadius: '8px',
            color: 'var(--accent-cyan)', cursor: 'pointer', fontSize: '0.8rem',
            display: 'flex', alignItems: 'center', gap: '0.3rem',
            fontFamily: 'var(--font-body)',
          }}>
            <Plus size={14} /> Manuell
          </button>
        </div>

        {searchResults.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
            {searchResults.map((r, i) => (
              <div key={i} onClick={() => addHolding(r)} style={{
                padding: '0.5rem 0.75rem', borderRadius: '6px',
                background: 'rgba(255,255,255,0.03)', cursor: 'pointer',
                border: '1px solid rgba(255,255,255,0.05)',
                display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8rem',
              }}>
                <div>
                  <span style={{ fontWeight: 600 }}>{r.ticker}</span>
                  <span style={{ color: 'var(--text-secondary)', marginLeft: '0.5rem' }}>{r.name}</span>
                </div>
                <span style={{ color: 'var(--accent-cyan)' }}>{r.price} {r.currency}</span>
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
                <input type="text" value={h.name} placeholder="Namn"
                  onChange={e => updateHolding(idx, 'name', e.target.value)}
                  style={{ flex: 2, padding: '0.4rem 0.5rem', background: 'transparent', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '4px', color: 'var(--text-primary)', fontSize: '0.8rem' }}
                />
                <input type="text" value={h.ticker || ''} placeholder="Ticker"
                  onChange={e => updateHolding(idx, 'ticker', e.target.value)}
                  style={{ width: '80px', padding: '0.4rem 0.5rem', background: 'transparent', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '4px', color: 'var(--accent-cyan)', fontSize: '0.8rem', fontFamily: 'monospace' }}
                />
                <input type="number" value={h.value || ''} placeholder="Värde (kr)"
                  onChange={e => updateHolding(idx, 'value', parseFloat(e.target.value) || 0)}
                  style={{ width: '100px', padding: '0.4rem 0.5rem', background: 'transparent', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '4px', color: 'var(--text-primary)', fontSize: '0.8rem' }}
                />
                <button onClick={() => removeHolding(idx)} style={{
                  background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-tertiary)', padding: '0.25rem',
                }}>
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>

          {/* Compare Button */}
          <button onClick={doCompare} disabled={comparing || holdings.length === 0} className="button-primary" style={{
            marginTop: '1rem', width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem',
            opacity: comparing ? 0.6 : 1,
          }}>
            {comparing ? 'Analyserar...' : <><BarChart2 size={16} /> Jämför med AI-portföljen <ArrowRight size={14} /></>}
          </button>
        </div>
      )}

      {/* Comparison Results */}
      {comparison && (
        <div className="glass-panel" style={{ padding: '1.25rem', marginBottom: '1.5rem' }}>
          <h3 style={{ margin: '0 0 1rem', fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <BarChart2 size={18} style={{ color: 'var(--accent-cyan)' }} />
            Din Portfölj vs AI
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
            <ComparisonCard label="DIN PORTFÖLJ" color="var(--accent-purple)"
              holdings={comparison.user_holdings_count}
              vol={comparison.user_volatility_annual}
              diversification={comparison.diversification_score}
            />
            <ComparisonCard label="AI-PORTFÖLJ" color="var(--accent-cyan)"
              holdings={comparison.ai_holdings_count}
              overlap={comparison.overlap_count}
            />
          </div>

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
        </div>
      )}

      {/* Efficient Frontier Chart */}
      {frontier && frontier.frontier?.length > 0 && (
        <div className="glass-panel" style={{ padding: '1.25rem' }}>
          <h4 style={{ margin: '0 0 0.75rem', fontSize: '0.95rem' }}>📈 Effektiv Front (Risk vs Avkastning)</h4>
          <div style={{ background: 'rgba(0,0,0,0.2)', borderRadius: '10px', padding: '1rem 0.5rem 0.5rem', border: '1px solid rgba(255,255,255,0.05)' }}>
            <ResponsiveContainer width="100%" height={300}>
              <ScatterChart margin={{ top: 10, right: 30, bottom: 20, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                <XAxis type="number" dataKey="risk" name="Risk"
                  label={{ value: 'Risk (%/år)', position: 'bottom', offset: 0, fill: 'var(--text-tertiary)', fontSize: 11 }}
                  tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }} stroke="rgba(255,255,255,0.1)"
                />
                <YAxis type="number" dataKey="return" name="Avkastning"
                  label={{ value: 'Avk (%/år)', angle: -90, position: 'insideLeft', fill: 'var(--text-tertiary)', fontSize: 11 }}
                  tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }} stroke="rgba(255,255,255,0.1)"
                />
                <Tooltip content={({ active, payload }: { active?: boolean; payload?: Array<{ payload: { risk: number; return: number } }> }) => {
                  if (!active || !payload?.length) return null;
                  const d = payload[0]?.payload;
                  return (
                    <div style={{ background: 'rgba(15,15,25,0.95)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', padding: '0.5rem', fontSize: '0.75rem' }}>
                      {d?.label && <div style={{ fontWeight: 600, marginBottom: '0.2rem' }}>{d.label}</div>}
                      <div style={{ color: '#ef4444' }}>Risk: {Number(d?.risk).toFixed(1)}%</div>
                      <div style={{ color: '#10b981' }}>Avk: {Number(d?.return).toFixed(1)}%</div>
                    </div>
                  );
                }} />
                <Scatter name="Möjliga" data={frontier.frontier} fill="rgba(255,255,255,0.12)">
                  {frontier.frontier.map((_: { risk: number; return: number }, i: number) => <Cell key={i} fill="rgba(255,255,255,0.12)" r={2} />)}
                </Scatter>
                {frontier.efficient?.length > 0 && (
                  <Scatter name="Effektiv front" data={frontier.efficient} fill="var(--accent-cyan)" line={{ stroke: 'var(--accent-cyan)', strokeWidth: 2 }} lineType="fitting">
                    {frontier.efficient.map((_: { risk: number; return: number }, i: number) => <Cell key={i} fill="var(--accent-cyan)" r={3} />)}
                  </Scatter>
                )}
                {frontier.user_position && (
                  <Scatter name="Din portfölj" data={[frontier.user_position]} fill="var(--accent-purple)">
                    <Cell fill="var(--accent-purple)" r={8} />
                  </Scatter>
                )}
                {frontier.ai_position && (
                  <Scatter name="AI-portfölj" data={[frontier.ai_position]} fill="var(--score-positive)">
                    <Cell fill="var(--score-positive)" r={8} />
                  </Scatter>
                )}
              </ScatterChart>
            </ResponsiveContainer>
          </div>
          <div style={{ display: 'flex', justifyContent: 'center', gap: '1.5rem', marginTop: '0.5rem', flexWrap: 'wrap', fontSize: '0.7rem' }}>
            <Legend color="var(--accent-purple)" label="Din Portfölj" />
            <Legend color="var(--score-positive)" label="AI-Portfölj" />
            <Legend color="var(--accent-cyan)" label="Effektiv front" />
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Sub-components ── */

interface Holding {
  name: string;
  ticker: string | null;
  value: number;
  weight_pct: number;
  currency?: string;
  current_price?: number;
  change_pct?: number;
}

function ComparisonCard({ label, color, holdings, vol, diversification, overlap }: {
  label: string; color: string; holdings: number;
  vol?: number; diversification?: number; overlap?: number;
}) {
  return (
    <div style={{ padding: '1rem', borderRadius: '8px', background: `${color}08`, border: `1px solid ${color}20` }}>
      <div style={{ fontSize: '0.7rem', color, marginBottom: '0.5rem', fontWeight: 700 }}>{label}</div>
      <div style={{ fontSize: '1.2rem', fontWeight: 700 }}>{holdings} innehav</div>
      {vol != null && vol > 0 && <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Vol: {vol}%/år</div>}
      {diversification != null && <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Diversifiering: {diversification}/100</div>}
      {overlap != null && <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Överlapp: {overlap} tillgångar</div>}
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
      <div style={{ width: 10, height: 10, borderRadius: '50%', background: color }} />
      {label}
    </div>
  );
}
