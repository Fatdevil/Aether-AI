import { ShieldAlert } from 'lucide-react';
import type { Asset } from '../types';
import { getRecommendation, getScoreColor } from '../types';

interface SupervisorPanelProps {
  asset: Asset;
}

export default function SupervisorPanel({ asset }: SupervisorPanelProps) {
  const recommendation = getRecommendation(asset.finalScore);
  const colorClass = getScoreColor(asset.finalScore);

  return (
    <div className="glass-panel supervisor-panel" style={{
      padding: '1.5rem',
      background: 'rgba(0, 242, 254, 0.05)',
      border: '1px solid rgba(0, 242, 254, 0.2)',
    }}>
      <div className="flex justify-between items-center" style={{ marginBottom: '0.75rem' }}>
        <h4 style={{
          color: 'var(--accent-cyan)',
          margin: 0,
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
        }}>
          <ShieldAlert size={16} /> Supervisor AI Motivering
        </h4>
        <span className={`badge ${colorClass}`}>
          {recommendation}
        </span>
      </div>
      <p style={{
        fontSize: '0.9rem',
        color: 'var(--text-secondary)',
        lineHeight: 1.7,
        margin: 0,
      }}>
        Transparensrapport: "{asset.supervisorText}"
      </p>
    </div>
  );
}
