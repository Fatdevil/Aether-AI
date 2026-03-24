import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { PieChart } from 'lucide-react';
import type { Asset } from '../types';

interface ScenarioChartProps {
  asset: Asset;
}

export default function ScenarioChart({ asset }: ScenarioChartProps) {
  const { scenarioData, scenarioProbabilities } = asset;

  return (
    <div>
      <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
        <PieChart size={20} color="var(--accent-purple)" /> Framtida Scenariomodellering (6 Månader)
      </h3>
      <div className="flex gap-4" style={{ marginBottom: '1rem', flexWrap: 'wrap' }}>
        <span className="badge positive">Bull: {scenarioProbabilities.bull}%</span>
        <span className="badge neutral">Base: {scenarioProbabilities.base}%</span>
        <span className="badge negative">Bear: {scenarioProbabilities.bear}%</span>
      </div>

      <div style={{ height: '280px', width: '100%', marginBottom: '1.5rem' }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={scenarioData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="colorBull" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#00e676" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#00e676" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="colorBase" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#00f2fe" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#00f2fe" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="colorBear" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#ff1744" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#ff1744" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
            <XAxis dataKey="name" stroke="#6c757d" fontSize={12} tickLine={false} axisLine={false} />
            <YAxis stroke="#6c757d" fontSize={12} tickLine={false} axisLine={false} />
            <Tooltip
              contentStyle={{ backgroundColor: '#13141f', borderColor: 'rgba(255,255,255,0.08)', borderRadius: '8px', color: '#f8f9fa' }}
              itemStyle={{ fontSize: '0.85rem' }}
            />
            <Area type="monotone" dataKey="bull" name={`Bull (${scenarioProbabilities.bull}%)`} stroke="#00e676" fillOpacity={1} fill="url(#colorBull)" strokeWidth={2} />
            <Area type="monotone" dataKey="base" name={`Base (${scenarioProbabilities.base}%)`} stroke="#00f2fe" fillOpacity={1} fill="url(#colorBase)" strokeWidth={2} />
            <Area type="monotone" dataKey="bear" name={`Bear (${scenarioProbabilities.bear}%)`} stroke="#ff1744" fillOpacity={1} fill="url(#colorBear)" strokeWidth={2} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
