/**
 * API client for Aether AI Backend
 * Fetches real market data, news, and AI analysis from FastAPI backend.
 */

const API_BASE = 'http://localhost:8000';

export interface APIAsset {
  id: string;
  name: string;
  category: string;
  icon: string;
  color: string;
  price: number;
  prevPrice: number;
  changePct: number;
  currency: string;
  isFallback: boolean;
  scores: {
    macro: number;
    micro: number;
    sentiment: number;
    tech: number;
  };
  agentDetails?: {
    macro: { reasoning: string; key_factors: string[]; confidence: number; provider: string };
    micro: { reasoning: string; key_factors: string[]; confidence: number; provider: string };
    sentiment: { reasoning: string; key_factors: string[]; confidence: number; provider: string };
    tech: { reasoning: string; key_factors: string[]; confidence: number; provider: string };
  };
  finalScore: number;
  trend: 'up' | 'down' | 'neutral';
  supervisorText: string;
  scenarioData: Array<{ name: string; bull: number; base: number; bear: number }>;
  scenarioProbabilities: { bull: number; base: number; bear: number };
}

export interface APINewsItem {
  id: string;
  title: string;
  source: string;
  time: string;
  timestamp: string;
  sentiment: 'positive' | 'negative' | 'neutral';
  category: string;
  summary: string;
  url: string;
}

export interface APIPortfolio {
  allocations: Array<{
    assetId: string;
    name: string;
    weight: number;
    action: 'buy' | 'sell' | 'hold';
    color: string;
    score: number;
  }>;
  cash: number;
  motivation: string;
}

export interface APIMarketState {
  overallScore: number;
  overallSummary: string;
  lastUpdated: string;
  assetCount: number;
  sectorCount: number;
  newsCount: number;
}

export interface APISector {
  id: string;
  name: string;
  emoji: string;
  description: string;
  examples: string;
  color: string;
  ticker: string;
  price: number;
  changePct: number;
  score: number;
  confidence: number;
  reasoning: string;
  keyDrivers: string[];
  rotationSignal: 'Övervikt' | 'Neutralvikt' | 'Undervikt';
  macroDrivers: string[];
  providerUsed: string;
}

export interface APIRegion {
  id: string;
  name: string;
  flag: string;
  description: string;
  indexName: string;
  color: string;
  ticker: string;
  price: number;
  changePct: number;
  score: number;
  confidence: number;
  reasoning: string;
  keyDrivers: string[];
  allocationSignal: 'Övervikt' | 'Neutralvikt' | 'Undervikt';
  macroDrivers: string[];
  providerUsed: string;
}

export interface APIHealth {
  status: string;
  timestamp: string;
  last_refresh: string | null;
}

