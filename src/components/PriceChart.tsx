import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { createChart, ColorType, CandlestickSeries } from 'lightweight-charts';
import { api } from '../api/client';

interface PriceChartProps {
  assetId: string;
  assetName?: string;
  height?: number;
}

const PERIOD_OPTIONS = [
  { label: '1M', value: '1mo' },
  { label: '3M', value: '3mo' },
  { label: '6M', value: '6mo' },
  { label: '1Y', value: '1y' },
  { label: '2Y', value: '2y' },
];

export default function PriceChart({ assetId, assetName, height = 300 }: PriceChartProps) {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<ReturnType<typeof createChart> | null>(null);
  const [period, setPeriod] = useState('3mo');

  const { data, isLoading } = useQuery({
    queryKey: ['price-history', assetId, period],
    queryFn: () => api.getPriceHistory(assetId, period),
    staleTime: 300_000,
    retry: 1,
  });

  useEffect(() => {
    if (!chartRef.current || !data?.candles?.length) return;

    if (chartInstance.current) {
      chartInstance.current.remove();
      chartInstance.current = null;
    }

    const chart = createChart(chartRef.current, {
      width: chartRef.current.clientWidth,
      height,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#9ca3af',
        fontSize: 11,
      },
      grid: {
        vertLines: { color: 'rgba(255,255,255,0.03)' },
        horzLines: { color: 'rgba(255,255,255,0.03)' },
      },
      crosshair: {
        vertLine: { color: 'rgba(102,126,234,0.3)', labelBackgroundColor: '#667eea' },
        horzLine: { color: 'rgba(102,126,234,0.3)', labelBackgroundColor: '#667eea' },
      },
      rightPriceScale: {
        borderColor: 'rgba(255,255,255,0.06)',
      },
      timeScale: {
        borderColor: 'rgba(255,255,255,0.06)',
        timeVisible: false,
      },
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: '#10b981',
      downColor: '#ef4444',
      borderUpColor: '#10b981',
      borderDownColor: '#ef4444',
      wickUpColor: '#10b98180',
      wickDownColor: '#ef444480',
    });

    const candles = data.candles.map((c: { time: string; open: number; high: number; low: number; close: number }) => ({
      time: c.time,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));

    series.setData(candles);
    chart.timeScale().fitContent();
    chartInstance.current = chart;

    const ro = new ResizeObserver(() => {
      if (chartRef.current && chartInstance.current) {
        chartInstance.current.applyOptions({ width: chartRef.current.clientWidth });
      }
    });
    ro.observe(chartRef.current);

    return () => {
      ro.disconnect();
      if (chartInstance.current) {
        chartInstance.current.remove();
        chartInstance.current = null;
      }
    };
  }, [data, height]);

  // Compute price change
  const lastCandle = data?.candles?.[data.candles.length - 1];
  const firstCandle = data?.candles?.[0];
  const changePct = lastCandle && firstCandle
    ? ((lastCandle.close - firstCandle.close) / firstCandle.close) * 100
    : null;

  return (
    <div className="glass-panel" style={{ padding: '1rem 1.25rem', position: 'relative' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)' }}>
            {assetName || data?.name || assetId}
          </span>
          {lastCandle && (
            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
              {data?.currency}{lastCandle.close.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
          )}
          {changePct !== null && (
            <span style={{
              fontSize: '0.72rem',
              fontWeight: 700,
              padding: '0.1rem 0.4rem',
              borderRadius: '4px',
              background: changePct >= 0 ? 'rgba(16,185,129,0.12)' : 'rgba(239,68,68,0.12)',
              color: changePct >= 0 ? '#10b981' : '#ef4444',
            }}>
              {changePct >= 0 ? '+' : ''}{changePct.toFixed(1)}%
            </span>
          )}
        </div>

        {/* Period selector */}
        <div style={{ display: 'flex', gap: '2px', background: 'rgba(255,255,255,0.03)', borderRadius: '6px', padding: '2px' }}>
          {PERIOD_OPTIONS.map(p => (
            <button
              key={p.value}
              onClick={() => setPeriod(p.value)}
              style={{
                fontSize: '0.65rem',
                fontWeight: period === p.value ? 700 : 500,
                padding: '0.25rem 0.5rem',
                borderRadius: '4px',
                border: 'none',
                cursor: 'pointer',
                background: period === p.value ? 'rgba(102,126,234,0.15)' : 'transparent',
                color: period === p.value ? '#667eea' : '#6b7280',
                transition: 'all 0.15s',
              }}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Chart container */}
      <div ref={chartRef} style={{ width: '100%', height: `${height}px` }} />

      {/* Loading overlay */}
      {isLoading && (
        <div style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'rgba(0,0,0,0.5)',
          borderRadius: '12px',
          fontSize: '0.82rem',
          color: '#9ca3af',
        }}>
          Laddar prishistorik...
        </div>
      )}
    </div>
  );
}
