import { useState, useEffect, useCallback } from 'react';
import { Shield, AlertTriangle, Bell, BellRing, Activity, Zap, Clock, Send, CheckCircle, XCircle } from 'lucide-react';
import { api } from '../api/client';
import type { APIAlert, SentinelStats } from '../api/client';

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<APIAlert[]>([]);
  const [stats, setStats] = useState<SentinelStats | null>(null);
  const [minImpact, setMinImpact] = useState(1);
  const [testStatus, setTestStatus] = useState<'idle' | 'sending' | 'success' | 'error'>('idle');

  const fetchAlerts = useCallback(async () => {
    try {
      const data = await api.getAlerts(minImpact);
      setAlerts(data.alerts || []);
      setStats(data.stats || null);
    } catch {
      // Backend might not be running
    }
  }, [minImpact]);

  useEffect(() => {
    fetchAlerts();
    const interval = setInterval(fetchAlerts, 15000); // Poll every 15s
    return () => clearInterval(interval);
  }, [fetchAlerts]);

  const handleTestNotification = async () => {
    setTestStatus('sending');
    try {
      const result = await api.testNotification();
      setTestStatus(result.success ? 'success' : 'error');
    } catch {
      setTestStatus('error');
    }
    setTimeout(() => setTestStatus('idle'), 3000);
  };

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
        background: `${info.color}20`,
        color: info.color,
        border: `1px solid ${info.color}40`,
        fontSize: '0.7rem',
      }}>
        {info.label}
      </span>
    );
  };

  return (
    <main className="container" style={{ paddingTop: '2rem', paddingBottom: '6rem' }}>

      {/* Header */}
      <div className="flex items-center gap-2" style={{ marginBottom: '0.5rem' }}>
        <Shield size={28} color="var(--accent-cyan)" />
        <h2 style={{ margin: 0, fontSize: '1.8rem' }}>News Sentinel</h2>
      </div>
      <p style={{ color: 'var(--text-tertiary)', marginBottom: '2rem', fontSize: '0.9rem' }}>
        AI-övervakare som bevakar alla nyheter och varnar vid marknadskritiska händelser.
      </p>

      {/* Stats & Controls */}
      <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
        <div className="glass-panel" style={{ padding: '1.25rem', textAlign: 'center' }}>
          <Activity size={20} color="var(--accent-cyan)" style={{ marginBottom: '0.5rem' }} />
          <div style={{ fontSize: '1.8rem', fontWeight: 700 }}>{stats?.total_scanned ?? 0}</div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>Nyheter skannade</div>
        </div>
        <div className="glass-panel" style={{ padding: '1.25rem', textAlign: 'center' }}>
          <AlertTriangle size={20} color="#ff9f43" style={{ marginBottom: '0.5rem' }} />
          <div style={{ fontSize: '1.8rem', fontWeight: 700, color: '#ff9f43' }}>{stats?.alerts_triggered ?? 0}</div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>Varningar (≥5)</div>
        </div>
        <div className="glass-panel" style={{ padding: '1.25rem', textAlign: 'center' }}>
          <Zap size={20} color="#ff4757" style={{ marginBottom: '0.5rem' }} />
          <div style={{ fontSize: '1.8rem', fontWeight: 700, color: '#ff4757' }}>{stats?.critical_alerts ?? 0}</div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>Kritiska (≥7)</div>
        </div>
        <div className="glass-panel" style={{ padding: '1.25rem', textAlign: 'center' }}>
          <Clock size={20} color="var(--text-tertiary)" style={{ marginBottom: '0.5rem' }} />
          <div style={{ fontSize: '0.9rem', fontWeight: 600 }}>
            {stats?.last_scan ? new Date(stats.last_scan).toLocaleTimeString('sv') : '—'}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>Senaste skanning</div>
        </div>
      </div>

      {/* Push notification setup */}
      <div className="glass-panel" style={{ padding: '1.5rem', marginBottom: '2rem', borderLeft: '3px solid var(--accent-cyan)' }}>
        <div className="flex items-center justify-between" style={{ flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h3 style={{ margin: '0 0 0.3rem', fontSize: '1.1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <BellRing size={18} /> Push-notiser till mobilen
            </h3>
            <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              Installera <strong>ntfy</strong>-appen → Prenumerera på ämne: <code style={{
                background: 'rgba(255,255,255,0.1)',
                padding: '0.15rem 0.4rem',
                borderRadius: '4px',
                fontSize: '0.85rem',
              }}>aether-ai-alerts</code>
            </p>
            <div className="flex items-center gap-3" style={{ marginTop: '0.5rem' }}>
              <a href="https://play.google.com/store/apps/details?id=io.heckel.ntfy" target="_blank" rel="noopener noreferrer"
                style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)', textDecoration: 'underline' }}>
                Android
              </a>
              <a href="https://apps.apple.com/app/ntfy/id1625396347" target="_blank" rel="noopener noreferrer"
                style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)', textDecoration: 'underline' }}>
                iOS
              </a>
            </div>
          </div>
          <button
            onClick={handleTestNotification}
            disabled={testStatus === 'sending'}
            className="glass-panel"
            style={{
              padding: '0.75rem 1.5rem',
              cursor: testStatus === 'sending' ? 'wait' : 'pointer',
              display: 'flex', alignItems: 'center', gap: '0.5rem',
              fontSize: '0.85rem', fontWeight: 600,
              border: `1px solid ${testStatus === 'success' ? '#2ed573' : testStatus === 'error' ? '#ff4757' : 'var(--accent-cyan)'}40`,
              color: testStatus === 'success' ? '#2ed573' : testStatus === 'error' ? '#ff4757' : 'var(--accent-cyan)',
              transition: 'all 0.3s ease',
            }}
          >
            {testStatus === 'sending' && <><Send size={14} /> Skickar...</>}
            {testStatus === 'success' && <><CheckCircle size={14} /> Skickad!</>}
            {testStatus === 'error' && <><XCircle size={14} /> Misslyckades</>}
            {testStatus === 'idle' && <><Bell size={14} /> Testa push-notis</>}
          </button>
        </div>
      </div>

      {/* Filter */}
      <div className="flex items-center gap-3" style={{ marginBottom: '1.5rem' }}>
        <span style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>Visa impact ≥</span>
        {[1, 3, 5, 7].map(level => (
          <button
            key={level}
            onClick={() => setMinImpact(level)}
            className="glass-panel"
            style={{
              padding: '0.4rem 0.8rem',
              fontSize: '0.8rem',
              cursor: 'pointer',
              border: `1px solid ${minImpact === level ? 'var(--accent-cyan)' : 'var(--glass-border)'}`,
              color: minImpact === level ? 'var(--accent-cyan)' : 'var(--text-secondary)',
              fontWeight: minImpact === level ? 700 : 400,
            }}
          >
            {level}+
          </button>
        ))}
      </div>

      {/* Alert List */}
      {alerts.length === 0 ? (
        <div className="glass-panel" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-tertiary)' }}>
          <Shield size={48} style={{ marginBottom: '1rem', opacity: 0.5 }} />
          <p style={{ margin: '0 0 0.5rem', fontSize: '1.1rem' }}>Inga varningar än</p>
          <p style={{ margin: 0, fontSize: '0.85rem' }}>
            Sentinel bevakar nyhetsflöden och varnar vid impact ≥ {minImpact}. 
            {stats?.total_scanned ? ` ${stats.total_scanned} nyheter har skannats.` : ''}
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {alerts.sort((a, b) => b.impact_score - a.impact_score).map((alert, index) => (
            <div
              key={alert.id}
              className="glass-panel animate-fade-in"
              style={{
                padding: '1.25rem',
                animationDelay: `${index * 0.03}s`,
                borderLeft: `3px solid ${getImpactColor(alert.impact_score)}`,
              }}
            >
              <div className="flex items-center justify-between" style={{ marginBottom: '0.5rem' }}>
                <div className="flex items-center gap-2" style={{ flexWrap: 'wrap' }}>
                  <div style={{
                    width: '36px', height: '36px', borderRadius: '50%',
                    background: `${getImpactColor(alert.impact_score)}20`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontWeight: 700, fontSize: '0.9rem',
                    color: getImpactColor(alert.impact_score),
                    flexShrink: 0,
                  }}>
                    {alert.impact_score}
                  </div>
                  {getUrgencyBadge(alert.urgency)}
                  <span className="badge" style={{ fontSize: '0.7rem' }}>{alert.category}</span>
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>{alert.source}</span>
                </div>
                <span style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', flexShrink: 0 }}>
                  {alert.time || new Date(alert.timestamp).toLocaleTimeString('sv')}
                </span>
              </div>

              <p style={{ margin: '0 0 0.5rem', fontSize: '0.9rem', fontWeight: 500 }}>
                {alert.one_liner || alert.title}
              </p>

              {(alert.affected_assets.length > 0 || alert.affected_sectors.length > 0 || alert.affected_regions.length > 0) && (
                <div className="flex" style={{ gap: '0.3rem', flexWrap: 'wrap' }}>
                  {alert.affected_assets.map(a => (
                    <span key={a} className="badge" style={{
                      fontSize: '0.65rem', padding: '0.15rem 0.4rem',
                      background: 'var(--accent-cyan)10', border: '1px solid var(--accent-cyan)30',
                      color: 'var(--accent-cyan)',
                    }}>
                      📈 {a}
                    </span>
                  ))}
                  {alert.affected_sectors.map(s => (
                    <span key={s} className="badge" style={{
                      fontSize: '0.65rem', padding: '0.15rem 0.4rem',
                      background: '#a55eea10', border: '1px solid #a55eea30',
                      color: '#a55eea',
                    }}>
                      🏭 {s}
                    </span>
                  ))}
                  {alert.affected_regions.map(r => (
                    <span key={r} className="badge" style={{
                      fontSize: '0.65rem', padding: '0.15rem 0.4rem',
                      background: '#2ed57310', border: '1px solid #2ed57330',
                      color: '#2ed573',
                    }}>
                      🌍 {r}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
