import React from 'react';
import { ChannelSummary } from '../types';

interface TemporalChartProps {
  channels: ChannelSummary[];
}

export const TemporalChart: React.FC<TemporalChartProps> = ({ channels }) => {
  const maxLeads = Math.max(...channels.map((c) => Math.max(c.total_source_leads, c.total_cv_leads)), 1);

  return (
    <div className="glass-panel rounded-2xl p-6 border border-slate-800 mb-6">
      <div className="mb-4">
        <h3 className="text-base font-bold text-white">Distribuição e Comparativo de Volume por Origem</h3>
        <p className="text-xs text-slate-400">Comparação visual direta: Volume Capturado na Origem vs Registros Efetivos no CRM CV</p>
      </div>

      <div className="space-y-4">
        {channels.map((ch) => {
          const srcWidth = `${(ch.total_source_leads / maxLeads) * 100}%`;
          const cvWidth = `${(ch.total_cv_leads / maxLeads) * 100}%`;

          return (
            <div key={ch.channel} className="space-y-1.5">
              <div className="flex justify-between text-xs">
                <span className="font-semibold text-slate-200 uppercase">{ch.channel.replace('_', ' ')}</span>
                <span className="text-slate-400">
                  Origem: <strong className="text-sky-400">{ch.total_source_leads}</strong> | CV: <strong className="text-emerald-400">{ch.total_cv_leads}</strong>
                </span>
              </div>
              
              <div className="space-y-1 bg-slate-900/60 p-2 rounded-xl border border-slate-800">
                {/* Source Bar */}
                <div className="flex items-center space-x-2">
                  <span className="text-[10px] w-12 text-slate-500 font-semibold">Origem</span>
                  <div className="flex-1 bg-slate-800 rounded-full h-2 overflow-hidden">
                    <div
                      className="bg-sky-500 h-2 rounded-full transition-all duration-500"
                      style={{ width: srcWidth }}
                    />
                  </div>
                </div>

                {/* CV Bar */}
                <div className="flex items-center space-x-2">
                  <span className="text-[10px] w-12 text-slate-500 font-semibold">CV CRM</span>
                  <div className="flex-1 bg-slate-800 rounded-full h-2 overflow-hidden">
                    <div
                      className="bg-emerald-500 h-2 rounded-full transition-all duration-500"
                      style={{ width: cvWidth }}
                    />
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
