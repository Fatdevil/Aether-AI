import { useState } from 'react';
import type { Asset } from '../types';
import { getScoreColor, scoreToPercent, getRecommendation } from '../types';
import ScenarioChart from './ScenarioChart';
import SupervisorPanel from './SupervisorPanel';
import TradeSignalPanel from './TradeSignalPanel';
import { OnchainPanel } from './IntelligenceWidgets';
import SentimentChart from './SentimentChart';

interface AssetDetailProps {
  asset: Asset;
  price?: { price: number; changePct: number; currency: string };
}

const analystDescriptions: Record<string, string> = {
  macro: 'Fokuserar på penningpolitik, räntor, likviditet och globala makrotrender.',
  micro: 'Granskar on-chain data, företagsspecifika kassaflöden och utbudsfaktorer.',
  sentiment: 'Skrapar nyheter, X (Twitter), Fear & Greed Index och marknadspositionering.',
  tech: 'Evaluerar stöd/motstånd, RSI, MACD, Bollinger Bands och glidande medelvärden.',
};

const analystNames: Record<string, string> = {
  macro: 'Makro-Analytiker',
  micro: 'Mikro-Analytiker',
  sentiment: 'Sentiment-Analytiker',
  tech: 'Teknisk Analytiker',
};

const analystIcons: Record<string, string> = {
  macro: '🏛️',
  micro: '🔬',
  sentiment: '📰',
  tech: '📊',
};

