import { LayoutDashboard, Factory, Globe2, Briefcase, Newspaper } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';

export default function MobileNav() {
  const location = useLocation();

  const tabs = [
    { path: '/', label: 'Dashboard', icon: LayoutDashboard },
    { path: '/sectors', label: 'Sektorer', icon: Factory },
    { path: '/regions', label: 'Regioner', icon: Globe2 },
    { path: '/portfolio', label: 'Portfölj', icon: Briefcase },
    { path: '/news', label: 'Nyheter', icon: Newspaper },
  ];

  return (
    <nav className="mobile-bottom-nav">
      {tabs.map(tab => {
        const isActive = location.pathname === tab.path;
        return (
          <Link
            key={tab.path}
            to={tab.path}
            className="mobile-bottom-nav-item"
            style={{
              color: isActive ? 'var(--accent-cyan)' : 'var(--text-tertiary)',
              textDecoration: 'none',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '0.2rem',
              fontSize: '0.65rem',
              fontWeight: isActive ? 600 : 400,
              transition: 'color 0.2s ease',
              flex: 1,
              padding: '0.4rem 0',
            }}
          >
            <tab.icon size={20} strokeWidth={isActive ? 2.5 : 1.5} />
            <span>{tab.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
