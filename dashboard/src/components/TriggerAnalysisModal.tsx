import React, { useState } from 'react';
import { X, Play, CheckCircle2, Loader2, Sparkles, AlertTriangle } from 'lucide-react';
import { GlobalReconciliationReport } from '../types';
import { triggerAnalysis } from '../lib/dataService';

interface TriggerAnalysisModalProps {
  isOpen: boolean;
  onClose: () => void;
  onRunSuccess: (newReport: GlobalReconciliationReport) => void;
}

export const TriggerAnalysisModal: React.FC<TriggerAnalysisModalProps> = ({
  isOpen,
  onClose,
  onRunSuccess,
}) => {
  // Default date range: last 7 days
  const today = new Date().toISOString().slice(0, 10);
  const sevenDaysAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);

  const [startDate, setStartDate] = useState(sevenDaysAgo);
  const [endDate, setEndDate] = useState(today);
  const [isRunning, setIsRunning] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const steps = [
    "Conectando ao backend Python...",
    "Extraindo leads de Meta Ads, Google Ads, RD Station, BeeViral e Planilhas BI...",
    "Consultando CRM Construtor de Vendas (CV)...",
    "Executando Algoritmo Híbrido de Sanitização e Matching...",
    "Gerando relatório e salvando no Firebase Firestore...",
  ];

  const handleRun = async () => {
    setIsRunning(true);
    setCurrentStep(0);
    setError(null);

    // Animate through steps while waiting for real API response
    let step = 0;
    const interval = setInterval(() => {
      step += 1;
      if (step < steps.length) {
        setCurrentStep(step);
      }
    }, 2500);

    try {
      const response = await triggerAnalysis(startDate, endDate);

      clearInterval(interval);
      setCurrentStep(steps.length); // All steps done
      setIsRunning(false);

      // Small delay to show final state, then close
      setTimeout(() => {
        onRunSuccess(response.report);
        onClose();
        setCurrentStep(0);
      }, 800);
    } catch (err: any) {
      clearInterval(interval);
      setIsRunning(false);
      setError(err.message || 'Erro desconhecido ao executar a engine.');
    }
  };

  return (
    <div className="theme-modal-backdrop fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md">
      <div className="theme-modal-panel glass-panel w-full max-w-lg rounded-2xl p-6 border border-slate-700 shadow-2xl relative bg-slate-900/95">
        <button
          onClick={onClose}
          disabled={isRunning}
          className="absolute top-4 right-4 text-slate-400 hover:text-slate-200 transition-colors disabled:opacity-30"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center space-x-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-sky-500/10 border border-sky-500/30 flex items-center justify-center text-sky-400">
            <Play className="w-5 h-5 fill-current" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white">Disparar Análise Sob Demanda</h3>
            <p className="text-xs text-slate-400">Executa o pipeline Python real e atualiza os dados do dashboard</p>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 flex items-start space-x-2">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-bold text-rose-400 mb-0.5">Erro na Execução</p>
              <p className="text-[11px] text-rose-300/80 leading-relaxed">{error}</p>
            </div>
          </div>
        )}

        {!isRunning && currentStep < steps.length ? (
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
                <span>Pipeline Real:</span>
              </div>
              <p>Extrai leads reais de Meta Ads, Google Ads, RD Station, BeeViral, Planilhas BI &amp; cruza com CRM CV.</p>
            </div>

            <div className="pt-2 flex justify-end space-x-3">
              <button
                onClick={onClose}
                className="px-4 py-2 rounded-xl text-xs font-medium text-slate-400 hover:text-white transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={handleRun}
                className="px-5 py-2 rounded-xl bg-gradient-to-r from-sky-500 to-blue-600 hover:from-sky-400 hover:to-blue-500 text-white text-xs font-semibold shadow-lg shadow-sky-500/20 transition-all"
              >
                Iniciar Processamento
              </button>
            </div>
          </div>
        ) : (
          <div className="py-6 space-y-4">
            <div className="flex items-center justify-center space-x-3">
              {currentStep >= steps.length ? (
                <>
                  <CheckCircle2 className="w-6 h-6 text-emerald-400" />
                  <span className="text-sm font-semibold text-emerald-300">Análise Concluída!</span>
                </>
              ) : (
                <>
                  <Loader2 className="w-6 h-6 text-sky-400 animate-spin" />
                  <span className="text-sm font-semibold text-slate-200">Executando Pipeline Real...</span>
                </>
              )}
            </div>

            <div className="bg-slate-900/80 p-4 rounded-xl border border-slate-800 space-y-2">
              {steps.map((st, idx) => (
                <div key={idx} className="flex items-center space-x-2 text-xs">
                  {idx < currentStep ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  ) : idx === currentStep ? (
                    <Loader2 className="w-4 h-4 text-sky-400 animate-spin shrink-0" />
                  ) : (
                    <div className="w-4 h-4 rounded-full border border-slate-700 shrink-0" />
                  )}
                  <span className={idx <= currentStep ? "text-slate-200" : "text-slate-500"}>
                    {st}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