function AgentCard({ agentKey, score, asset }: { agentKey: string; score: number; asset: Asset }) {
  const [expanded, setExpanded] = useState(false);
  const detail = asset.agentDetails?.[agentKey as keyof NonNullable<typeof asset.agentDetails>];
  const hasDetail = detail && (detail.reasoning || detail.key_factors?.length > 0);

  return (
    <div
      className="glass-panel"
      onClick={() => hasDetail && setExpanded(!expanded)}
      style={{
        padding: '1rem',
        background: 'rgba(255,255,255,0.02)',
        cursor: hasDetail ? 'pointer' : 'default',
        transition: 'all 0.2s ease',
        border: expanded ? '1px solid rgba(139, 92, 246, 0.3)' : '1px solid transparent',
      }}
    >
      {/* Header row */}
      <div className="flex justify-between" style={{ marginBottom: '0.5rem' }}>
        <span style={{ fontWeight: 500, display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <span>{analystIcons[agentKey]}</span>
          {analystNames[agentKey]}
        </span>
        <div className="flex items-center gap-2">
          <span style={{ color: `var(--score-${getScoreColor(score)})`, fontWeight: 700 }}>{score} / 10</span>
          {hasDetail && (
            <span style={{
              fontSize: '0.7rem', transition: 'transform 0.2s',
              transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
              display: 'inline-block',
            }}>▼</span>
          )}
        </div>
      </div>

      {/* Score bar */}
      <div className="score-progress">
        <div className={`score-progress-bar ${getScoreColor(score)}`} style={{ width: scoreToPercent(score) }} />
      </div>

      {/* Collapsed: static description */}
      {!expanded && (
        <p style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)', marginTop: '0.5rem', marginBottom: 0 }}>
          {analystDescriptions[agentKey]}
        </p>
      )}

      {/* Expanded: full analysis */}
      {expanded && detail && (
        <div className="animate-fade-in" style={{ marginTop: '0.75rem' }}>
          {/* AI Reasoning */}
          {detail.reasoning && (
            <div style={{
              padding: '0.7rem 0.85rem', borderRadius: '6px', marginBottom: '0.75rem',
              background: 'rgba(139, 92, 246, 0.05)', borderLeft: '3px solid rgba(139, 92, 246, 0.4)',
            }}>
              <div style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-tertiary)', marginBottom: '0.3rem' }}>
                📝 AI-motivering
              </div>
              <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.7 }}>
                {detail.reasoning}
              </div>
            </div>
          )}

          {/* Key factors */}
          {detail.key_factors && detail.key_factors.length > 0 && (
            <div style={{ marginBottom: '0.75rem' }}>
              <div style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-tertiary)', marginBottom: '0.4rem' }}>
                🔑 Nyckelfaktorer
              </div>
              <div className="flex gap-1" style={{ flexWrap: 'wrap' }}>
                {detail.key_factors.map((factor, i) => (
                  <span key={i} style={{
                    fontSize: '0.72rem', padding: '0.2rem 0.5rem', borderRadius: '4px',
                    background: 'rgba(255,255,255,0.06)', color: 'var(--text-secondary)',
                    border: '1px solid rgba(255,255,255,0.08)',
                  }}>
                    {factor}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Confidence + Provider row */}
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-2">
              <span style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>
                Konfidens: {Math.round(detail.confidence * 100)}%
              </span>
              <div style={{
                width: '50px', height: '4px', borderRadius: '2px',
                background: 'rgba(255,255,255,0.1)', overflow: 'hidden',
              }}>
                <div style={{
                  width: `${detail.confidence * 100}%`, height: '100%', borderRadius: '2px',
                  background: detail.confidence > 0.6 ? 'var(--score-positive)' :
                              detail.confidence > 0.3 ? 'var(--accent-gold)' : 'var(--score-negative)',
                }} />
              </div>
            </div>
            <span style={{
              fontSize: '0.6rem', padding: '0.12rem 0.4rem', borderRadius: '4px',
              background: detail.provider === 'gemini' ? 'rgba(139, 92, 246, 0.2)' : 'rgba(255,255,255,0.06)',
              color: detail.provider === 'gemini' ? '#a78bfa' : 'var(--text-tertiary)',
            }}>
              {detail.provider === 'gemini' ? '🧠 Gemini' : detail.provider === 'rule_based' ? '⚙️ rule-based' : `⚙️ ${detail.provider}`}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

export default function AssetDetail({ asset, price }: AssetDetailProps) {
  const Icon = asset.icon;
  const recommendation = getRecommendation(asset.finalScore);
  const colorClass = getScoreColor(asset.finalScore);

  return (
    <div className="glass-panel" style={{ padding: '2rem', height: '100%' }}>

      {/* Title & Score */}
      <div className="flex justify-between items-start" style={{ marginBottom: '2rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <div className="flex items-center gap-2" style={{ marginBottom: '0.5rem' }}>
            <Icon size={28} color={asset.color} />
            <h2 style={{ fontSize: '1.8rem', margin: 0 }}>{asset.name}</h2>
          </div>
          <div className="flex items-center gap-2" style={{ flexWrap: 'wrap' }}>
            <span className={`badge ${colorClass}`}>{recommendation}</span>
            {price && (
              <span style={{ fontSize: '1rem', color: 'var(--text-secondary)' }}>
                {price.currency}{price.price.toLocaleString('sv-SE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                <span style={{
                  color: price.changePct >= 0 ? 'var(--score-positive)' : 'var(--score-negative)',
                  marginLeft: '0.4rem',
                }}>
                  ({price.changePct >= 0 ? '+' : ''}{price.changePct.toFixed(2)}%)
                </span>
              </span>
            )}
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{
            fontSize: '3rem', fontWeight: 700, lineHeight: '1',
            color: `var(--score-${colorClass})`,
          }}>
            {asset.finalScore > 0 ? '+' : ''}{asset.finalScore.toFixed(1)}
          </div>
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>Viktad AI Poäng</div>
        </div>
      </div>

      {/* AI Models Breakdown - Expandable */}
      <div className="grid grid-cols-2" style={{ gap: '1rem', marginBottom: '2rem' }}>
        {Object.entries(asset.scores).map(([key, score]) => (
          <AgentCard key={key} agentKey={key} score={score} asset={asset} />
        ))}
      </div>

      {/* Sentiment Timeline */}
      <SentimentChart assetId={asset.id} assetName={asset.name} color={asset.color} />

      <ScenarioChart asset={asset} />
      <SupervisorPanel asset={asset} />

      {/* Trade Signal */}
      <TradeSignalPanel assetId={asset.id} />

      {/* On-chain data for BTC */}
      {asset.id === 'btc' && <OnchainPanel />}
    </div>
  );
}
