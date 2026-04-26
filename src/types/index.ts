import type { LucideIcon } from 'lucide-react';

export interface AIScores {
  macro: number;
  micro: number;
  sentiment: number;
  tech: number;
}

export interface AgentDetail {
  reasoning: string;
  key_factors: string[];
  confidence: number;
  provider: string;
}

export interface ScenarioPoint {
  name: string;
  bull: number;
  base: number;
  bear: number;
}

export interface ScenarioNarratives {
  bull: string;
  base: string;
  bear: string;
}

export interface ScenarioDrivers {
  bull: string[];
  base: string[];
  bear: string[];
}

export interface Asset {
  id: string;
  name: string;
  category: string;
  icon: LucideIcon;
  scores: AIScores;
  agentDetails?: {
    macro: AgentDetail;
    micro: AgentDetail;
    sentiment: AgentDetail;
    tech: AgentDetail;
  };
  finalScore: number;
  trend: 'up' | 'down' | 'neutral';
  color: string;
  supervisorText: string;
  scenarioData: ScenarioPoint[];
  scenarioProbabilities: {
    bull: number;
    base: number;
    bear: number;
  };
  // Metadata: when and by which model
  analyzedAt?: string;          // ISO timestamp from backend
  providerUsed?: string;        // Supervisor model (e.g. openrouter/anthropic/claude-opus-4.6)
  providersUsed?: string[];     // All models used across agents
  // Level 1+ scenario enrichment
  scenarioNarratives?: ScenarioNarratives;
  scenarioDrivers?: ScenarioDrivers;
  scenarioWorstCasePct?: number;
  scenarioLevel?: string;
  // Level 1.5: trigger conditions
  scenarioKeyTrigger?: string;
  scenarioWorstCaseCatalyst?: string;
}


export interface NewsItem {
  id: string;
  title: string;
  source: string;
  time: string;
  sentiment: 'positive' | 'negative' | 'neutral';
  category: string;
  summary: string;
  url?: string;
  // Extended API fields
  tickers?: string[];
  data_source?: string;
  impact?: {
    score: number;
    category: string;
    urgency: string;
    one_liner: string;
    affected_assets: Array<{ id: string; direction: 'up' | 'down' | 'mixed'; strength: 'weak' | 'moderate' | 'strong'; reason: string }>;
    affected_sectors: Array<{ id: string; direction: 'up' | 'down' | 'mixed'; reason: string }>;
    affected_regions: string[];
    provider: string;
  };
}

export interface PortfolioAllocation {
  assetId: string;
  name: string;
  weight: number;
  action: 'buy' | 'sell' | 'hold';
  color: string;
}

export type RecommendationLevel = 'Starkt Köp' | 'Köp' | 'Neutral' | 'Sälj' | 'Starkt Sälj';

export function getRecommendation(score: number): RecommendationLevel {
  if (score >= 6) return 'Starkt Köp';
  if (score >= 3) return 'Köp';
  if (score >= -3) return 'Neutral';
  if (score >= -6) return 'Sälj';
  return 'Starkt Sälj';
}

export function getScoreColor(score: number): 'positive' | 'negative' | 'neutral' {
  if (score >= 4) return 'positive';
  if (score <= -4) return 'negative';
  return 'neutral';
}

export function scoreToPercent(score: number): string {
  return `${(Math.abs(score) / 10) * 100}%`;
}
