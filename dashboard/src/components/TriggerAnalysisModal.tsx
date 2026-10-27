import React, { useState } from 'react';
import { X, Play, Loader2, AlertTriangle, Sparkles } from 'lucide-react';
import { GlobalReconciliationReport, SourceStatus } from '../types';
import { runReconciliation } from '../lib/engine';

interface TriggerAnalysisModalProps {
  isOpen: boolean;
  onClose: () => void;
  onRunSuccess: (newReport: GlobalReconciliationReport, sources: SourceStatus[]) => void;
}

function isoDay(date: Date): string {
  return date.toISOString().slice(0, 10);
}

export const TriggerAnalysisModal: React.FC<TriggerAnalysisModalProps> = ({
  isOpen,
  onClose,
  onRunSuccess,
}) => {
  const [startDate, setStartDate] = useState(() => isoDay(new Date(Date.now() - 7 * 24 * 3600 * 1000)));
  const [endDate, setEndDate] = useState(() => isoDay(new Date()));
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleRun = async () => {
    setIsRunning(true);
    setError(null);
    try {
      const result = await runReconciliation(startDate, endDate);
      if (!result.report) throw new Error('O motor não devolveu um relatório.');
      onRunSuccess(result.report, result.sources);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Falha ao executar a análise.');
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md">
      <div className="glass-panel w-full max-w-lg rounded-2xl p-6 border border-slate-700 shadow-2xl relative">
        <button
          onClick={onClose}
          disabled={isRunning}
          className="absolute top-4 right-4 text-slate-400 hover:text-slate-200 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center space-x-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-sky-500/10 border border-sky-500/30 flex items-center justify-center text-sky-400">
            <Play className="w-5 h-5 fill-current" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white">Disparar Análise Sob Demanda</h3>
            <p className="text-xs text-slate-400">Busca os leads nas mídias e cruza com o CRM Construtor de Vendas</p>
          </div>
        </div>

        {!isRunning ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Data Inicial</label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-sky-500"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Data Final</label>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-sky-500"
                />
              </div>
            </div>

            <div className="bg-slate-900/60 p-3 rounded-xl border border-slate-800 text-xs text-slate-400 space-y-1">
              <div className="font-semibold text-slate-300 flex items-center space-x-1.5">
                <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                <span>Fontes Inspecionadas:</span>
              </div>
              <p>Meta Ads, Google Ads, RD Station, BeeViral, Planilhas BI & CRM CV.</p>
            </div>

            {error && (
              <div className="flex items-start space-x-2 p-3 rounded-xl border border-rose-500/30 bg-rose-500/5 text-xs text-rose-300">
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            <div className="pt-2 flex justify-end space-x-3">
              <button
                onClick={onClose}
                className="px-4 py-2 rounded-xl text-xs font-medium text-slate-400 hover:text-white transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={handleRun}
                disabled={!startDate || !endDate}
                className="px-5 py-2 rounded-xl bg-gradient-to-r from-sky-500 to-blue-600 hover:from-sky-400 hover:to-blue-500 text-white text-xs font-semibold shadow-lg shadow-sky-500/20 transition-all disabled:opacity-50"
              >
                Iniciar Processamento
              </button>
            </div>
          </div>
        ) : (
          <div className="py-8 space-y-3 text-center">
            <Loader2 className="w-7 h-7 text-sky-400 animate-spin mx-auto" />
            <p className="text-sm font-semibold text-slate-200">Processando Reconciliação...</p>
            <p className="text-xs text-slate-400">
              Consultando as mídias e o CRM CV. Pode levar até 1 minuto.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
