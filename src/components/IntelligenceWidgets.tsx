import { useState, useEffect } from 'react';
import { api, type APIRegimeData, type APICalendarEvent, type APIOnchainData } from '../api/client';

// ============================
// REGIME BADGE (for Header)
// ============================
export function RegimeBadge() {
  const [regime, setRegime] = useState<APIRegimeData | null>(null);

  useEffect(() => {
    api.getRegime().then(setRegime).catch(() => {});
  }, []);

  if (!regime) return null;

  const regimeColors: Record<string, string> = {
    'risk-on': '#00c851',
    'risk-off': '#ff4757',
    'inflation': '#ffa502',
    'deflation': '#5352ed',
    'transition': '#a4b0be',
    'leaning-risk-on': '#7bed9f',
    'leaning-risk-off': '#ff6b81',
  };

  const bgColor = regimeColors[regime.regime] || '#a4b0be';
  const confidence = Math.round(regime.confidence * 100);

  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: '0.4rem',
      padding: '0.3rem 0.7rem', borderRadius: '6px',
      background: `${bgColor}18`, border: `1px solid ${bgColor}40`,
      fontSize: '0.75rem', fontWeight: 600, color: bgColor,
      whiteSpace: 'nowrap',
    }}>
      <span style={{ fontSize: '0.85rem' }}>
        {regime.regime.includes('risk-on') ? '📈' : regime.regime.includes('risk-off') ? '📉' : regime.regime === 'inflation' ? '🔥' : '🔄'}
      </span>
      <span>{regime.regime.replace('-', ' ').replace('leaning ', '↗').toUpperCase()}</span>
      <span style={{ opacity: 0.7, fontSize: '0.7rem' }}>{confidence}%</span>
    </div>
  );
}

