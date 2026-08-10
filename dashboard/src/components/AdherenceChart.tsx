'use client';

import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  LabelList,
} from 'recharts';
import { ChannelSummary } from '../types';

interface AdherenceChartProps {
  channels: ChannelSummary[];
}

const channelNames: Record<string, string> = {
  meta_ads: 'Meta Ads',
  google_ads: 'Google Ads',
  rd_station: 'RD Station',
  beeviral: 'BeeViral',
  sheets_bi: 'Planilhas',
};

const channelColors: Record<string, string> = {
  meta_ads: '#3b82f6',
  google_ads: '#10b981',
  rd_station: '#8b5cf6',
  beeviral: '#f59e0b',
  sheets_bi: '#64748b',
};

function getBarColor(rate: number): string {
  if (rate >= 95) return '#10b981';
  if (rate >= 80) return '#f59e0b';
  return '#f43f5e';
}

const CustomTooltip = ({ active, payload }: any) => {
  if (!active || !payload?.length) return null;
  const data = payload[0].payload;
  return (
    <div className="bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 shadow-2xl">
      <p className="text-sm font-bold text-white mb-1">{data.name}</p>
      <div className="space-y-0.5 text-xs">
        <p className="text-slate-300">
          Aderência: <span className="font-bold" style={{ color: getBarColor(data.rate) }}>{data.rate}%</span>
        </p>
        <p className="text-slate-400">{data.source} leads captados · {data.matched} no CRM</p>
        {data.missing > 0 && <p className="text-rose-400">{data.missing} lead(s) perdido(s)</p>}
        {data.mismatch > 0 && <p className="text-amber-400">{data.mismatch} origem errada</p>}
      </div>
    </div>
  );
};

export const AdherenceChart: React.FC<AdherenceChartProps> = ({ channels }) => {
  const data = channels
    .map((ch) => ({
      name: channelNames[ch.channel] || ch.channel,
      channel: ch.channel,
      rate: ch.adherence_rate,
      source: ch.total_source_leads,
      matched: ch.match_ok_count,
      missing: ch.missing_in_cv_count,
      mismatch: ch.origin_mismatch_count,
    }))
    .sort((a, b) => a.rate - b.rate);

  return (
    <div className="card p-6">
      <h3 className="text-sm font-bold text-white mb-1">Taxa de Aderência por Canal</h3>
      <p className="text-[11px] text-slate-500 mb-4">Percentual de leads que chegaram corretamente ao CRM</p>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 40, bottom: 0, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" horizontal={false} />
          <XAxis type="number" domain={[0, 100]} tick={{ fill: '#64748b', fontSize: 11 }} axisLine={{ stroke: '#334155' }} />
          <YAxis
            type="category"
            dataKey="name"
            width={90}
            tick={{ fill: '#94a3b8', fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(56, 189, 248, 0.05)' }} />
          <Bar dataKey="rate" radius={[0, 6, 6, 0]} barSize={24}>
            {data.map((entry, index) => (
              <Cell key={index} fill={channelColors[entry.channel] || '#64748b'} fillOpacity={0.85} />
            ))}
            <LabelList
              dataKey="rate"
              position="right"
              formatter={(val: number) => `${val}%`}
              style={{ fill: '#94a3b8', fontSize: 11, fontWeight: 600 }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};
