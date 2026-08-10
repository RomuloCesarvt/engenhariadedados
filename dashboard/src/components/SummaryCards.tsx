import React from 'react';
import { Users, CheckCircle2, AlertTriangle, XCircle } from 'lucide-react';
import { GlobalReconciliationReport } from '../types';

interface SummaryCardsProps {
  report: GlobalReconciliationReport;
}

export const SummaryCards: React.FC<SummaryCardsProps> = ({ report }) => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
      {/* Total Criados nas Mídias */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-slate-400">Total de Leads Criados</span>
          <div className="w-7 h-7 rounded-lg bg-sky-500/10 flex items-center justify-center text-sky-400">
            <Users className="w-4 h-4" />
          </div>
        </div>
        <div className="text-2xl font-bold text-white">{report.total_source_leads}</div>
        <p className="text-[11px] text-slate-400 mt-1">Soma de Meta, Google, RD e BeeViral</p>
      </div>

      {/* Total Recebidos no CRM */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-slate-400">Entraram no CRM (CV)</span>
          <div className="w-7 h-7 rounded-lg bg-emerald-500/10 flex items-center justify-center text-emerald-400">
            <CheckCircle2 className="w-4 h-4" />
          </div>
        </div>
        <div className="text-2xl font-bold text-emerald-400">{report.total_reconciled_ok}</div>
        <p className="text-[11px] text-slate-400 mt-1">Leads integrados corretamente</p>
      </div>

      {/* Leads Faltando / Perdidos */}
      <div className="bg-slate-900 border border-rose-950/60 rounded-2xl p-5 bg-gradient-to-b from-rose-950/20 to-transparent">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-rose-300">Leads Faltando no CRM</span>
          <div className="w-7 h-7 rounded-lg bg-rose-500/10 flex items-center justify-center text-rose-400">
            <XCircle className="w-4 h-4" />
          </div>
        </div>
        <div className="text-2xl font-bold text-rose-400">{report.total_missing_in_cv}</div>
        <p className="text-[11px] text-rose-300/80 mt-1">Leads perdidos no caminho</p>
      </div>

      {/* Origem Incorreta */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-slate-400">Origem Cadastrada Errada</span>
          <div className="w-7 h-7 rounded-lg bg-amber-500/10 flex items-center justify-center text-amber-400">
            <AlertTriangle className="w-4 h-4" />
          </div>
        </div>
        <div className="text-2xl font-bold text-amber-400">{report.total_origin_mismatch}</div>
        <p className="text-[11px] text-slate-400 mt-1">Entraram no CV com a mídia trocada</p>
      </div>
    </div>
  );
};
