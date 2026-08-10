import React, { useState } from 'react';
import { DivergenceRecord } from '../types';
import { Search, Download, ShieldAlert } from 'lucide-react';

interface DivergenceListProps {
  divergences: DivergenceRecord[];
}

export const DivergenceList: React.FC<DivergenceListProps> = ({ divergences }) => {
  const [searchTerm, setSearchTerm] = useState('');

  const filteredDivergences = divergences.filter((item) => {
    const term = searchTerm.toLowerCase();
    return (
      (item.email && item.email.toLowerCase().includes(term)) ||
      (item.phone && item.phone.includes(term)) ||
      (item.details && item.details.toLowerCase().includes(term))
    );
  });

  const exportToCSV = () => {
    if (filteredDivergences.length === 0) return;

    const headers = ['E-mail', 'Telefone', 'Canal de Origem', 'Status do Diagnostico', 'Detalhes', 'Data'];
    const rows = filteredDivergences.map((d) => [
      d.email || '',
      d.phone || '',
      d.origin_channel,
      d.divergence_type,
      `"${d.details.replace(/"/g, '""')}"`,
      d.source_created_at,
    ]);

    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map((e) => e.join(','))].join('\n');
    const link = document.createElement('a');
    link.setAttribute('href', encodeURI(csvContent));
    link.setAttribute('download', `leads_divergentes_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const getDivergenceLabel = (type: string) => {
    switch (type) {
      case 'MISSING_IN_CV':
        return <span className="px-2.5 py-1 rounded-full text-[11px] font-bold bg-rose-500/10 text-rose-400 border border-rose-500/20">❌ Lead Faltando no CRM</span>;
      case 'ORIGIN_MISMATCH':
        return <span className="px-2.5 py-1 rounded-full text-[11px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">⚠️ Origem Cadastrada Errada</span>;
      case 'LATENCY_DELAY':
        return <span className="px-2.5 py-1 rounded-full text-[11px] font-bold bg-sky-500/10 text-sky-400 border border-sky-500/20">⏱️ Atraso de Envio</span>;
      default:
        return <span className="text-slate-400">{type}</span>;
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-5">
        <div>
          <h3 className="text-sm font-bold text-white flex items-center space-x-2">
            <ShieldAlert className="w-4 h-4 text-rose-400" />
            <span>Lista de Leads com Inconsistência</span>
          </h3>
          <p className="text-xs text-slate-400">Identificação individual de quem sumiu ou entrou errado no CRM</p>
        </div>

        <button
          onClick={exportToCSV}
          className="inline-flex items-center space-x-2 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition-colors"
        >
          <Download className="w-3.5 h-3.5" />
          <span>Baixar Lista (CSV)</span>
        </button>
      </div>

      {/* Busca */}
      <div className="mb-4 relative">
        <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
        <input
          type="text"
          placeholder="Buscar por e-mail ou telefone..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-sky-500"
        />
      </div>

      {/* Tabela de Divergências */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider">
              <th className="pb-3 px-2">E-mail / Telefone</th>
              <th className="pb-3 px-2">Canal de Origem</th>
              <th className="pb-3 px-2">O que Aconteceu</th>
              <th className="pb-3 px-2">Diagnóstico</th>
              <th className="pb-3 px-2 text-right">Data</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {filteredDivergences.length > 0 ? (
              filteredDivergences.map((item) => (
                <tr key={item.id} className="hover:bg-slate-800/40">
                  <td className="py-3 px-2">
                    <div className="font-semibold text-slate-200">{item.email || 'E-mail não informado'}</div>
                    <div className="text-[11px] text-slate-400">{item.phone || 'Sem telefone'}</div>
                  </td>
                  <td className="py-3 px-2 font-semibold text-sky-400 uppercase text-[11px]">
                    {item.origin_channel.replace('_', ' ')}
                  </td>
                  <td className="py-3 px-2">
                    {getDivergenceLabel(item.divergence_type)}
                  </td>
                  <td className="py-3 px-2 text-slate-300 max-w-sm">
                    {item.details}
                  </td>
                  <td className="py-3 px-2 text-right text-slate-400 text-[11px]">
                    {new Date(item.source_created_at).toLocaleString('pt-BR')}
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={5} className="py-8 text-center text-slate-500">
                  Nenhuma divergência encontrada.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
