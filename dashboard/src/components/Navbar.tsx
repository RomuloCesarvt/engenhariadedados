import React from 'react';
import { Activity, Play, FileText, Database, ShieldAlert } from 'lucide-react';
import { HealthStatus } from '../types';

interface NavbarProps {
  healthStatus: HealthStatus;
  overallAdherence: number;
  onOpenTriggerModal: () => void;
  activeTab: 'summary' | 'investigation' | 'import';
  setActiveTab: (tab: 'summary' | 'investigation' | 'import') => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  healthStatus,
  overallAdherence,
  onOpenTriggerModal,
  activeTab,
  setActiveTab,
}) => {
  return (
    <header className="sticky top-0 z-30 bg-slate-900/90 backdrop-blur-md border-b border-slate-800">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo Limpo */}
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-xl bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400">
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-base font-bold text-white tracking-tight">
                Auditor de Leads
              </h1>
              <p className="text-[11px] text-slate-400">Validação Origens vs CRM Construtor de Vendas</p>
            </div>
          </div>

          {/* Abas Principais Limpas */}
          <nav className="flex items-center space-x-2 bg-slate-950 p-1 rounded-xl border border-slate-800 text-xs">
            <button
              onClick={() => setActiveTab('summary')}
              className={`flex items-center space-x-2 px-3 py-1.5 rounded-lg font-medium transition-all ${
                activeTab === 'summary'
                  ? 'bg-sky-500 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Database className="w-3.5 h-3.5" />
              <span>1. Visão Geral</span>
            </button>

            <button
              onClick={() => setActiveTab('investigation')}
              className={`flex items-center space-x-2 px-3 py-1.5 rounded-lg font-medium transition-all ${
                activeTab === 'investigation'
                  ? 'bg-sky-500 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <ShieldAlert className="w-3.5 h-3.5" />
              <span>2. Leads Faltando / Erros</span>
            </button>

            <button
              onClick={() => setActiveTab('import')}
              className={`flex items-center space-x-2 px-3 py-1.5 rounded-lg font-medium transition-all ${
                activeTab === 'import'
                  ? 'bg-sky-500 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <FileText className="w-3.5 h-3.5" />
              <span>3. Carregar Planilha</span>
            </button>
          </nav>

          {/* Botão de Ação Único */}
          <button
            onClick={onOpenTriggerModal}
            className="inline-flex items-center space-x-2 px-4 py-2 rounded-xl bg-sky-500 hover:bg-sky-400 text-white text-xs font-semibold shadow-md transition-all"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            <span>Rodar Análise</span>
          </button>
        </div>
      </div>
    </header>
  );
};
