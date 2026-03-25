import { Brain, Menu, X } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { useState } from 'react';
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
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  const rec = getRecommendation(marketState.overallScore);

  const navLinks = [
    { path: '/', label: 'Dashboard' },
    { path: '/sectors', label: 'Sektorer' },
    { path: '/regions', label: 'Regioner' },
    { path: '/portfolio', label: 'Portfölj' },
    { path: '/news', label: 'Nyheter' },
    { path: '/performance', label: 'AI Prestanda' },
    { path: '/backtest', label: 'Backtest' },
    { path: '/predict', label: '🧠 Predict' },
    { path: '/global', label: 'Global' },
  ];

  return (
    <header className="glass-header" style={{ padding: '1rem 0' }}>
      <div className="container flex justify-between items-center">
        <Link to="/" className="flex items-center gap-2" style={{ textDecoration: 'none', color: 'inherit' }}>
          <Brain size={32} color="var(--accent-cyan)" />
          <h1 style={{ margin: 0, fontSize: '1.5rem' }}>
            <span className="text-gradient">Aether</span> AI
          </h1>
        </Link>

        <nav className="desktop-nav flex items-center gap-4">
          {navLinks.map(link => (
            <Link
              key={link.path}
              to={link.path}
              className="nav-link"
              style={{
                color: location.pathname === link.path ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                textDecoration: 'none',
                fontSize: '0.95rem',
                fontWeight: location.pathname === link.path ? 600 : 400,
                transition: 'color 0.2s ease',
              }}
            >
              {link.label}
            </Link>
          ))}
          <RegimeBadge />
          <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginLeft: '0.5rem' }}>
            Market: <strong style={{ color: `var(--score-${getScoreColor(marketState.overallScore)})` }}>{rec}</strong>
          </span>
        </nav>

        <button
          className="mobile-menu-btn"
          onClick={() => setMenuOpen(!menuOpen)}
          style={{ background: 'none', border: 'none', color: 'var(--text-primary)', cursor: 'pointer', padding: '0.5rem' }}
        >
          {menuOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
      </div>

      {menuOpen && (
        <div className="mobile-dropdown" style={{
          position: 'absolute', top: '100%', left: 0, right: 0,
          background: 'rgba(10, 10, 15, 0.95)', backdropFilter: 'blur(20px)',
          borderBottom: '1px solid var(--glass-border)', padding: '1rem 1.5rem', zIndex: 99,
        }}>
          {navLinks.map(link => (
            <Link key={link.path} to={link.path} onClick={() => setMenuOpen(false)} style={{
              display: 'block', padding: '0.75rem 0',
              color: location.pathname === link.path ? 'var(--accent-cyan)' : 'var(--text-secondary)',
              textDecoration: 'none', fontSize: '1.1rem',
              fontWeight: location.pathname === link.path ? 600 : 400,
              borderBottom: '1px solid var(--glass-border)',
            }}>
              {link.label}
            </Link>
          ))}
          <div style={{ padding: '0.75rem 0', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            Market State: <strong style={{ color: `var(--score-${getScoreColor(marketState.overallScore)})` }}>{rec}</strong>
          </div>
        </div>
      )}
    </header>
  );
}
