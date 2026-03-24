import { useState, useEffect, useCallback } from 'react';
import { Newspaper, Shield, Bell, BellRing, Filter, Activity, Zap, Clock, Send, CheckCircle, XCircle } from 'lucide-react';
import type { NewsItem } from '../types';
import NewsCard from '../components/NewsCard';
import { api } from '../api/client';
import type { APIAlert, SentinelStats } from '../api/client';

type ActiveTab = 'feed' | 'alerts' | 'settings';
type SentimentFilter = 'all' | 'positive' | 'negative' | 'neutral';

interface NewsPageProps {
  news: NewsItem[];
}

export default function NewsPage({ news }: NewsPageProps) {
  const [activeTab, setActiveTab] = useState<ActiveTab>('feed');
  const [filter, setFilter] = useState<SentimentFilter>('all');
  const [alerts, setAlerts] = useState<APIAlert[]>([]);
  const [stats, setStats] = useState<SentinelStats | null>(null);
  const [minImpact, setMinImpact] = useState(1);
  const [testStatus, setTestStatus] = useState<'idle' | 'sending' | 'success' | 'error'>('idle');

  const fetchAlerts = useCallback(async () => {
    try {
      const data = await api.getAlerts(minImpact);
      setAlerts(data.alerts || []);
      setStats(data.stats || null);
    } catch { /* Backend might not be running */ }
  }, [minImpact]);

  useEffect(() => {
    fetchAlerts();
    const interval = setInterval(fetchAlerts, 15000);
    return () => clearInterval(interval);
  }, [fetchAlerts]);

  const handleTestNotification = async () => {
    setTestStatus('sending');
    try {
      const result = await api.testNotification();
      setTestStatus(result.success ? 'success' : 'error');
    } catch { setTestStatus('error'); }
    setTimeout(() => setTestStatus('idle'), 3000);
  };

  const filteredNews = filter === 'all' ? news
    : filter === 'negative' ? news.filter(n => (n as any).impact?.score >= 7)
    : filter === 'positive' ? news.filter(n => (n as any).impact?.provider === 'gemini' && (n as any).impact?.score >= 7)
    : news;
  const alertCount = stats?.alerts_triggered ?? 0;

  const getImpactColor = (score: number) => {
    if (score >= 8) return '#ff4757';
    if (score >= 6) return '#ff9f43';
    if (score >= 4) return '#ffd93d';
    return '#2ed573';
  };

  const getUrgencyBadge = (urgency: string) => {
    const map: Record<string, { color: string; label: string }> = {
      critical: { color: '#ff4757', label: '🚨 Kritisk' },
      urgent: { color: '#ff9f43', label: '⚠️ Brådskande' },
      notable: { color: '#ffd93d', label: '📊 Noterbart' },
      routine: { color: '#2ed573', label: '✅ Rutin' },
    };
    const info = map[urgency] || map.routine;
    return (
      <span className="badge" style={{
        background: `${info.color}20`, color: info.color,
        border: `1px solid ${info.color}40`, fontSize: '0.7rem',
      }}>
        {info.label}
      </span>
    );
  };

  const tabs: { id: ActiveTab; label: string; icon: React.ReactNode; badge?: number }[] = [
    { id: 'alerts', label: 'Varningar', icon: <Shield size={16} />, badge: alertCount > 0 ? alertCount : undefined },
    { id: 'feed', label: 'Nyhetsflöde', icon: <Newspaper size={16} /> },
    { id: 'settings', label: 'Push-notiser', icon: <Bell size={16} /> },
  ];

  return (
    <main className="container" style={{ paddingTop: '2rem', paddingBottom: '6rem' }}>

      {/* Header */}
      <div className="flex items-center gap-2" style={{ marginBottom: '1rem' }}>
        <Newspaper size={28} color="var(--accent-blue)" />
        <h2 style={{ margin: 0, fontSize: '1.8rem' }}>Nyheter & Sentinel</h2>
      </div>

      {/* Tab bar */}
      <div className="flex" style={{
        gap: '0.25rem', marginBottom: '1.5rem',
        borderBottom: '1px solid var(--glass-border)', paddingBottom: '0',
      }}>
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              background: 'none', border: 'none', borderBottom: `2px solid ${activeTab === tab.id ? 'var(--accent-cyan)' : 'transparent'}`,
              color: activeTab === tab.id ? 'var(--accent-cyan)' : 'var(--text-tertiary)',
              padding: '0.6rem 1rem', cursor: 'pointer', fontSize: '0.9rem',
              fontWeight: activeTab === tab.id ? 600 : 400, fontFamily: 'var(--font-body)',
              display: 'flex', alignItems: 'center', gap: '0.4rem',
              transition: 'all 0.2s ease', position: 'relative',
            }}
          >
            {tab.icon} {tab.label}
            {tab.badge && (
              <span style={{
                background: '#ff4757', color: '#fff', fontSize: '0.65rem', fontWeight: 700,
                padding: '0.1rem 0.4rem', borderRadius: '10px', minWidth: '18px', textAlign: 'center',
              }}>
                {tab.badge}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ========== TAB: ALERTS ========== */}
      {activeTab === 'alerts' && (
        <>
          {/* Sentinel Stats */}
          <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.75rem', marginBottom: '1.5rem' }}>
            <div className="glass-panel" style={{ padding: '1rem', textAlign: 'center' }}>
              <Activity size={18} color="var(--accent-cyan)" style={{ marginBottom: '0.3rem' }} />
              <div style={{ fontSize: '1.5rem', fontWeight: 700 }}>{stats?.total_scanned ?? 0}</div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>Skannade</div>
            </div>
            <div className="glass-panel" style={{ padding: '1rem', textAlign: 'center' }}>
              <Shield size={18} color="#ff9f43" style={{ marginBottom: '0.3rem' }} />
              <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#ff9f43' }}>{stats?.alerts_triggered ?? 0}</div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>Varningar</div>
            </div>
            <div className="glass-panel" style={{ padding: '1rem', textAlign: 'center' }}>
              <Zap size={18} color="#ff4757" style={{ marginBottom: '0.3rem' }} />
              <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#ff4757' }}>{stats?.critical_alerts ?? 0}</div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>Kritiska</div>
            </div>
            <div className="glass-panel" style={{ padding: '1rem', textAlign: 'center' }}>
              <Clock size={18} color="var(--text-tertiary)" style={{ marginBottom: '0.3rem' }} />
              <div style={{ fontSize: '0.85rem', fontWeight: 600 }}>
                {stats?.last_scan ? new Date(stats.last_scan).toLocaleTimeString('sv') : '—'}
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>Senaste</div>
            </div>
          </div>

          {/* Impact filter */}
          <div className="flex items-center gap-2" style={{ marginBottom: '1rem' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>Impact ≥</span>
            {[1, 3, 5, 7].map(level => (
              <button key={level} onClick={() => setMinImpact(level)} className="glass-panel" style={{
                padding: '0.3rem 0.6rem', fontSize: '0.75rem', cursor: 'pointer',
                border: `1px solid ${minImpact === level ? 'var(--accent-cyan)' : 'var(--glass-border)'}`,
                color: minImpact === level ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                fontWeight: minImpact === level ? 700 : 400,
              }}>
                {level}+
              </button>
            ))}
          </div>

          {/* Alert list */}
          {alerts.length === 0 ? (
            <div className="glass-panel" style={{ padding: '2.5rem', textAlign: 'center', color: 'var(--text-tertiary)' }}>
              <Shield size={40} style={{ marginBottom: '0.75rem', opacity: 0.5 }} />
              <p style={{ margin: '0 0 0.3rem', fontSize: '1rem' }}>Inga varningar</p>
              <p style={{ margin: 0, fontSize: '0.8rem' }}>
                Sentinel bevakar och varnar vid impact ≥ {minImpact}.
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {alerts.sort((a, b) => b.impact_score - a.impact_score).map((alert, i) => (
                <div key={alert.id} className="glass-panel animate-fade-in" style={{
                  padding: '1rem', animationDelay: `${i * 0.03}s`,
                  borderLeft: `3px solid ${getImpactColor(alert.impact_score)}`,
                }}>
                  <div className="flex items-center justify-between" style={{ marginBottom: '0.4rem' }}>
                    <div className="flex items-center gap-2" style={{ flexWrap: 'wrap' }}>
                      <div style={{
                        width: '32px', height: '32px', borderRadius: '50%',
                        background: `${getImpactColor(alert.impact_score)}20`,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontWeight: 700, fontSize: '0.85rem', color: getImpactColor(alert.impact_score), flexShrink: 0,
                      }}>
                        {alert.impact_score}
                      </div>
                      {getUrgencyBadge(alert.urgency)}
                      <span className="badge" style={{ fontSize: '0.65rem' }}>{alert.category}</span>
                      <span style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)' }}>{alert.source}</span>
                    </div>
                    <span style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)', flexShrink: 0 }}>
                      {alert.time || new Date(alert.timestamp).toLocaleTimeString('sv')}
                    </span>
                  </div>
                  <p style={{ margin: 0, fontSize: '0.85rem', fontWeight: 500 }}>
                    {alert.one_liner || alert.title}
                  </p>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* ========== TAB: NEWS FEED ========== */}
      {activeTab === 'feed' && (
        <>
          <div className="flex justify-between items-center" style={{ marginBottom: '1.5rem', flexWrap: 'wrap', gap: '0.75rem' }}>
            <div className="grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem', flex: 1, minWidth: '280px' }}>
              <div className="glass-panel" style={{ padding: '0.6rem', textAlign: 'center' }}>
                <div style={{ fontSize: '1.3rem', fontWeight: 700 }}>{news.length}</div>
                <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)' }}>Totalt</div>
              </div>
              <div className="glass-panel" style={{ padding: '0.6rem', textAlign: 'center' }}>
                <div style={{ fontSize: '1.3rem', fontWeight: 700, color: '#f59e0b' }}>
                  {news.filter(n => (n as any).impact?.score >= 7).length}
                </div>
                <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)' }}>⚡ Hög impact</div>
              </div>
              <div className="glass-panel" style={{ padding: '0.6rem', textAlign: 'center' }}>
                <div style={{ fontSize: '1.3rem', fontWeight: 700, color: '#a78bfa' }}>
                  {news.filter(n => (n as any).impact?.provider === 'gemini' && (n as any).impact?.score >= 7).length}
                </div>
                <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)' }}>🧠 AI-analyserade</div>
              </div>
            </div>
            <div className="flex items-center gap-2" style={{ flexWrap: 'wrap' }}>
              <Filter size={14} color="var(--text-tertiary)" />
              {([
                { label: 'Alla', value: 'all' as const },
                { label: '⚡ Impact', value: 'negative' as const },
                { label: '🧠 AI', value: 'positive' as const },
              ]).map(f => (
                <button key={f.value} onClick={() => setFilter(f.value)} style={{
                  background: filter === f.value ? 'rgba(0, 242, 254, 0.15)' : 'transparent',
                  border: `1px solid ${filter === f.value ? 'var(--accent-cyan)' : 'var(--glass-border)'}`,
                  color: filter === f.value ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                  padding: '0.3rem 0.6rem', borderRadius: '16px', cursor: 'pointer',
                  fontSize: '0.8rem', fontFamily: 'var(--font-body)', transition: 'all 0.2s ease',
                }}>
                  {f.label}
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-3">
            {filteredNews.map(item => (<NewsCard key={item.id} item={item} />))}
            {filteredNews.length === 0 && (
              <div className="glass-panel" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-tertiary)' }}>
                Inga nyheter matchar filtret.
              </div>
            )}
          </div>
        </>
      )}

      {/* ========== TAB: SETTINGS ========== */}
      {activeTab === 'settings' && (
        <div className="flex flex-col gap-4">
          <div className="glass-panel" style={{ padding: '1.5rem', borderLeft: '3px solid var(--accent-cyan)' }}>
            <h3 style={{ margin: '0 0 0.5rem', fontSize: '1.1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <BellRing size={18} /> Push-notiser till mobilen
            </h3>
            <p style={{ margin: '0 0 0.75rem', fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              Installera <strong>ntfy</strong>-appen på din telefon och prenumerera på ämne:
            </p>
            <code style={{
              display: 'inline-block', background: 'rgba(255,255,255,0.08)',
              padding: '0.4rem 0.8rem', borderRadius: '6px', fontSize: '0.95rem',
              marginBottom: '1rem', fontWeight: 600,
            }}>
              aether-ai-alerts
            </code>
            <div className="flex items-center gap-4" style={{ marginBottom: '1rem' }}>
              <a href="https://play.google.com/store/apps/details?id=io.heckel.ntfy" target="_blank" rel="noopener noreferrer"
                style={{ fontSize: '0.85rem', color: 'var(--accent-cyan)', textDecoration: 'underline' }}>
                📱 Android
              </a>
              <a href="https://apps.apple.com/app/ntfy/id1625396347" target="_blank" rel="noopener noreferrer"
                style={{ fontSize: '0.85rem', color: 'var(--accent-cyan)', textDecoration: 'underline' }}>
                🍎 iOS
              </a>
            </div>
            <button onClick={handleTestNotification} disabled={testStatus === 'sending'} className="glass-panel" style={{
              padding: '0.7rem 1.5rem', cursor: testStatus === 'sending' ? 'wait' : 'pointer',
              display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', fontWeight: 600,
              border: `1px solid ${testStatus === 'success' ? '#2ed573' : testStatus === 'error' ? '#ff4757' : 'var(--accent-cyan)'}40`,
              color: testStatus === 'success' ? '#2ed573' : testStatus === 'error' ? '#ff4757' : 'var(--accent-cyan)',
              transition: 'all 0.3s ease',
            }}>
              {testStatus === 'sending' && <><Send size={14} /> Skickar...</>}
              {testStatus === 'success' && <><CheckCircle size={14} /> Skickad!</>}
              {testStatus === 'error' && <><XCircle size={14} /> Misslyckades</>}
              {testStatus === 'idle' && <><Bell size={14} /> Testa push-notis</>}
            </button>
          </div>

          <div className="glass-panel" style={{ padding: '1.5rem' }}>
            <h3 style={{ margin: '0 0 0.5rem', fontSize: '1.1rem' }}>Hur det fungerar</h3>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.8 }}>
              <p style={{ margin: '0 0 0.5rem' }}>
                <strong>AI Sentinel</strong> (Gemini Flash) skannar varje nyhet och ger den en impact-poäng 1-10:
              </p>
              <div style={{ paddingLeft: '0.5rem' }}>
                <div>🟢 <strong>1-4</strong>: Rutinnyhet → lagras tyst</div>
                <div>🟡 <strong>5-6</strong>: Viktig → noteras i varningar</div>
                <div>🔴 <strong>7-10</strong>: Marknadskritisk → <strong>push-notis + full AI-analys</strong></div>
              </div>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