// ============================
// CALENDAR WIDGET (for Dashboard)
// ============================
export function CalendarWidget() {
  const [events, setEvents] = useState<APICalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getCalendar()
      .then(d => setEvents(d.upcoming || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading || events.length === 0) {
    return (
      <div className="glass-panel" style={{ padding: '1.25rem' }}>
        <h4 style={{ margin: '0 0 0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1rem' }}>
          📅 Ekonomisk Kalender
        </h4>
        <p style={{ color: 'var(--text-tertiary)', fontSize: '0.85rem', margin: 0 }}>
          {loading ? 'Laddar...' : 'Inga kommande events inom 7 dagar'}
        </p>
      </div>
    );
  }

  return (
    <div className="glass-panel" style={{ padding: '1.25rem' }}>
      <h4 style={{ margin: '0 0 0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1rem' }}>
        📅 Ekonomisk Kalender
        <span style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', fontWeight: 400 }}>
          närmaste 7d
        </span>
      </h4>
      <div className="flex flex-col gap-2">
        {events.slice(0, 5).map((event, i) => {
          const urgencyColor = event.urgency === 'imminent' ? '#ff4757' : event.urgency === 'today' ? '#ffa502' : event.urgency === 'soon' ? '#ffd93d' : '#a4b0be';
          const urgencyEmoji = event.urgency === 'imminent' ? '🔴' : event.urgency === 'today' ? '🟠' : '🟡';
          return (
            <div key={i} style={{
              padding: '0.6rem 0.75rem', borderRadius: '8px',
              background: 'rgba(255,255,255,0.02)',
              borderLeft: `3px solid ${urgencyColor}`,
            }}>
              <div className="flex justify-between items-center">
                <div>
                  <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>{urgencyEmoji} {event.name}</span>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', marginTop: '0.15rem' }}>
                    {event.date} • {event.time_utc} UTC
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{
                    fontSize: '0.78rem', fontWeight: 600,
                    color: event.hours_until && event.hours_until < 12 ? urgencyColor : 'var(--text-secondary)',
                  }}>
                    {event.hours_until ? `om ${Math.round(event.hours_until)}h` : `${Math.round(event.hours_ago || 0)}h sedan`}
                  </div>
                  <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)' }}>
                    Impact: {'🔥'.repeat(Math.min(3, Math.ceil(event.impact / 3)))} {event.impact}/10
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ============================
// ONCHAIN PANEL (for BTC detail)
// ============================
export function OnchainPanel() {
  const [data, setData] = useState<APIOnchainData | null>(null);

  useEffect(() => {
    api.getOnchain().then(setData).catch(() => {});
  }, []);

  if (!data || !data.available) return null;

  const metrics = [
    data.mempool ? { label: 'Mempool', value: `${data.mempool.tx_count.toLocaleString()} tx`, sub: `Trängsel: ${data.mempool.congestion}`, icon: '📦' } : null,
    data.fees ? { label: 'Avgifter', value: `${data.fees.fastest} sat/vB`, sub: `Tryck: ${data.fees.pressure}`, icon: '⛽' } : null,
    data.hashrate ? { label: 'Hashrate', value: `${data.hashrate.current_eh} EH/s`, sub: `${data.hashrate.weekly_change_pct > 0 ? '+' : ''}${data.hashrate.weekly_change_pct}% vecka`, icon: '⚡' } : null,
    data.supply ? { label: 'Supply', value: `${data.supply.pct_mined}%`, sub: `${(data.supply.remaining_btc / 1000).toFixed(0)}k BTC kvar`, icon: '💎' } : null,
  ].filter(Boolean) as Array<{ label: string; value: string; sub: string; icon: string }>;

  return (
    <div className="glass-panel" style={{
      padding: '1.25rem', marginTop: '1.5rem',
      background: 'rgba(247, 147, 26, 0.04)', borderLeft: '3px solid #f7931a',
    }}>
      <h4 style={{ margin: '0 0 0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#f7931a' }}>
        ⛓️ On-Chain Data
      </h4>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: '0.5rem' }}>
        {metrics.map((m, i) => (
          <div key={i} style={{ padding: '0.5rem', borderRadius: '6px', background: 'rgba(255,255,255,0.02)' }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>{m.icon} {m.label}</div>
            <div style={{ fontSize: '1rem', fontWeight: 700, marginTop: '0.15rem' }}>{m.value}</div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>{m.sub}</div>
          </div>
        ))}
      </div>
      {data.difficulty && (
        <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginTop: '0.5rem' }}>
          ⚙️ Nästa difficulty: {data.difficulty.estimated_change_pct > 0 ? '+' : ''}{data.difficulty.estimated_change_pct}% 
          (progress: {data.difficulty.progress_pct}%)
        </div>
      )}
    </div>
  );
}

// ============================
// CORRELATION MINI (for Dashboard sidebar)
// ============================
export function CorrelationMini() {
  const [data, setData] = useState<{ notable_pairs: Array<{ asset_a: string; asset_b: string; correlation: number; strength: string }>; systemic?: { regime: string; risk_on_count: number; risk_off_count: number } } | null>(null);

  useEffect(() => {
    api.getCorrelations().then(setData).catch(() => {});
  }, []);

  if (!data || !data.notable_pairs?.length) return null;

  const nameMap: Record<string, string> = {
    btc: 'BTC', sp500: 'S&P', gold: 'Guld', silver: 'Silver',
    oil: 'Olja', us10y: '10Y', eurusd: 'EUR/USD', 'global-equity': 'ACWI',
  };

  const sys = data.systemic;

  return (
    <div className="glass-panel" style={{ padding: '1.25rem' }}>
      <h4 style={{ margin: '0 0 0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1rem' }}>
        🔗 Korrelationer
        {sys && (
          <span style={{
            fontSize: '0.7rem', padding: '0.15rem 0.5rem', borderRadius: '4px',
            background: sys.risk_on_count > sys.risk_off_count ? 'rgba(0,200,81,0.1)' : 'rgba(255,71,87,0.1)',
            color: sys.risk_on_count > sys.risk_off_count ? 'var(--score-positive)' : 'var(--score-negative)',
          }}>
            {sys.risk_on_count} on / {sys.risk_off_count} off
          </span>
        )}
      </h4>
      <div className="flex flex-col gap-1">
        {data.notable_pairs.slice(0, 5).map((p, i) => {
          const corrColor = p.correlation > 0 ? 'var(--score-positive)' : 'var(--score-negative)';
          const barWidth = Math.abs(p.correlation) * 100;
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8rem' }}>
              <span style={{ width: '100px', color: 'var(--text-secondary)' }}>
                {nameMap[p.asset_a] || p.asset_a}↔{nameMap[p.asset_b] || p.asset_b}
              </span>
              <div style={{ flex: 1, height: '6px', background: 'rgba(255,255,255,0.05)', borderRadius: '3px', overflow: 'hidden' }}>
                <div style={{ width: `${barWidth}%`, height: '100%', background: corrColor, borderRadius: '3px', transition: 'width 0.5s' }} />
              </div>
              <span style={{ width: '45px', textAlign: 'right', fontWeight: 600, color: corrColor, fontSize: '0.78rem' }}>
                {p.correlation > 0 ? '+' : ''}{p.correlation.toFixed(2)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
