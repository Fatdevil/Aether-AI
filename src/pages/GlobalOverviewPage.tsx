import { useState, useEffect, useCallback } from 'react';
import { Globe, Search, Filter, TrendingUp, ArrowUp, ArrowDown, Minus, Newspaper, RefreshCw } from 'lucide-react';

// Available filter options
const REGIONS = [
  { code: '', label: 'Alla regioner' },
  { code: 'us', label: '🇺🇸 USA' },
  { code: 'gb', label: '🇬🇧 UK' },
  { code: 'de', label: '🇩🇪 Tyskland' },
  { code: 'se', label: '🇸🇪 Sverige' },
  { code: 'no', label: '🇳🇴 Norge' },
  { code: 'dk', label: '🇩🇰 Danmark' },
  { code: 'fi', label: '🇫🇮 Finland' },
  { code: 'jp', label: '🇯🇵 Japan' },
  { code: 'cn', label: '🇨🇳 Kina' },
  { code: 'in', label: '🇮🇳 Indien' },
  { code: 'au', label: '🇦🇺 Australien' },
  { code: 'ca', label: '🇨🇦 Kanada' },
  { code: 'br', label: '🇧🇷 Brasilien' },
];

const INDUSTRIES = [
  { code: '', label: 'Alla sektorer' },
  { code: 'Technology', label: '💻 Teknologi' },
  { code: 'Financial', label: '🏦 Finans' },
  { code: 'Healthcare', label: '🏥 Hälsovård' },
  { code: 'Energy', label: '⚡ Energi' },
  { code: 'Consumer Cyclical', label: '🛒 Konsument' },
  { code: 'Industrials', label: '🏭 Industri' },
  { code: 'Real Estate', label: '🏠 Fastigheter' },
  { code: 'Communication Services', label: '📡 Kommunikation' },
  { code: 'Basic Materials', label: '⛏️ Råvaror' },
  { code: 'Utilities', label: '💡 Kraftförsörjning' },
];

const LANGUAGES = [
  { code: 'en', label: 'English' },
  { code: 'sv', label: 'Svenska' },
  { code: 'de', label: 'Deutsch' },
  { code: 'fr', label: 'Français' },
  { code: 'es', label: 'Español' },
  { code: 'ja', label: '日本語' },
  { code: 'zh', label: '中文' },
];

interface NewsItem {
  id: string;
  title: string;
  source: string;
  time: string;
  sentiment: string;
  sentiment_score: number;
  category: string;
  summary: string;
  url: string;
  tickers: string[];
  language: string;
}

interface TrendingEntity {
  symbol: string;
  mentions: number;
  sentiment_avg: number;
  score: number;
}

