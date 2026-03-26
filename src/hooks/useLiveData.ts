/**
 * Custom hook for fetching live data from the backend API.
 * Falls back to mock data if the backend is unreachable.
 */

import { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';
import type { APIAsset, APISector, APIRegion } from '../api/client';
import { assets as mockAssets, newsItems as mockNews, portfolioAllocations as mockPortfolio, globalMarketState as mockMarketState } from '../data/mockData';
import type { Asset, NewsItem } from '../types';
import { Bitcoin, Globe, Coins, Droplet, DollarSign, LineChart, Gem, BarChart } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

const ICON_LOOKUP: Record<string, LucideIcon> = {
  Bitcoin, Globe, Coins, Droplet, DollarSign, LineChart, Gem, BarChart,
  Circle: Globe, // Fallback
};

function apiAssetToAsset(a: APIAsset): Asset {
  return {
    id: a.id,
    name: a.name,
    category: a.category,
    icon: ICON_LOOKUP[a.icon] || Globe,
    color: a.color,
    scores: a.scores,
    agentDetails: a.agentDetails,
    finalScore: a.finalScore,
    trend: a.trend,
    supervisorText: a.supervisorText,
    scenarioData: a.scenarioData,
    scenarioProbabilities: a.scenarioProbabilities,
  };
}

export interface LiveData {
  assets: Asset[];
  news: NewsItem[];
  portfolio: {
    allocations: Array<{
      assetId: string;
      name: string;
      weight: number;
      action: 'buy' | 'sell' | 'hold';
      color: string;
      score?: number;
    }>;
    cash: number;
    motivation: string;
  };
  marketState: {
    overallScore: number;
    overallSummary: string;
    expandedSummary?: string;
    lastUpdated: string;
  };
  prices: Record<string, { price: number; changePct: number; currency: string }>;
  sectors: APISector[];
  regions: APIRegion[];
  isLive: boolean;
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

// Preferred dashboard order: Aktier → Krypto → Råvaror → Makro
const ASSET_ORDER: string[] = [
  'global-equity', 'sp500', 'btc', 'gold', 'oil', 'silver', 'us10y', 'eurusd',
];

function sortAssets(assets: Asset[]): Asset[] {
  return [...assets].sort((a, b) => {
    const ai = ASSET_ORDER.indexOf(a.id);
    const bi = ASSET_ORDER.indexOf(b.id);
    return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
  });
}

export function useLiveData(): LiveData {
  const [assets, setAssets] = useState<Asset[]>(mockAssets);
  const [news, setNews] = useState<NewsItem[]>(mockNews);
  const [portfolio, setPortfolio] = useState<LiveData['portfolio']>({
    allocations: mockPortfolio.map(p => ({ ...p, score: 0 })),
    cash: 100 - mockPortfolio.reduce((s, a) => s + a.weight, 0),
    motivation: 'Risk-on-portfölj med kvalitetsfilter.',
  });
  const [marketState, setMarketState] = useState<LiveData['marketState']>({
    overallScore: mockMarketState.overallScore,
    overallSummary: mockMarketState.overallSummary,
    lastUpdated: mockMarketState.lastUpdated,
  });
  const [prices, setPrices] = useState<Record<string, { price: number; changePct: number; currency: string }>>({});
  const [sectors, setSectors] = useState<APISector[]>([]);
  const [regions, setRegions] = useState<APIRegion[]>([]);
  const [isLive, setIsLive] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      // Try to reach backend
      const [apiAssets, apiNews, apiPortfolio, apiMarketState, apiSectors, apiRegions] = await Promise.all([
        api.getAssets(),
        api.getNews(),
        api.getPortfolio(),
        api.getMarketState(),
        api.getSectors(),
        api.getRegions(),
      ]);

      // Convert API assets to frontend Asset type, then sort
      const convertedAssets = sortAssets(apiAssets.map(apiAssetToAsset));
      setAssets(convertedAssets);

      // News - pass through all fields including impact data
      setNews(apiNews.map(n => ({
        id: n.id,
        title: n.title,
        source: n.source,
        time: n.time,
        sentiment: n.sentiment,
        category: n.category,
        summary: n.summary,
        ...( (n as any).impact ? { impact: (n as any).impact } : {}),
      })));

      // Portfolio
      setPortfolio({
        allocations: apiPortfolio.allocations,
        cash: apiPortfolio.cash,
        motivation: apiPortfolio.motivation,
      });

      // Market state
      setMarketState({
        overallScore: apiMarketState.overallScore,
        overallSummary: apiMarketState.overallSummary,
        expandedSummary: apiMarketState.expandedSummary,
        lastUpdated: apiMarketState.lastUpdated,
      });

      // Extract prices
      const priceMap: Record<string, { price: number; changePct: number; currency: string }> = {};
      apiAssets.forEach(a => {
        priceMap[a.id] = { price: a.price, changePct: a.changePct, currency: a.currency };
      });
      setPrices(priceMap);

      // Sectors
      setSectors(apiSectors);

      // Regions
      setRegions(apiRegions);

      setIsLive(true);
      setError(null);
    } catch (err) {
      console.warn('Backend not reachable, using mock data:', err);
      setIsLive(false);
      setError('Backend offline – visar demodata');
      // Keep mock data as fallback (already set in initial state)
    }
    setIsLoading(false);
  }, []);

  useEffect(() => {
    fetchData();

    // Auto-refresh every 5 minutes if live
    const interval = setInterval(() => {
      if (isLive) fetchData();
    }, 300000);

    return () => clearInterval(interval);
  }, [fetchData]);

  return {
    assets,
    news,
    portfolio,
    marketState,
    prices,
    sectors,
    regions,
    isLive,
    isLoading,
    error,
    refresh: fetchData,
  };
}
