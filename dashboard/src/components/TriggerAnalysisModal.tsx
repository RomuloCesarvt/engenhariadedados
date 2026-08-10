import React, { useState } from 'react';
import { X, Play, CheckCircle2, Loader2, Calendar, Server, Database, Sparkles } from 'lucide-react';
import { GlobalReconciliationReport } from '../types';

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
  const [startDate, setStartDate] = useState('2026-07-20');
  const [endDate, setEndDate] = useState('2026-07-27');
  const [isRunning, setIsRunning] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);

  if (!isOpen) return null;

  const steps = [
    "Iniciando GitHub Action runner Python...",
    "Extraindo Meta Ads, Google Ads, RD Station, BeeViral e Planilhas BI...",
    "Consultando CRM Construtor de Vendas (CV)...",
    "Executando Algoritmo Híbrido de Sanitização e Matching...",
    "Persistindo resultados no Firebase Firestore..."
  ];

  const handleRun = () => {
    setIsRunning(true);
    setCurrentStep(0);

    let step = 0;
    const interval = setInterval(() => {
      step += 1;
      if (step < steps.length) {
        setCurrentStep(step);
      } else {
        clearInterval(interval);
        setIsRunning(false);
        // Gera relatório atualizado
        const updatedReport: GlobalReconciliationReport = {
          execution_id: `exec_${Date.now()}`,
          timestamp: new Date().toISOString(),
          start_date: startDate,
          end_date: endDate,
          total_source_leads: 24,
          total_cv_leads: 23,
          total_reconciled_ok: 22,
          total_missing_in_cv: 1,
          total_origin_mismatch: 1,
          overall_adherence_rate: 91.7,
          overall_health: "WARNING",
          channels: [
            {
              channel: "meta_ads",
              total_source_leads: 8,
              total_cv_leads: 8,
              match_ok_count: 7,
              missing_in_cv_count: 0,
              origin_mismatch_count: 1,
              latency_delay_count: 0,
              pending_sync_count: 0,
              adherence_rate: 87.5,
              health_status: "WARNING"
            },
            {
              channel: "google_ads",
              total_source_leads: 5,
              total_cv_leads: 5,
              match_ok_count: 5,
              missing_in_cv_count: 0,
              origin_mismatch_count: 0,
              latency_delay_count: 0,
              pending_sync_count: 0,
              adherence_rate: 100.0,
              health_status: "HEALTHY"
            },
            {
              channel: "rd_station",
              total_source_leads: 5,
              total_cv_leads: 5,
              match_ok_count: 5,
              missing_in_cv_count: 0,
              origin_mismatch_count: 0,
              latency_delay_count: 0,
              pending_sync_count: 0,
              adherence_rate: 100.0,
              health_status: "HEALTHY"
            },
            {
              channel: "beeviral",
              total_source_leads: 4,
              total_cv_leads: 3,
              match_ok_count: 3,
              missing_in_cv_count: 1,
              origin_mismatch_count: 0,
              latency_delay_count: 0,
              pending_sync_count: 0,
              adherence_rate: 75.0,
              health_status: "CRITICAL"
            },
            {
              channel: "sheets_bi",
              total_source_leads: 2,
              total_cv_leads: 2,
              match_ok_count: 2,
              missing_in_cv_count: 0,
              origin_mismatch_count: 0,
              latency_delay_count: 0,
              pending_sync_count: 0,
              adherence_rate: 100.0,
              health_status: "HEALTHY"
            }
          ],
          divergences: [
            {
              id: `div_bee_${Date.now()}`,
              source_lead_id: "bee_new_901",
              email: "novo.indicado.beeviral@gmail.com",
              phone: "5511977770000",
              origin_channel: "beeviral",
              divergence_type: "MISSING_IN_CV",
              severity: "HIGH",
              details: "Lead indicado via BeeViral ausente no CRM Construtor de Vendas.",
              source_created_at: new Date().toISOString(),
              integration_id: "bee_ref_901"
            },
            {
              id: `div_meta_${Date.now()}`,
              source_lead_id: "meta_106",
              email: "juliana.mendes@yahoo.com.br",
              phone: "5511944446666",
              origin_channel: "meta_ads",
              divergence_type: "ORIGIN_MISMATCH",
              severity: "MEDIUM",
              details: "Lead capturado no META_ADS, mas registrado no CV como 'Google Ads'.",
              source_created_at: "2026-07-27T08:10:00Z",
              cv_created_at: "2026-07-27T08:12:00Z",
              origem_no_cv: "Google Ads",
              integration_id: "fb_click_106"
            }
          ]
        };

        onRunSuccess(updatedReport);
        onClose();
      }
    }, 1200);
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
            <p className="text-xs text-slate-400">Executa o pipeline Python via GitHub Actions e atualiza o Firestore</p>
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
              <Loader2 className="w-6 h-6 text-sky-400 animate-spin" />
              <span className="text-sm font-semibold text-slate-200">Processando Reconciliação...</span>
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