export default function GlobalOverviewPage() {
  const [news, setNews] = useState<NewsItem[]>([]);
  const [trending, setTrending] = useState<TrendingEntity[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  // Filters
  const [country, setCountry] = useState('');
  const [industry, setIndustry] = useState('');
  const [language, setLanguage] = useState('en');

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (country) params.set('countries', country);
      if (industry) params.set('industries', industry);
      if (language) params.set('language', language);
      if (search) params.set('search', search);
      params.set('limit', '40');

      const response = await fetch(`http://localhost:8000/api/global-news?${params}`);
      const data = await response.json();
      setNews(data.news || []);
      setTrending(data.trending || []);
    } catch {
      // fallback
    }
    setLoading(false);
  }, [country, industry, language, search]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Stats
  const posNews = news.filter(n => n.sentiment === 'positive').length;
  const negNews = news.filter(n => n.sentiment === 'negative').length;
  const neutralNews = news.length - posNews - negNews;

  const getSentimentColor = (s: string) =>
    s === 'positive' ? '#10b981' : s === 'negative' ? '#ef4444' : 'var(--text-tertiary)';

  const getSentimentIcon = (avg: number) => {
    if (avg > 0.15) return <ArrowUp size={11} style={{ color: '#10b981' }} />;
    if (avg < -0.15) return <ArrowDown size={11} style={{ color: '#ef4444' }} />;
    return <Minus size={11} style={{ color: 'var(--text-tertiary)' }} />;
  };

  const activeRegion = REGIONS.find(r => r.code === country)?.label || 'Alla regioner';
  const activeIndustry = INDUSTRIES.find(i => i.code === industry)?.label || 'Alla sektorer';

  return (
    <main className="container" style={{ paddingTop: '2rem', paddingBottom: '6rem' }}>

      {/* Header */}
      <section className="glass-panel animate-fade-in" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
          <Globe size={28} color="var(--accent-cyan)" />
          <div>
            <h2 style={{ margin: 0, fontSize: '1.4rem' }}>Global Marknadsöverblick</h2>
            <p style={{ margin: 0, fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>
              80+ marknader • 5,000+ nyhetskällor • 200,000+ enheter • Live via Marketaux
            </p>
          </div>
          <button
            onClick={fetchData}
            disabled={loading}
            style={{
              marginLeft: 'auto', padding: '0.4rem 0.8rem', borderRadius: '6px',
              background: 'rgba(0,242,254,0.1)', border: '1px solid rgba(0,242,254,0.2)',
              color: '#00f2fe', cursor: 'pointer', fontSize: '0.75rem',
              display: 'flex', alignItems: 'center', gap: '0.3rem',
            }}
          >
            <RefreshCw size={14} className={loading ? 'spin' : ''} /> Uppdatera
          </button>
        </div>

        {/* Filters row */}
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center' }}>
          {/* Search */}
          <div style={{ position: 'relative', flex: '1 1 200px', minWidth: '150px' }}>
            <Search size={14} style={{ position: 'absolute', left: '0.6rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-tertiary)' }} />
            <input
              type="text"
              placeholder="Sök nyheter..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && fetchData()}
              style={{
                width: '100%', padding: '0.5rem 0.5rem 0.5rem 2rem', borderRadius: '6px',
                background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
                color: 'var(--text-primary)', fontSize: '0.8rem',
              }}
            />
          </div>

          {/* Country */}
          <select
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            style={{
              padding: '0.5rem', borderRadius: '6px', fontSize: '0.8rem',
              background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
              color: 'var(--text-primary)', cursor: 'pointer',
            }}
          >
            {REGIONS.map(r => <option key={r.code} value={r.code}>{r.label}</option>)}
          </select>

          {/* Industry */}
          <select
            value={industry}
            onChange={(e) => setIndustry(e.target.value)}
            style={{
              padding: '0.5rem', borderRadius: '6px', fontSize: '0.8rem',
              background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
              color: 'var(--text-primary)', cursor: 'pointer',
            }}
          >
            {INDUSTRIES.map(i => <option key={i.code} value={i.code}>{i.label}</option>)}
          </select>

          {/* Language */}
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            style={{
              padding: '0.5rem', borderRadius: '6px', fontSize: '0.8rem',
              background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
              color: 'var(--text-primary)', cursor: 'pointer',
            }}
          >
            {LANGUAGES.map(l => <option key={l.code} value={l.code}>{l.label}</option>)}
          </select>
        </div>

        {/* Active filters summary */}
        <div style={{ marginTop: '0.75rem', display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <Filter size={12} color="var(--text-tertiary)" />
          <span style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)' }}>
            {activeRegion} • {activeIndustry} • {LANGUAGES.find(l => l.code === language)?.label}
          </span>
          {!loading && (
            <span style={{ fontSize: '0.65rem', marginLeft: 'auto' }}>
              <span style={{ color: '#10b981' }}>▲ {posNews}</span>
              {' · '}
              <span style={{ color: 'var(--text-tertiary)' }}>— {neutralNews}</span>
              {' · '}
              <span style={{ color: '#ef4444' }}>▼ {negNews}</span>
              {' · '}
              <span style={{ color: 'var(--text-secondary)' }}>{news.length} totalt</span>
            </span>
          )}
        </div>
      </section>

      {/* Main Content Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 280px', gap: '1.5rem' }}>

        {/* News Feed */}
        <div>
          {loading ? (
            <div className="glass-panel" style={{ padding: '3rem', textAlign: 'center' }}>
              <RefreshCw size={24} className="spin" color="var(--accent-cyan)" />
              <p style={{ color: 'var(--text-tertiary)', marginTop: '1rem', fontSize: '0.85rem' }}>
                Hämtar globala nyheter...
              </p>
            </div>
          ) : news.length === 0 ? (
            <div className="glass-panel" style={{ padding: '3rem', textAlign: 'center' }}>
              <Newspaper size={32} color="var(--text-tertiary)" />
              <p style={{ color: 'var(--text-tertiary)', marginTop: '1rem' }}>
                Inga nyheter hittades. Prova andra filter.
              </p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {news.map((item, i) => (
                <a
                  key={item.id || i}
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="glass-panel animate-fade-in"
                  style={{
                    display: 'block', padding: '1rem', textDecoration: 'none', color: 'inherit',
                    animationDelay: `${i * 0.02}s`, transition: 'all 0.2s ease',
                    borderLeft: `3px solid ${getSentimentColor(item.sentiment)}`,
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.04)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = '')}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem' }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.3rem', lineHeight: '1.4' }}>
                        {item.title}
                      </div>
                      {item.summary && item.summary !== item.title && (
                        <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', lineHeight: '1.5', marginBottom: '0.4rem' }}>
                          {item.summary.slice(0, 180)}{item.summary.length > 180 ? '...' : ''}
                        </div>
                      )}
                      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
                        <span style={{ fontSize: '0.6rem', color: 'var(--text-tertiary)' }}>{item.source}</span>
                        <span style={{ fontSize: '0.6rem', color: 'var(--text-tertiary)' }}>{item.time}</span>
                        {item.tickers?.slice(0, 4).map(t => (
                          <span key={t} style={{
                            fontSize: '0.55rem', padding: '0.1rem 0.35rem', borderRadius: '3px',
                            background: 'rgba(139,92,246,0.12)', color: '#a78bfa', fontFamily: 'monospace',
                          }}>{t}</span>
                        ))}
                        {item.language && item.language !== 'en' && (
                          <span style={{
                            fontSize: '0.5rem', padding: '0.1rem 0.3rem', borderRadius: '3px',
                            background: 'rgba(0,242,254,0.1)', color: '#00f2fe',
                          }}>{item.language.toUpperCase()}</span>
                        )}
                      </div>
                    </div>
                    <div style={{
                      padding: '0.2rem 0.5rem', borderRadius: '4px', fontSize: '0.6rem', fontWeight: 700,
                      height: 'fit-content', whiteSpace: 'nowrap',
                      background: item.sentiment === 'positive' ? 'rgba(16,185,129,0.12)' :
                                 item.sentiment === 'negative' ? 'rgba(239,68,68,0.12)' : 'rgba(255,255,255,0.04)',
                      color: getSentimentColor(item.sentiment),
                    }}>
                      {item.sentiment === 'positive' ? '↑ Positiv' :
                       item.sentiment === 'negative' ? '↓ Negativ' : '— Neutral'}
                    </div>
                  </div>
                </a>
              ))}
            </div>
          )}
        </div>

        {/* Sidebar: Trending */}
        <div>
          <div className="glass-panel" style={{ padding: '1rem', position: 'sticky', top: '5rem' }}>
            <h4 style={{ margin: '0 0 0.75rem', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <TrendingUp size={16} color="#f59e0b" />
              Trending
              <span style={{ fontSize: '0.6rem', color: 'var(--text-tertiary)', fontWeight: 400, marginLeft: 'auto' }}>
                {activeRegion !== 'Alla regioner' ? activeRegion : 'Globalt'}
              </span>
            </h4>

            {trending.length === 0 ? (
              <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>
                {loading ? 'Laddar...' : 'Ingen trending-data'}
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
                {trending.slice(0, 12).map((e, i) => {
                  const maxMentions = Math.max(...trending.map(t => t.mentions));
                  return (
                    <div key={e.symbol} style={{
                      display: 'flex', alignItems: 'center', gap: '0.4rem',
                      padding: '0.3rem 0.4rem', borderRadius: '5px',
                      background: i < 3 ? 'rgba(245,158,11,0.05)' : 'transparent',
                    }}>
                      <span style={{
                        fontSize: '0.6rem', fontWeight: 700, width: '14px', textAlign: 'center',
                        color: i < 3 ? '#f59e0b' : 'var(--text-tertiary)',
                      }}>{i + 1}</span>
                      <span style={{
                        fontSize: '0.75rem', fontWeight: 600, width: '55px',
                        fontFamily: 'monospace', color: 'var(--text-primary)',
                      }}>{e.symbol}</span>
                      <div style={{ flex: 1, height: '5px', borderRadius: '2px', background: 'rgba(255,255,255,0.04)' }}>
                        <div style={{
                          height: '100%', borderRadius: '2px',
                          width: `${(e.mentions / maxMentions) * 100}%`,
                          background: e.sentiment_avg > 0.1 ? '#10b981' : e.sentiment_avg < -0.1 ? '#ef4444' : 'rgba(255,255,255,0.2)',
                        }} />
                      </div>
                      <span style={{ fontSize: '0.55rem', color: 'var(--text-tertiary)', width: '20px', textAlign: 'right' }}>
                        {e.mentions}
                      </span>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.1rem', width: '35px' }}>
                        {getSentimentIcon(e.sentiment_avg)}
                        <span style={{
                          fontSize: '0.55rem', fontWeight: 600,
                          color: e.sentiment_avg > 0.1 ? '#10b981' : e.sentiment_avg < -0.1 ? '#ef4444' : 'var(--text-tertiary)',
                        }}>
                          {(e.sentiment_avg * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Sentiment summary */}
            {!loading && news.length > 0 && (
              <div style={{ marginTop: '1rem', paddingTop: '0.75rem', borderTop: '1px solid rgba(255,255,255,0.06)' }}>
                <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)', marginBottom: '0.4rem' }}>
                  Sentiment fördelning
                </div>
                <div style={{ display: 'flex', height: '8px', borderRadius: '4px', overflow: 'hidden', gap: '2px' }}>
                  <div style={{ width: `${(posNews / news.length) * 100}%`, background: '#10b981', borderRadius: '4px' }} />
                  <div style={{ width: `${(neutralNews / news.length) * 100}%`, background: 'rgba(255,255,255,0.1)', borderRadius: '4px' }} />
                  <div style={{ width: `${(negNews / news.length) * 100}%`, background: '#ef4444', borderRadius: '4px' }} />
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.3rem' }}>
                  <span style={{ fontSize: '0.55rem', color: '#10b981' }}>{posNews} pos</span>
                  <span style={{ fontSize: '0.55rem', color: 'var(--text-tertiary)' }}>{neutralNews} neut</span>
                  <span style={{ fontSize: '0.55rem', color: '#ef4444' }}>{negNews} neg</span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