class AetherAPI {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl;
  }

  private async fetch<T>(endpoint: string): Promise<T> {
    const response = await fetch(`${this.baseUrl}${endpoint}`);
    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }
    return response.json();
  }

  async getHealth(): Promise<APIHealth> {
    return this.fetch('/api/health');
  }

  async getAssets(): Promise<APIAsset[]> {
    return this.fetch('/api/assets');
  }

  async getAsset(id: string): Promise<APIAsset> {
    return this.fetch(`/api/assets/${id}`);
  }

  async getNews(): Promise<APINewsItem[]> {
    return this.fetch('/api/news');
  }

  async getPortfolio(): Promise<APIPortfolio> {
    return this.fetch('/api/portfolio');
  }

  async getMarketState(): Promise<APIMarketState> {
    return this.fetch('/api/market-state');
  }

  async getSectors(): Promise<APISector[]> {
    return this.fetch('/api/sectors');
  }

  async getRegions(): Promise<APIRegion[]> {
    return this.fetch('/api/regions');
  }

  async getAlerts(minImpact: number = 1): Promise<{ alerts: APIAlert[]; stats: SentinelStats }> {
    return this.fetch(`/api/alerts?min_impact=${minImpact}`);
  }

  async testNotification(): Promise<{ success: boolean; message: string }> {
    const response = await fetch(`${this.baseUrl}/api/alerts/test`, { method: 'POST' });
    return response.json();
  }

  async forceRefresh(): Promise<{ status: string; timestamp: string }> {
    const response = await fetch(`${this.baseUrl}/api/refresh`, { method: 'POST' });
    return response.json();
  }

  async getRegime(): Promise<APIRegimeData> {
    return this.fetch('/api/regime');
  }

  async getCorrelations(period: string = '30d'): Promise<APICorrelationData> {
    return this.fetch(`/api/correlations?period=${period}`);
  }

  async getCorrelationInsights(period: string = '30d'): Promise<{ insights: Array<{ icon: string; title: string; text: string }>; source: string; period: string }> {
    return this.fetch(`/api/correlations/insights?period=${period}`);
  }

  async getCalendar(): Promise<APICalendarData> {
    return this.fetch('/api/calendar');
  }

  async getSignals(): Promise<{ signals: Record<string, APITradeSignal> }> {
    return this.fetch('/api/signals');
  }

  async getOnchain(): Promise<APIOnchainData> {
    return this.fetch('/api/onchain');
  }

  async getRealPortfolio(): Promise<APIRealPortfolio> {
    return this.fetch('/api/portfolio');
  }

  async addPosition(data: { asset_id: string; quantity: number; entry_price: number; asset_name?: string; notes?: string }): Promise<{ id: string }> {
    const response = await fetch(`${this.baseUrl}/api/portfolio/positions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return response.json();
  }

  async deletePosition(id: string): Promise<{ success: boolean }> {
    const response = await fetch(`${this.baseUrl}/api/portfolio/positions/${id}`, { method: 'DELETE' });
    return response.json();
  }

  // ---- Predictive Intelligence (Del 4B + 5) ----

  async getPredictiveSummary(): Promise<any> {
    return this.fetch('/api/predictive/summary');
  }

  async getEventLog(): Promise<any> {
    return this.fetch('/api/predictive/event-log');
  }

  async getUnprocessedEvents(): Promise<any> {
    return this.fetch('/api/predictive/unprocessed-events');
  }

  async runPipeline(): Promise<any> {
    const response = await fetch(`${this.baseUrl}/api/predictive/run-pipeline`, { method: 'POST' });
    return response.json();
  }

  async getActorIntelligence(): Promise<any> {
    return this.fetch('/api/predictive/actor-intelligence');
  }

  async runActorSimulation(event: string, context: string = ''): Promise<any> {
    const response = await fetch(`${this.baseUrl}/api/predictive/actor-simulation?event=${encodeURIComponent(event)}&context=${encodeURIComponent(context)}`, { method: 'POST' });
    return response.json();
  }

  async getConfidence(): Promise<any> {
    return this.fetch('/api/predictive/confidence');
  }

  async getMetaStrategy(): Promise<any> {
    return this.fetch('/api/predictive/meta-strategy');
  }

  async runAdversarialCheck(asset: string, action: string, reasoning: string): Promise<any> {
    const response = await fetch(`${this.baseUrl}/api/predictive/adversarial-check?asset=${encodeURIComponent(asset)}&action=${encodeURIComponent(action)}&reasoning=${encodeURIComponent(reasoning)}`, { method: 'POST' });
    return response.json();
  }

  async getSystemHealth(): Promise<any> {
    return this.fetch('/api/system/health');
  }

  async getAutoStatus(): Promise<any> {
    return this.fetch('/api/predictive/auto-status');
  }

  async getCausalChainsActive(): Promise<any> {
    return this.fetch('/api/predictive/causal-chain/active');
  }

  async getLeadLagNetwork(): Promise<any> {
    return this.fetch('/api/predictive/lead-lag/network');
  }

  async getPipelineHistory(): Promise<any> {
    return this.fetch('/api/predictive/pipeline-history');
  }

  async convexityOptimize(): Promise<any> {
    const response = await fetch(`${this.baseUrl}/api/predictive/convexity-optimize`, { method: 'POST' });
    return response.json();
  }
}

// Intelligence types
export interface APIRegimeData {
  regime: string;
  label: string;
  description: string;
  confidence: number;
  signals: Record<string, any>;
  agent_guidance: Record<string, string>;
  weight_adjustments: Record<string, number>;
  detected_at: string;
}

export interface APICorrelationData {
  matrix: Record<string, Record<string, number>>;
  systemic: {
    regime: string;
    signal_strength: number;
    risk_on_count: number;
    risk_off_count: number;
    details: Record<string, string>;
  };
  notable_pairs: Array<{
    asset_a: string;
    asset_b: string;
    correlation: number;
    strength: string;
  }>;
  calculated_at: string;
}

export interface APICalendarData {
  upcoming: APICalendarEvent[];
  recent: APICalendarEvent[];
  imminent_count: number;
  today_count: number;
  next_high_impact: APICalendarEvent | null;
}

export interface APICalendarEvent {
  key: string;
  name: string;
  description?: string;
  datetime: string;
  date: string;
  time_utc: string;
  hours_until?: number;
  hours_ago?: number;
  impact: number;
  affects_assets: string[];
  category: string;
  urgency?: string;
}

export interface APITradeSignal {
  asset_id: string;
  direction: string;
  strength: string;
  score: number;
  confidence: number;
  recommendation: string;
  current_price: number;
  entry?: { primary: number; ideal: number; note: string };
  stop_loss?: { price: number; pct_from_entry: number; type: string };
  targets?: Array<{ label: string; price: number; pct_from_entry: number }>;
  risk_reward?: { ratio: number; label: string };
  position_sizing?: { max_portfolio_pct: number; volatility_warning: string | null };
  quality?: { stars: number; label: string; factors: string[] };
  atr: number;
  atr_pct: number;
  key_levels?: { support: number; resistance: number };
}

export interface APIOnchainData {
  available: boolean;
  mempool?: { tx_count: number; vsize_mb: number; congestion: string };
  fees?: { fastest: number; hour: number; economy: number; pressure: string };
  hashrate?: { current_eh: number; weekly_change_pct: number; trend: string };
  difficulty?: { progress_pct: number; estimated_change_pct: number; remaining_blocks: number };
  supply?: { total_btc: number; max_supply: number; pct_mined: number; remaining_btc: number };
}

export interface APIRealPortfolio {
  total_value: number;
  total_cost: number;
  total_pnl: number;
  total_pnl_pct: number;
  position_count: number;
  positions: Array<{
    id: string;
    asset_id: string;
    asset_name: string;
    quantity: number;
    entry_price: number;
    current_price: number;
    current_value: number;
    cost_basis: number;
    pnl: number;
    pnl_pct: number;
  }>;
  allocation: Record<string, number>;
  risk_metrics: {
    daily_var_pct?: number;
    weighted_volatility?: number;
    risk_level?: string;
    concentration?: { max_single_pct: number; diversified: boolean };
  };
}

export interface APIAlert {
  id: string;
  title: string;
  source: string;
  time: string;
  impact_score: number;
  category: string;
  affected_assets: string[];
  affected_sectors: string[];
  affected_regions: string[];
  urgency: 'routine' | 'notable' | 'urgent' | 'critical';
  one_liner: string;
  provider: string;
  timestamp: string;
}

export interface SentinelStats {
  total_scanned: number;
  alerts_triggered: number;
  critical_alerts: number;
  last_scan: string | null;
}

export const api = new AetherAPI();
