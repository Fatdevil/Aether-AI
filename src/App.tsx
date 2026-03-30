import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Component, type ReactNode } from 'react';
import { useLiveData } from './hooks/useLiveData';
import { useNotifications } from './hooks/useNotifications';
import Header from './components/Header';
import MobileNav from './components/MobileNav';
import StatusBar from './components/StatusBar';
import Dashboard from './pages/Dashboard';
import AnalysisPage from './pages/AnalysisPage';
import MyPortfolioPage from './pages/MyPortfolioPage';
import InsightsPage from './pages/InsightsPage';
import ChatPanel from './components/ChatPanel';

import './index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

/* ── React Error Boundary (resets on key change) ── */
class ErrorBoundary extends Component<{ children: ReactNode; resetKey: string }, { hasError: boolean; error: string }> {
  constructor(props: { children: ReactNode; resetKey: string }) {
    super(props);
    this.state = { hasError: false, error: '' };
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error: error.message };
  }
  componentDidUpdate(prevProps: { resetKey: string }) {
    if (prevProps.resetKey !== this.props.resetKey && this.state.hasError) {
      this.setState({ hasError: false, error: '' });
    }
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="container" style={{ padding: '3rem 1.25rem', textAlign: 'center' }}>
          <div className="glass-panel" style={{ padding: '2rem', maxWidth: '500px', margin: '0 auto' }}>
            <p style={{ fontSize: '1.2rem', margin: '0 0 0.5rem' }}>⚠️ Något gick fel</p>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', margin: '0 0 1rem' }}>
              {this.state.error || 'Ett oväntat fel inträffade'}
            </p>
            <button
              onClick={() => { this.setState({ hasError: false, error: '' }); window.location.href = '/'; }}
              className="button-primary"
              style={{ padding: '0.6rem 1.5rem' }}
            >
              Tillbaka till Marknad
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppContent />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

function AppContent() {
  const liveData = useLiveData();
  const location = useLocation();
  useNotifications();

  return (
    <div className="app-container">
      <Header marketState={liveData.marketState} />
      <StatusBar isLive={liveData.isLive} isLoading={liveData.isLoading} error={liveData.error} onRefresh={liveData.refresh} />
      <ErrorBoundary resetKey={location.pathname}>
        <Routes>
          <Route path="/" element={<Dashboard assets={liveData.assets} marketState={liveData.marketState} prices={liveData.prices} />} />
          <Route path="/analysis" element={<AnalysisPage />} />
          <Route path="/portfolio" element={<MyPortfolioPage />} />
          <Route path="/insights" element={<InsightsPage />} />
        </Routes>
      </ErrorBoundary>
      <MobileNav />
      <ChatPanel />
    </div>
  );
}

