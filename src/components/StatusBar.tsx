import { RefreshCw, Wifi, WifiOff, Loader2 } from 'lucide-react';

interface StatusBarProps {
  isLive: boolean;
  isLoading: boolean;
  error: string | null;
  onRefresh: () => Promise<void>;
}

export default function StatusBar({ isLive, isLoading, error, onRefresh }: StatusBarProps) {
  return (
    <div className="status-bar" style={{
      padding: '0.4rem 0',
      borderBottom: '1px solid var(--glass-border)',
      background: isLive ? 'rgba(0, 230, 118, 0.05)' : 'rgba(255, 234, 0, 0.05)',
    }}>
      <div className="container flex justify-between items-center" style={{ fontSize: '0.8rem' }}>
        <div className="flex items-center gap-2">
          {isLive ? (
            <Wifi size={14} style={{ color: 'var(--score-positive)' }} />
          ) : (
            <WifiOff size={14} style={{ color: 'var(--score-neutral)' }} />
          )}
          <span style={{ color: isLive ? 'var(--score-positive)' : 'var(--score-neutral)' }}>
            {isLive ? 'LIVE – Realtidsdata' : 'DEMO – Mockdata'}
          </span>
          {error && !isLive && (
            <span style={{ color: 'var(--text-tertiary)', marginLeft: '0.5rem' }}>
              ({error})
            </span>
          )}
        </div>
        <button
          onClick={onRefresh}
          disabled={isLoading}
          className="flex items-center gap-2"
          style={{
            background: 'none',
            border: '1px solid var(--glass-border)',
            color: 'var(--text-secondary)',
            padding: '0.2rem 0.6rem',
            borderRadius: '12px',
            cursor: isLoading ? 'wait' : 'pointer',
            fontSize: '0.75rem',
            fontFamily: 'var(--font-body)',
            transition: 'all 0.2s ease',
          }}
        >
          {isLoading ? (
            <Loader2 size={12} className="spin-animation" />
          ) : (
            <RefreshCw size={12} />
          )}
          {isLoading ? 'Uppdaterar...' : 'Uppdatera'}
        </button>
      </div>
    </div>
  );
}
