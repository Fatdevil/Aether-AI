import { useState, useEffect } from 'react';
import { XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Area, AreaChart } from 'recharts';

// Map Aether asset IDs to Marketaux symbols
const ASSET_SYMBOL_MAP: Record<string, string[]> = {
  'btc': ['BTC', 'CC:BTC'],
  'gold': ['XAU', 'GLD'],
  'silver': ['XAG', 'SLV'],
  'oil': ['CL', 'BZ'],
  'sp500': ['SPY', 'SPX'],
  'global-equity': ['ACWI', 'VT'],
  'eurusd': ['EURUSD'],
  'us10y': ['TNX', 'TLT'],
};

interface SentimentPoint {
  date: string;
  sentiment_avg: number;
  mentions: number;
}

interface SentimentChartProps {
  assetId: string;
  assetName: string;
  color: string;
}

export default function SentimentChart({ assetId, assetName, color }: SentimentChartProps) {
  const [data, setData] = useState<SentimentPoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const symbols = ASSET_SYMBOL_MAP[assetId] || [assetId.toUpperCase()];
    const symbolStr = symbols.join(',');

    fetch(`http://localhost:8000/api/sentiment-stats?symbols=${symbolStr}&days=14`)
      .then(r => r.json())
      .then(result => {
        // Merge data from all matching symbols
        const merged: Record<string, SentimentPoint> = {};
        const stats = result.stats || {};

        for (const sym of Object.keys(stats)) {
          for (const point of stats[sym]) {
            const key = point.date;
            if (!merged[key]) {
              merged[key] = { date: key, sentiment_avg: 0, mentions: 0 };
            }
            merged[key].sentiment_avg += point.sentiment_avg;
            merged[key].mentions += point.mentions;
          }
        }

        // Normalize sentiment by number of symbols that contributed
        const symCount = Object.keys(stats).length || 1;
        const points = Object.values(merged)
          .map(p => ({
            ...p,
            sentiment_avg: Number((p.sentiment_avg / symCount).toFixed(3)),
          }))
          .sort((a, b) => a.date.localeCompare(b.date));

        setData(points);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [assetId]);

  if (loading) {
    return (
      <div style={{ padding: '1rem', fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>
        Laddar sentimentdata...
      </div>
    );
  }

  if (data.length < 2) {
    return null; // Not enough data to show a chart
  }

  const minSentiment = Math.min(...data.map(d => d.sentiment_avg));
  const maxSentiment = Math.max(...data.map(d => d.sentiment_avg));
  const latestSentiment = data[data.length - 1]?.sentiment_avg || 0;

  return (
    <div style={{ marginBottom: '1.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
        <h4 style={{ margin: 0, fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          📰 Nyhetssentiment ({assetName})
        </h4>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{
            fontSize: '0.75rem', fontWeight: 700,
            color: latestSentiment > 0.1 ? '#10b981' : latestSentiment < -0.1 ? '#ef4444' : 'var(--text-secondary)',
          }}>
            {latestSentiment > 0 ? '+' : ''}{(latestSentiment * 100).toFixed(0)}%
          </span>
          <span style={{ fontSize: '0.6rem', color: 'var(--text-tertiary)' }}>senaste</span>
        </div>
      </div>

      <div style={{
        background: 'rgba(0,0,0,0.15)', borderRadius: '8px', padding: '0.5rem 0',
        border: '1px solid rgba(255,255,255,0.04)',
      }}>
        <ResponsiveContainer width="100%" height={140}>
          <AreaChart data={data} margin={{ top: 5, right: 15, bottom: 5, left: -15 }}>
            <defs>
              <linearGradient id={`sentGrad-${assetId}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity={0.3} />
                <stop offset="100%" stopColor={color} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
            <XAxis
              dataKey="date"
              tick={{ fill: 'var(--text-tertiary)', fontSize: 9 }}
              stroke="rgba(255,255,255,0.06)"
              tickFormatter={(val: string) => val.slice(5)} // MM-DD
            />
            <YAxis
              tick={{ fill: 'var(--text-tertiary)', fontSize: 9 }}
              stroke="rgba(255,255,255,0.06)"
              domain={[Math.min(minSentiment - 0.05, -0.1), Math.max(maxSentiment + 0.05, 0.1)]}
              tickFormatter={(val: number) => `${(val * 100).toFixed(0)}%`}
            />
            <Tooltip
              contentStyle={{
                background: 'rgba(15,15,25,0.95)', border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '6px', fontSize: '0.7rem',
              }}
              formatter={(val: any) => [(Number(val) * 100).toFixed(1) + '%', 'Sentiment']}
              labelFormatter={((label: any) => `Datum: ${label}`) as any}
            />
            <ReferenceLine y={0} stroke="rgba(255,255,255,0.15)" strokeDasharray="3 3" />
            <Area
              type="monotone" dataKey="sentiment_avg"
              stroke={color} strokeWidth={2}
              fill={`url(#sentGrad-${assetId})`}
              dot={{ r: 3, fill: color, stroke: 'rgba(0,0,0,0.3)', strokeWidth: 1 }}
              activeDot={{ r: 5, fill: color }}
            />
          </AreaChart>
        </ResponsiveContainer>

        {/* Mentions bar */}
        <div style={{ padding: '0 1rem', display: 'flex', gap: '0.15rem', alignItems: 'flex-end', height: '20px' }}>
          {data.map((d, i) => {
            const maxMentions = Math.max(...data.map(p => p.mentions), 1);
            const height = Math.max(2, (d.mentions / maxMentions) * 18);
            return (
              <div key={i} style={{
                flex: 1, height: `${height}px`, borderRadius: '1px',
                background: d.sentiment_avg > 0.1 ? 'rgba(16,185,129,0.4)' :
                             d.sentiment_avg < -0.1 ? 'rgba(239,68,68,0.4)' : 'rgba(255,255,255,0.1)',
              }} title={`${d.date}: ${d.mentions} omnämnanden`} />
            );
          })}
        </div>
        <div style={{ textAlign: 'center', fontSize: '0.55rem', color: 'var(--text-tertiary)', marginTop: '0.2rem' }}>
          Omnämnanden per dag (Marketaux)
        </div>
      </div>
    </div>
  );
}
