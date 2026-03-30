import { LayoutDashboard, Search, Briefcase, Brain } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';

export default function MobileNav() {
  const location = useLocation();

  const tabs = [
    { path: '/', label: 'Marknad', icon: LayoutDashboard },
    { path: '/analysis', label: 'Analys', icon: Search },
    { path: '/portfolio', label: 'Portfölj', icon: Briefcase },
    { path: '/insights', label: 'AI', icon: Brain },
  ];

  return (
    <nav className="mobile-bottom-nav">
      {tabs.map(tab => {
        const isActive = location.pathname === tab.path;
        return (
          <Link
            key={tab.path}
            to={tab.path}
            style={{
              color: isActive ? 'var(--accent-cyan)' : 'var(--text-tertiary)',
              textDecoration: 'none',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '0.25rem',
              fontSize: '0.65rem',
              fontWeight: isActive ? 600 : 400,
              transition: 'color 0.2s ease',
              flex: 1,
              padding: '0.5rem 0',
              position: 'relative',
            }}
          >
            {isActive && (
              <div style={{
                position: 'absolute',
                top: 0,
                left: '25%',
                right: '25%',
                height: '2px',
                background: 'var(--accent-cyan)',
                borderRadius: '0 0 2px 2px',
              }} />
            )}
            <tab.icon size={22} strokeWidth={isActive ? 2.5 : 1.5} />
            <span>{tab.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
