import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import { useLiveData } from './hooks/useLiveData';
import { useNotifications } from './hooks/useNotifications';
import Header from './components/Header';
import MobileNav from './components/MobileNav';
import StatusBar from './components/StatusBar';
import Dashboard from './pages/Dashboard';
import MyPortfolioPage from './pages/MyPortfolioPage';
import NewsPage from './pages/NewsPage';
import SectorsPage from './pages/SectorsPage';
import RegionsPage from './pages/RegionsPage';
import PerformancePage from './pages/PerformancePage';
import BacktestPage from './pages/BacktestPage';
import PredictivePage from './pages/PredictivePage';
import ToolsPage from './pages/ToolsPage';
import ChatPanel from './components/ChatPanel';
import InvestorDemo from './pages/InvestorDemo';

import GlobalOverviewPage from './pages/GlobalOverviewPage';
import './index.css';

export default function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
}

function AppContent() {
  const liveData = useLiveData();
  useNotifications();
  const location = useLocation();

  // Investor demo renders standalone (no app shell)
  if (location.pathname === '/investor') {
    return <InvestorDemo />;
  }

  return (
    <div className="app-container">
      <Header marketState={liveData.marketState} />
      <StatusBar isLive={liveData.isLive} isLoading={liveData.isLoading} error={liveData.error} onRefresh={liveData.refresh} />
      <Routes>
        <Route path="/" element={<Dashboard assets={liveData.assets} marketState={liveData.marketState} prices={liveData.prices} />} />
        <Route path="/sectors" element={<SectorsPage sectors={liveData.sectors} />} />
        <Route path="/regions" element={<RegionsPage regions={liveData.regions} />} />
        <Route path="/portfolio" element={<MyPortfolioPage />} />
        <Route path="/news" element={<NewsPage news={liveData.news} />} />
        <Route path="/performance" element={<PerformancePage />} />
        <Route path="/backtest" element={<BacktestPage />} />
        <Route path="/predict" element={<PredictivePage />} />
        <Route path="/tools" element={<ToolsPage />} />
        <Route path="/global" element={<GlobalOverviewPage />} />
      </Routes>
      <MobileNav />
      <ChatPanel />
    </div>
  );
}
