import React from 'react';
import { ChannelSummary, OriginChannel } from '../types';

interface ReconciliationTableProps {
  channels: ChannelSummary[];
}

export const ReconciliationTable: React.FC<ReconciliationTableProps> = ({ channels }) => {
  const channelNames: Record<OriginChannel, string> = {
    meta_ads: 'Meta Ads (Facebook / Instagram)',
    google_ads: 'Google Ads',
    rd_station: 'RD Station Marketing',
    beeviral: 'BeeViral (Programa de Indicação)',
    sheets_bi: 'Planilhas BI / Eventos',
    cv_crm: 'CRM Construtor de Vendas (CV)',
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 mb-6">
      <div className="mb-4">
        <h3 className="text-sm font-bold text-white">Resumo por Canal de Origem</h3>
        <p className="text-xs text-slate-400">Compare quantos leads foram criados em cada ferramenta vs quantos chegaram no CV</p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider">
              <th className="pb-3 px-2">Canal / Ferramenta</th>
              <th className="pb-3 px-2 text-center">Criados na Mídia</th>
              <th className="pb-3 px-2 text-center">No CRM (CV)</th>
              <th className="pb-3 px-2 text-center">Integrados OK</th>
              <th className="pb-3 px-2 text-center">Leads Faltando</th>
              <th className="pb-3 px-2 text-center">Origem Incorreta</th>
              <th className="pb-3 px-2 text-right">Aderência (%)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {channels.map((item) => (
              <tr key={item.channel} className="hover:bg-slate-800/40">
                <td className="py-3 px-2 font-medium text-slate-200">
                  {channelNames[item.channel] || item.channel}
                </td>
                <td className="py-3 px-2 text-center font-bold text-slate-100">{item.total_source_leads}</td>
                <td className="py-3 px-2 text-center text-slate-300">{item.total_cv_leads}</td>
                <td className="py-3 px-2 text-center">
                  <span className="text-emerald-400 font-semibold">{item.match_ok_count}</span>
                </td>
                <td className="py-3 px-2 text-center">
                  {item.missing_in_cv_count > 0 ? (
                    <span className="px-2 py-0.5 rounded bg-rose-500/10 text-rose-400 font-bold">
                      {item.missing_in_cv_count} Faltando
                    </span>
                  ) : (
                    <span className="text-slate-500">0</span>
                  )}
                </td>
                <td className="py-3 px-2 text-center">
                  {item.origin_mismatch_count > 0 ? (
                    <span className="px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 font-bold">
                      {item.origin_mismatch_count} Trocado
                    </span>
                  ) : (
                    <span className="text-slate-500">0</span>
                  )}
                </td>
                <td className="py-3 px-2 text-right font-bold text-sky-400">
                  {item.adherence_rate}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
