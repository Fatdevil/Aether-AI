/**
 * API client for Aether AI Backend
 * Fetches real market data, news, and AI analysis from FastAPI backend.
 */

export const API_BASE = import.meta.env.VITE_API_URL || (import.meta.env.DEV ? 'http://localhost:8000' : '');

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
  // Extended fields from enriched news
  tickers?: string[];
  data_source?: string;
  impact?: {
    score: number;
    category: string;
    urgency: string;
    one_liner: string;
    affected_assets: Array<{ id: string; direction: string; strength: string; reason: string }>;
    affected_sectors: Array<{ id: string; direction: string; reason: string }>;
    affected_regions: string[];
    provider: string;
  };
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
  expandedSummary?: string;
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

  // A1 FIX: getRealPortfolio() removed — was duplicate of getPortfolio() with different type.
  // Use getPortfolioRisk() for real positions or getPortfolio() for AI allocation.

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

  async getPredictiveSummary(): Promise<APIPredictiveSummary> {
    return this.fetch('/api/predictive/summary');
  }

  async getEventLog(): Promise<APIEventLog> {
    return this.fetch('/api/predictive/event-log');
  }

  async getUnprocessedEvents(): Promise<APIUnprocessedEvents> {
    return this.fetch('/api/predictive/unprocessed-events');
  }

  async runPipeline(): Promise<APIPipelineResult> {
    const response = await fetch(`${this.baseUrl}/api/predictive/run-pipeline`, { method: 'POST' });
    return response.json();
  }

  async getActorIntelligence(): Promise<APIActorIntelligence> {
    return this.fetch('/api/predictive/actor-intelligence');
  }

  async runActorSimulation(event: string, context: string = ''): Promise<APIActorSimulationResult> {
    const response = await fetch(`${this.baseUrl}/api/predictive/actor-simulation?event=${encodeURIComponent(event)}&context=${encodeURIComponent(context)}`, { method: 'POST' });
    return response.json();
  }

  async getConfidence(): Promise<APIConfidenceData> {
    return this.fetch('/api/predictive/confidence');
  }

  async getMetaStrategy(): Promise<APIMetaStrategy> {
    return this.fetch('/api/predictive/meta-strategy');
  }

  async runAdversarialCheck(asset: string, action: string, reasoning: string): Promise<APIAdversarialResult> {
    const response = await fetch(`${this.baseUrl}/api/predictive/adversarial-check?asset=${encodeURIComponent(asset)}&action=${encodeURIComponent(action)}&reasoning=${encodeURIComponent(reasoning)}`, { method: 'POST' });
    return response.json();
  }

  async getSystemHealth(): Promise<APISystemHealth> {
    return this.fetch('/api/system/health');
  }

  async getAutoStatus(): Promise<APIAutoStatus> {
    return this.fetch('/api/predictive/auto-status');
  }

  async getCausalChainsActive(): Promise<APICausalChains> {
    return this.fetch('/api/predictive/causal-chain/active');
  }

  async getLeadLagNetwork(): Promise<APILeadLagNetwork> {
    return this.fetch('/api/predictive/lead-lag/network');
  }

  async getPipelineHistory(): Promise<APIPipelineHistory> {
    return this.fetch('/api/predictive/pipeline-history');
  }

  async convexityOptimize(): Promise<APIConvexityResult> {
    const response = await fetch(`${this.baseUrl}/api/predictive/convexity-optimize`, { method: 'POST' });
    return response.json();
  }

  async getConvexPositions(): Promise<APIConvexPositions> {
    return this.fetch('/api/predictive/event-tree/convex-positions');
  }

  // -- Del 3: Operational Tools --
  async getTaxComparison(holdings: Array<{ asset_id: string; weight: number }>, totalIskValue: number = 0): Promise<APITaxComparison> {
    const response = await fetch(`${this.baseUrl}/api/tax-comparison`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ holdings, total_isk_value: totalIskValue }),
    });
    return response.json();
  }

  async getCurrencyHedge(weights: Record<string, number>): Promise<APICurrencyHedge> {
    const response = await fetch(`${this.baseUrl}/api/currency-hedge`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ portfolio_weights: weights }),
    });
    return response.json();
  }

  async shouldRebalance(current: Record<string, number>, target: Record<string, number>, regimeChanged: boolean = false, portfolioValue: number = 0): Promise<APIRebalanceResult> {
    const response = await fetch(`${this.baseUrl}/api/should-rebalance`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ current_weights: current, target_weights: target, regime_changed: regimeChanged, portfolio_value: portfolioValue }),
    });
    return response.json();
  }

  async getDrawdownRecovery(drawdownPct: number, annualReturn: number = 0.08, volatility: number = 0.12): Promise<APIDrawdownRecovery> {
    return this.fetch(`/api/drawdown-recovery?drawdown_pct=${drawdownPct}&annual_return=${annualReturn}&volatility=${volatility}`);
  }

  async getCostSummary(): Promise<APICostSummary> {
    return this.fetch('/api/cost-summary');
  }

  async getNarratives(): Promise<APINarratives> {
    return this.fetch('/api/predictive/narratives');
  }

  // ---- Alpha vs Omega: Dual Portfolio ----

  async getDualPortfolio(): Promise<APIDualPortfolio> {
    return this.fetch('/api/portfolio/dual');
  }

  async getScenarios(): Promise<APIScenarios> {
    return this.fetch('/api/portfolio/scenarios');
  }

  async refreshScenarios(): Promise<{ status: string }> {
    const response = await fetch(`${this.baseUrl}/api/portfolio/scenarios/refresh`, { method: 'POST' });
    return response.json();
  }

  // ---- Core-Satellite Portfolio ----

  async getCoreSatellite(portfolioValue: number = 700000, broker: string = 'avanza'): Promise<APICoreSatellite> {
    return this.fetch(`/api/core-satellite?portfolio_value=${portfolioValue}&broker=${broker}`);
  }

  // ---- Price History (TradingView charts) ----

  async getPriceHistory(assetId: string, period: string = '3mo'): Promise<APIPriceHistory> {
    return this.fetch(`/api/prices/history/${assetId}?period=${period}`);
  }

  // ---- Daily Brief (Opus-powered) ----

  async getLatestBrief(type?: string): Promise<APIBrief> {
    const url = type ? `/api/brief/latest?type=${type}` : '/api/brief/latest';
    return this.fetch(url);
  }

  async generateBrief(type: string = 'morning'): Promise<APIBrief> {
    const response = await fetch(`${this.baseUrl}/api/brief/generate?type=${type}`, { method: 'POST' });
    return response.json();
  }

  async getBriefHistory(limit: number = 14): Promise<APIBriefHistory> {
    return this.fetch(`/api/brief/history?limit=${limit}`);
  }
}

