'use client';

import React from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { DivergenceRecord } from '../types';

interface DivergenceDonutProps {
  divergences: DivergenceRecord[];
  totalReconciled: number;
}

const typeConfig: Record<string, { label: string; color: string }> = {
  MISSING_IN_CV: { label: 'Ausente no CRM', color: '#f43f5e' },
  ORIGIN_MISMATCH: { label: 'Origem errada', color: '#f59e0b' },
  LATENCY_DELAY: { label: 'Atraso na integração', color: '#3b82f6' },
  PENDING_SYNC: { label: 'Aguardando sync', color: '#8b5cf6' },
  MATCH_OK: { label: 'Integrado OK', color: '#10b981' },
};

const CustomTooltip = ({ active, payload }: any) => {
  if (!active || !payload?.length) return null;
  const data = payload[0].payload;
  return (
    <div className="bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 shadow-2xl">
      <div className="flex items-center space-x-2 mb-1">
        <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: data.color }} />
        <span className="text-sm font-bold text-white">{data.label}</span>
      </div>
      <p className="text-xs text-slate-300">
        {data.value} lead(s) · {data.percent}%
      </p>
    </div>
  );
};

export const DivergenceDonut: React.FC<DivergenceDonutProps> = ({ divergences, totalReconciled }) => {
  // Count divergences by type
  const counts: Record<string, number> = {};
  for (const d of divergences) {
    counts[d.divergence_type] = (counts[d.divergence_type] || 0) + 1;
  }

  // Build chart data — include MATCH_OK as the "green" slice
  const totalDivergences = divergences.length;
  const total = totalReconciled + totalDivergences;

  const chartData = [];

  if (totalReconciled > 0) {
    chartData.push({
      label: 'Integrado OK',
      value: totalReconciled,
      color: typeConfig.MATCH_OK.color,
      percent: total > 0 ? Math.round((totalReconciled / total) * 100) : 0,
    });
  }

  for (const [type, count] of Object.entries(counts)) {
    const cfg = typeConfig[type] || { label: type, color: '#64748b' };
    chartData.push({
      label: cfg.label,
      value: count,
      color: cfg.color,
      percent: total > 0 ? Math.round((count / total) * 100) : 0,
    });
  }

  return (
    <div className="card p-6">
      <h3 className="text-sm font-bold text-white mb-1">Distribuição de Resultados</h3>
      <p className="text-[11px] text-slate-500 mb-4">Proporção de leads integrados vs problemas</p>

      <div className="flex flex-col md:flex-row items-center gap-4">
        <div className="w-48 h-48">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={chartData}
                cx="50%"
                cy="50%"
                innerRadius={48}
                outerRadius={76}
                paddingAngle={3}
                dataKey="value"
                strokeWidth={0}
              >
                {chartData.map((entry, index) => (
                  <Cell key={index} fill={entry.color} fillOpacity={0.85} />
                ))}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="flex-1 space-y-2">
          {chartData.map((item, idx) => (
            <div key={idx} className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: item.color }} />
                <span className="text-xs text-slate-300">{item.label}</span>
              </div>
              <div className="flex items-center space-x-2">
                <span className="text-xs font-bold text-white">{item.value}</span>
                <span className="text-[10px] text-slate-500">({item.percent}%)</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
