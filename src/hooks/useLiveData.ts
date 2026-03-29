/**
 * useLiveData — Powered by TanStack Query
 *
 * Each data source has its own query with appropriate refresh interval:
 *   - Prices (assets):  30s  (most time-sensitive)
 *   - News:             60s  (frequent updates)
 *   - Market state:    120s  (moderate)
 *   - Portfolio:       120s  (moderate)
 *   - Sectors/Regions: 300s  (slow-changing)
 *
 * Benefits over the old manual fetch:
 *   - Automatic deduplication (2 components using same data = 1 API call)
 *   - Smart caching (staleTime prevents redundant requests)
 *   - Background refetch (data updates without loading spinners)
 *   - Retry logic (3 retries with exponential backoff)
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import type { APIAsset, APISector, APIRegion } from '../api/client';
import { assets as mockAssets, newsItems as mockNews, portfolioAllocations as mockPortfolio, globalMarketState as mockMarketState } from '../data/mockData';
import type { Asset, NewsItem } from '../types';
import { Bitcoin, Globe, Coins, Droplet, DollarSign, LineChart, Gem, BarChart } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

const ICON_LOOKUP: Record<string, LucideIcon> = {
  Bitcoin, Globe, Coins, Droplet, DollarSign, LineChart, Gem, BarChart,
  Circle: Globe,
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

// Preferred dashboard order
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

// -------------------------------------------------------------------
// Individual query hooks (reusable by any component)
// -------------------------------------------------------------------

export function useAssetsQuery() {
  return useQuery({
    queryKey: ['assets'],
    queryFn: () => api.getAssets(),
    staleTime: 30_000,       // 30s
    refetchInterval: 30_000, // Auto-refresh every 30s
    retry: 2,
  });
}

export function useNewsQuery() {
  return useQuery({
    queryKey: ['news'],
    queryFn: () => api.getNews(),
    staleTime: 60_000,
    refetchInterval: 60_000,
    retry: 2,
  });
}

export function useMarketStateQuery() {
  return useQuery({
    queryKey: ['market-state'],
    queryFn: () => api.getMarketState(),
    staleTime: 120_000,
    refetchInterval: 120_000,
    retry: 2,
  });
}

export function usePortfolioQuery() {
  return useQuery({
    queryKey: ['portfolio'],
    queryFn: () => api.getPortfolio(),
    staleTime: 120_000,
    refetchInterval: 120_000,
    retry: 2,
  });
}

export function useSectorsQuery() {
  return useQuery({
    queryKey: ['sectors'],
    queryFn: () => api.getSectors(),
    staleTime: 300_000,
    refetchInterval: 300_000,
    retry: 2,
  });
}

export function useRegionsQuery() {
  return useQuery({
    queryKey: ['regions'],
    queryFn: () => api.getRegions(),
    staleTime: 300_000,
    refetchInterval: 300_000,
    retry: 2,
  });
}

// -------------------------------------------------------------------
// useLiveData — composite hook (backward-compatible with existing code)
// -------------------------------------------------------------------

export function useLiveData(): LiveData {
  const queryClient = useQueryClient();

  const assetsQ = useAssetsQuery();
  const newsQ = useNewsQuery();
  const marketQ = useMarketStateQuery();
  const portfolioQ = usePortfolioQuery();
  const sectorsQ = useSectorsQuery();
  const regionsQ = useRegionsQuery();

  // Derive values from queries (with mock fallbacks)
  const isLive = assetsQ.isSuccess;
  const isLoading = assetsQ.isLoading && !assetsQ.data;
  const error = assetsQ.isError ? 'Backend offline – visar demodata' : null;

  // Assets
  const assets: Asset[] = assetsQ.data
    ? sortAssets(assetsQ.data.map(apiAssetToAsset))
    : mockAssets;

  // Prices (derived from assets)
  const prices: Record<string, { price: number; changePct: number; currency: string }> = {};
  if (assetsQ.data) {
    assetsQ.data.forEach(a => {
      prices[a.id] = { price: a.price, changePct: a.changePct, currency: a.currency };
    });
  }

  // News
  const news: NewsItem[] = newsQ.data
    ? newsQ.data.map(n => ({
        id: n.id,
        title: n.title,
        source: n.source,
        time: n.time,
        sentiment: n.sentiment,
        category: n.category,
        summary: n.summary,
        ...((n as any).impact ? { impact: (n as any).impact } : {}),
      }))
    : mockNews;

  // Portfolio
  const portfolio = portfolioQ.data
    ? {
        allocations: portfolioQ.data.allocations,
        cash: portfolioQ.data.cash,
        motivation: portfolioQ.data.motivation,
      }
    : {
        allocations: mockPortfolio.map(p => ({ ...p, score: 0 })),
        cash: 100 - mockPortfolio.reduce((s, a) => s + a.weight, 0),
        motivation: 'Risk-on-portfölj med kvalitetsfilter.',
      };

  // Market state
  const marketState = marketQ.data
    ? {
        overallScore: marketQ.data.overallScore,
        overallSummary: marketQ.data.overallSummary,
        expandedSummary: marketQ.data.expandedSummary,
        lastUpdated: marketQ.data.lastUpdated,
      }
    : {
        overallScore: mockMarketState.overallScore,
        overallSummary: mockMarketState.overallSummary,
        lastUpdated: mockMarketState.lastUpdated,
      };

  // Sectors & Regions
  const sectors = sectorsQ.data || [];
  const regions = regionsQ.data || [];

  // Manual refresh — invalidates all queries
  const refresh = async () => {
    await queryClient.invalidateQueries();
  };

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
    refresh,
  };
}