// Intelligence types
export interface APIRegimeData {
  regime: string;
  label: string;
  description: string;
  confidence: number;
  signals: Record<string, { value: number; signal: string; description?: string }>;
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

// ---- Predictive Intelligence Types ----

export interface APIPredictiveSummary {
  predictions: Array<{
    asset_id: string;
    predicted_move: number;
    confidence: number;
    reasoning: string;
    timeframe: string;
  }>;
  model_version: string;
  generated_at: string;
}

export interface APIEventLog {
  events: Array<{
    id: string;
    event_type: string;
    description: string;
    impact_score: number;
    affected_assets: string[];
    timestamp: string;
    processed: boolean;
  }>;
  count: number;
}

export interface APIUnprocessedEvents {
  events: Array<{
    id: string;
    event_type: string;
    description: string;
    timestamp: string;
  }>;
  count: number;
}

export interface APIPipelineResult {
  status: string;
  layers_completed: number;
  duration_seconds: number;
  timestamp: string;
  assets_analyzed: number;
}

export interface APIActorIntelligence {
  actors: Array<{
    name: string;
    type: string;
    influence_score: number;
    recent_actions: string[];
    market_impact: string;
  }>;
}

export interface APIActorSimulationResult {
  scenario: string;
  impact_analysis: string;
  affected_assets: Array<{ asset_id: string; expected_impact: number }>;
  confidence: number;
}

export interface APIConfidenceData {
  assets: Record<string, {
    raw_confidence: number;
    calibrated_confidence: number;
    adjustment: number;
    historical_accuracy: number;
  }>;
  model_stats: {
    total_predictions: number;
    accuracy_pct: number;
    calibration_score: number;
  };
}

export interface APIMetaStrategy {
  weights: Record<string, number>;
  reasoning: string;
  regime_adapted: boolean;
  performance_score: number;
}

export interface APIAdversarialResult {
  challenge: string;
  counter_arguments: string[];
  risk_factors: string[];
  adjusted_confidence: number;
  verdict: string;
}

export interface APISystemHealth {
  status: string;
  uptime_seconds: number;
  memory_mb: number;
  api_calls_today: number;
  last_pipeline_run: string | null;
  database_status: string;
  components: Record<string, { status: string; latency_ms?: number }>;
}

export interface APIAutoStatus {
  enabled: boolean;
  interval_hours: number;
  last_run: string | null;
  next_run: string | null;
  run_count: number;
}

export interface APICausalChains {
  active_chains: Array<{
    id: string;
    trigger_event: string;
    chain_steps: Array<{ description: string; probability: number; timeframe: string }>;
    affected_assets: string[];
    status: string;
    created_at: string;
  }>;
  count: number;
}

export interface APILeadLagNetwork {
  nodes: Array<{ id: string; label: string; category: string }>;
  edges: Array<{ source: string; target: string; lag_days: number; correlation: number }>;
}

export interface APIPipelineHistory {
  history: Array<{
    timestamp: string;
    duration_seconds: number;
    layers_completed: number;
    assets_analyzed: number;
    status: string;
  }>;
  total_runs: number;
}

export interface APIConvexityResult {
  positions: Array<{
    asset_id: string;
    type: string;
    expected_payoff: number;
    risk: number;
    convexity_score: number;
  }>;
  total_expected_return: number;
}

export interface APIConvexPositions {
  positions: Array<{
    asset_id: string;
    position_type: string;
    entry_condition: string;
    potential_return: number;
    risk_pct: number;
  }>;
}

// ---- Operational Tools Types ----

export interface APITaxComparison {
  isk: { tax_cost: number; effective_rate: number; explanation: string };
  kf: { tax_cost: number; effective_rate: number; explanation: string };
  recommendation: string;
  savings: number;
}

export interface APICurrencyHedge {
  exposure: Record<string, number>;
  hedge_recommendations: Array<{
    currency: string;
    exposure_pct: number;
    hedge_pct: number;
    instrument: string;
  }>;
  total_foreign_exposure: number;
}

export interface APIRebalanceResult {
  should_rebalance: boolean;
  urgency: string;
  drift_pct: number;
  cost_estimate: number;
  trades: Array<{ asset_id: string; action: 'buy' | 'sell'; weight_change: number }>;
  reasoning: string;
}

export interface APIDrawdownRecovery {
  drawdown_pct: number;
  expected_recovery_months: number;
  scenarios: Array<{ label: string; months: number; probability: number }>;
  historical_reference: string;
}

export interface APICostSummary {
  today: number;
  this_week: number;
  this_month: number;
  total: number;
  by_provider: Record<string, { calls: number; cost: number }>;
}

export interface APINarratives {
  narratives: Array<{
    id: string;
    title: string;
    summary: string;
    impact: string;
    affected_assets: string[];
    confidence: number;
    timestamp: string;
  }>;
}

// ---- Dual Portfolio Types ----

export interface APIDualPortfolio {
  alpha: {
    name: string;
    allocations: Array<{ asset_id: string; name: string; weight: number; score: number }>;
    expected_return: number;
    risk_level: string;
  };
  omega: {
    name: string;
    allocations: Array<{ asset_id: string; name: string; weight: number; score: number }>;
    expected_return: number;
    risk_level: string;
  };
  scenarios?: APIScenarios;
}

export interface APIScenarios {
  scenarios: Array<{
    name: string;
    probability: number;
    description: string;
    alpha_return: number;
    omega_return: number;
  }>;
  generated_at: string;
}

// ---- Core-Satellite Types ----

export interface APICoreSatellite {
  core: Array<{ asset_id: string; name: string; weight: number; type: string; ticker: string }>;
  satellite: Array<{ asset_id: string; name: string; weight: number; conviction: number; ticker: string }>;
  core_pct: number;
  satellite_pct: number;
  total_value: number;
  broker: string;
}

// ---- Price History Types ----

export interface APIPriceHistory {
  candles: Array<{
    date: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
  }>;
  asset_id: string;
  period: string;
}

// ---- Brief Types ----

export interface APIBrief {
  type: string;
  content: {
    headline: string;
    summary: string;
    key_points: string[];
    market_outlook: string;
    actionable_insights: string[];
  };
  generated_at: string;
  model_used: string;
}

export interface APIBriefHistory {
  briefs: Array<{
    type: string;
    date: string;
    headline: string;
    generated_at: string;
  }>;
  count: number;
}

export const api = new AetherAPI();
