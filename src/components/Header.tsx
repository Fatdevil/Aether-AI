import { Brain } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { getScoreColor, getRecommendation } from '../types';
import { RegimeBadge } from './IntelligenceWidgets';

interface HeaderProps {
  marketState: {
    overallScore: number;
    overallSummary: string;
    lastUpdated: string;
  };
}

export default function Header({ marketState }: HeaderProps) {
  const location = useLocation();
  const rec = getRecommendation(marketState.overallScore);

  const navLinks = [
    { path: '/', label: 'Marknad' },
    { path: '/analysis', label: 'Analys' },
    { path: '/brief', label: 'Rapport' },
    { path: '/portfolio', label: 'Portfölj' },
    { path: '/insights', label: 'AI Insikter' },
  ];

  return (
    <header className="glass-header" style={{ padding: '0.85rem 0' }}>
      <div className="container flex justify-between items-center">
        <Link to="/" className="flex items-center gap-2" style={{ textDecoration: 'none', color: 'inherit' }}>
          <Brain size={28} color="var(--accent-cyan)" />
          <h1 style={{ margin: 0, fontSize: '1.3rem' }}>
            <span className="text-gradient">Aether</span> <span style={{ fontWeight: 400, color: 'var(--text-secondary)' }}>AI</span>
          </h1>
        </Link>

        <nav className="desktop-nav flex items-center gap-2">
          {navLinks.map(link => {
            const isActive = location.pathname === link.path;
            return (
              <Link
                key={link.path}
                to={link.path}
                className="nav-link"
                style={{
                  color: isActive ? 'var(--text-primary)' : 'var(--text-tertiary)',
                  textDecoration: 'none',
                  fontSize: '0.9rem',
                  fontWeight: isActive ? 600 : 400,
                  transition: 'all 0.2s ease',
                  padding: '0.5rem 1rem',
                  borderRadius: '8px',
                  background: isActive ? 'rgba(79, 172, 254, 0.1)' : 'transparent',
                  border: isActive ? '1px solid rgba(79, 172, 254, 0.2)' : '1px solid transparent',
                }}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-2" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <RegimeBadge />
          <span style={{
            color: `var(--score-${getScoreColor(marketState.overallScore)})`,
            fontSize: '0.85rem',
            fontWeight: 600,
          }}>
            {rec}
          </span>
        </div>
      </div>
    </header>
  );
}
