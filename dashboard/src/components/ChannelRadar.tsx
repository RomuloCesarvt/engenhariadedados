'use client';

import React from 'react';
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import { ChannelSummary } from '../types';

interface ChannelRadarProps {
  channels: ChannelSummary[];
}

const channelNames: Record<string, string> = {
  meta_ads: 'Meta Ads',
  google_ads: 'Google Ads',
  rd_station: 'RD Station',
  beeviral: 'BeeViral',
  sheets_bi: 'Planilhas',
};

const CustomTooltip = ({ active, payload }: any) => {
  if (!active || !payload?.length) return null;
  const data = payload[0].payload;
  return (
    <div className="bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 shadow-2xl">
      <p className="text-sm font-bold text-white mb-1">{data.subject}</p>
      <div className="space-y-0.5 text-xs">
        <p className="text-sky-400">Aderência: {data.aderencia}%</p>
        <p className="text-emerald-400">Volume: {data.volume} leads</p>
        <p className="text-amber-400">Confiabilidade: {data.confiabilidade}%</p>
      </div>
    </div>
  );
};

export const ChannelRadar: React.FC<ChannelRadarProps> = ({ channels }) => {
  const data = channels.map((ch) => {
    const totalProblems = ch.missing_in_cv_count + ch.origin_mismatch_count;
    const reliability = ch.total_source_leads > 0
      ? Math.round(((ch.total_source_leads - totalProblems) / ch.total_source_leads) * 100)
      : 100;

    return {
      subject: channelNames[ch.channel] || ch.channel,
      aderencia: ch.adherence_rate,
      volume: ch.total_source_leads,
      confiabilidade: reliability,
      fullMark: 100,
    };
  });

  return (
    <div className="card p-6">
      <h3 className="text-sm font-bold text-white mb-1">Radar de Saúde por Canal</h3>
      <p className="text-[11px] text-slate-500 mb-4">Visão multidimensional: aderência, volume e confiabilidade</p>

      <ResponsiveContainer width="100%" height={280}>
        <RadarChart cx="50%" cy="50%" outerRadius="70%" data={data}>
          <PolarGrid stroke="#1e293b" />
          <PolarAngleAxis
            dataKey="subject"
            tick={{ fill: '#94a3b8', fontSize: 11 }}
          />
          <PolarRadiusAxis
            angle={90}
            domain={[0, 100]}
            tick={{ fill: '#475569', fontSize: 10 }}
            axisLine={false}
          />
          <Radar
            name="Aderência"
            dataKey="aderencia"
            stroke="#0ea5e9"
            fill="#0ea5e9"
            fillOpacity={0.2}
            strokeWidth={2}
          />
          <Radar
            name="Confiabilidade"
            dataKey="confiabilidade"
            stroke="#10b981"
            fill="#10b981"
            fillOpacity={0.1}
            strokeWidth={2}
            strokeDasharray="4 4"
          />
          <Tooltip content={<CustomTooltip />} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
};
